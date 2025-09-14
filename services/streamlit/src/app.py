# =====================
# 1. Cargar configuración y logging
# =====================
import time
from urllib.parse import urlparse
import os
import csv
import yaml
import logging
import streamlit as st
import chromadb
from src.utils.logger import setup_logger
from src.utils.interaction import query_services, manager_input, fetch_supported_languages
import pandas as pd
import matplotlib.pyplot as plt

# Cargar configuración desde config.yaml
try:
    with open("/app/config.yaml", "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    st.error(f"No se pudo leer config.yaml: {e}")
    config = {}

# Configurar logging según el nivel definido en config.yaml
try:
    level = config.get("RUNNING", {}).get("LOG_LEVEL", "INFO")
    setup_logger(level)
except Exception as e:
    st.warning(f"No se pudo configurar el logger: {e}")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Filtrar los logs DEBUG de watchdog.observers.inotify_buffer
class WatchdogFilter(logging.Filter):
    def filter(self, record):
        return not (record.levelno == logging.DEBUG and record.name.startswith("watchdog.observers.inotify_buffer"))
for handler in logging.getLogger().handlers:
    handler.addFilter(WatchdogFilter())

# Silenciar loggers ruidosos de terceros (evita "matplotlib.font_manager" DEBUG, etc.)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.INFO)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.INFO)

STATS_FILE = '/data/statistics_response/statistics.csv'

# =====================
# 2. Definir endpoints de los microservicios
# =====================
ASR_URL_TRANSCRIBE = config.get("ASR", {}).get("TRANSCRIPTION_URL", "http://asr:8000/transcribe")
ASR_URL_LANGUAGES = config.get("ASR", {}).get("LANGUAGES_URL", "http://asr:8000/languages")
RAG_URL = config.get("RAG", {}).get("WEBHOOK_RAG_URL", "http://rag:8000/rag_result")
# AGENT_REACT_URL = config.get("RAG", {}).get("WEBHOOK_AGENT_REACT_URL", "http://rag:8000/react_agent_result")
CHROMADB_URL = config.get("VECTOR_DB", {}).get("URL", "http://chromadb:8000")

# Timeouts configurable desde config.yaml
_timeouts_cfg = config.get("TIMEOUTS", {})
ASR_TIMEOUT = int(_timeouts_cfg.get("ASR", 60))
RAG_TIMEOUT = int(_timeouts_cfg.get("RAG", 60))
# AGENT_TIMEOUT = int(_timeouts_cfg.get("AGENT_REACT", 60))

# Errores
OUTPUT_NOT_MATCH_ANSWER_CONTEXT = config.get("RAG", {}).get("OUTPUT_NOT_MATCH_ANSWER_CONTEXT", "The question does not match with the context provided.")

# =====================
# 3. Configuración de la interfaz Streamlit
# =====================
st.set_page_config(page_title="RAG Pilot Chatbot", layout="wide")
st.title("🛩️ RAG Pilot Chatbot")

# Menú lateral para navegación
menu = st.sidebar.radio("Navigation", ["Chatbot", "Vector Database"])

# =====================
# 4. Lógica del Chatbot
# =====================
if menu == "Chatbot":
    tabs = st.tabs(["Chat", "History", "Statistics"])
    with tabs[0]:
        st.header("Interactive Chatbot")
        st.write("Type your query below. You will get responses from RAG and Agent React in parallel.")

        ## Inicializar historial de chat en la sesión si no existe
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []   

        ## Input y audio en dos columnas, input más grande y audio bien visible
        col_input, col_audio, col_language = st.columns([3,1.5,1.5])
        with col_input:
            user_input = st.chat_input(
                "Type your query...",
                accept_file=True,
                file_type=["wav", "mp3"],
            )
        with col_audio:           
            recorded_audio = st.audio_input(
                label="Record audio",
                # help="Record your query by voice",
                label_visibility="collapsed", # "visible", "collapsed"
            )
            logger.info(f"recorded_audio: {recorded_audio}")
        with col_language:
            lang_map = fetch_supported_languages(asr_languages_url=ASR_URL_LANGUAGES, asr_timeout=ASR_TIMEOUT)
            if lang_map:
                lang_names = list(lang_map.keys())
                default_label = "Auto-detect/Multi-language"
                default_index = lang_names.index(default_label) if default_label in lang_names else 0
                selected_name = st.selectbox("Select the audio language to improve transcription.", options=lang_names, index=default_index)
                language = lang_map.get(selected_name)
            else:
                selected_name = "Auto-detect/Multi-language"
                language = None
            logger.info(f"Selected language for ASR: {selected_name} -> {language}")

        ## Procesar entrada del usuario (texto y/o audio)
        text_input = manager_input(
            user_input=user_input,
            recorded_audio=recorded_audio,
            asr_transcription_url=ASR_URL_TRANSCRIBE,
            asr_timeout=ASR_TIMEOUT,
            language=language
        )
        # Si hay input (texto o audio transcrito), consultar RAG y Agent React
        if text_input:
            logger.info(f"Usuario ha enviado la consulta: {text_input}")
            # Use centralized _query_services to perform calls and update UI
            results = query_services(
                text_input, 
                rag_url=RAG_URL, 
                # agent_react_url=AGENT_REACT_URL, 
                rag_timeout=RAG_TIMEOUT, 
                # agent_timeout=AGENT_TIMEOUT, 
                output_not_match_answer_context=OUTPUT_NOT_MATCH_ANSWER_CONTEXT
            )
            # Guardar info de la interacción en CSV usando los resultados retornados
            os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
            # Para el CSV, distinguir correctamente:
            # - Text Input: solo el texto escrito por el usuario
            # - Audio Input: solo la transcripción del audio
            # Estos valores se mantienen en session_state por _transcribe_audio y por las ramas de input
            input_text = st.session_state.get('last_text_input', '')
            input_audio = st.session_state.get('last_audio_input', '')
            transcription_time = st.session_state.get('last_transcription_time', '')

            rag_status_code = results.get('rag_status_code', None)            
            rag_status = results.get('rag_status', '')            
            rag_error_message = results.get('rag_error_message', None)  # Nuevo campo
            rag_answer = results.get('rag_answer', '')
            rag_context = results.get('rag_context', None)  # Nuevo campo            
            rag_time = results.get('rag_time', '')

            agent_status_code = results.get('agent_status_code', None)
            agent_status = results.get('agent_status', '')
            agent_error_message = results.get('agent_error_message', None)  # Nuevo campo
            agent_answer = results.get('agent_answer', '')
            agent_context = results.get('agent_context', None)  # Nuevo campo            
            agent_time = results.get('agent_time', '')

            today = time.strftime('%d/%m/%Y')

            write_header = not os.path.exists(STATS_FILE)
            with open(STATS_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow([
                        'Text Input', 'Audio Input', 'Transcription Time',
                        'RAG Status Code', 'RAG Status', 'RAG Error Message', 'RAG Answer', 'RAG Context', 'RAG Response Time',
                        'AgentReact Status Code', 'AgentReact Status', 'AgentReact Error Message', 'AgentReact Answer', 'AgentReact Context', 'AgentReact Response Time',
                        'Date'
                    ])
                writer.writerow([
                    input_text, input_audio, transcription_time,
                    rag_status_code, rag_status, rag_error_message, rag_answer, rag_context, rag_time,
                    agent_status_code, agent_status, agent_error_message, agent_answer, agent_context, agent_time,
                    today
                ])

    with tabs[1]:
        st.header("Conversation History")
        # Render history at the top
        for m in st.session_state.chat_history:
            st.chat_message(m["role"]).markdown(m["content"])
    
    # --- TAB 2: Estadísticas del chatbot ---
    with tabs[2]:
        if os.path.exists(STATS_FILE):
            df = pd.read_csv(STATS_FILE)

            # Convertir columnas numéricas de manera segura
            for col_name in [
                'Transcription Time',
                'RAG Response Time',
                'AgentReact Response Time'
            ]:
                if col_name in df.columns:
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

            # KPIs
            st.subheader("Overview")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)  # Primera fila: métricas generales
            with kpi1:
                st.metric("Total Interactions", len(df))
            with kpi2:
                text_interactions = df['Text Input'].notna().sum() if 'Text Input' in df.columns else 0
                st.metric("Text Interactions", text_interactions)
            with kpi3:
                audio_interactions = df['Audio Input'].notna().sum() if 'Audio Input' in df.columns else 0
                st.metric("Audio Interactions", audio_interactions)
            with kpi4:
                st.metric("Today", df['Date'].eq(time.strftime('%d/%m/%Y')).sum() if 'Date' in df.columns else 0)

            kpi5, kpi6, kpi7, kpi8 = st.columns(4)  # Segunda fila: métricas relacionadas con tiempos y errores
            with kpi5:
                avg_transc = df['Transcription Time'].mean() if 'Transcription Time' in df.columns else None
                st.metric("Avg Transcription (s)", f"{avg_transc:.2f}" if avg_transc is not None and not pd.isna(avg_transc) else "—")
            with kpi6:
                avg_rag = df['RAG Response Time'].mean() if 'RAG Response Time' in df.columns else None
                st.metric("Avg RAG (s)", f"{avg_rag:.2f}" if avg_rag is not None and not pd.isna(avg_rag) else "—")
            with kpi7:
                avg_agent = df['AgentReact Response Time'].mean() if 'AgentReact Response Time' in df.columns else None
                st.metric("Avg AgentReact (s)", f"{avg_agent:.2f}" if avg_agent is not None and not pd.isna(avg_agent) else "—")
            with kpi8:
                error_count = df['RAG Error Message'].notna().sum() + df['AgentReact Error Message'].notna().sum()
                st.metric("Total Errors", error_count)

            st.markdown("---")
            
            # Definir una paleta de colores uniforme
            palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

            # --- Estadísticas de Audio Input ---
            st.subheader("Audio Input Statistics")
            col1, col2 = st.columns(2)

            # Gráfico 1: Distribución del tiempo de transcripción (frecuencia en intervalos de 1 segundo)
            with col1:
                if 'Transcription Time' in df.columns and df['Transcription Time'].notna().any():
                    st.markdown("<h4 style='text-align: center;'>Transcription Time Distribution</h4>", unsafe_allow_html=True)
                    fig_transc, ax_transc = plt.subplots(figsize=(4, 4))
                    df['Transcription Time'].dropna().plot(kind='hist', bins=range(0, int(df['Transcription Time'].max()) + 2), ax=ax_transc, color='#1f77b4', alpha=0.8)
                    ax_transc.set_xlabel('Seconds')
                    ax_transc.set_ylabel('Frequency')
                    ax_transc.grid(axis='y', linestyle='--', alpha=0.5)
                    st.pyplot(fig_transc)

            # Gráfico 2: Frecuencia de valores de Audio Input
            with col2:
                if 'Audio Input' in df.columns:
                    st.markdown("<h4 style='text-align: center;'>Audio Input Frequency</h4>", unsafe_allow_html=True)
                    fig_audio, ax_audio = plt.subplots(figsize=(4, 4))
                    
                    # Truncar los valores de Audio Input para mostrar solo las primeras palabras
                    audio_input_counts = df['Audio Input'].value_counts()
                    truncated_labels = [label[:10] + "..." if len(label) > 10 else label for label in audio_input_counts.index]
                    
                    audio_input_counts.index = truncated_labels  # Actualizar los índices con los valores truncados
                    audio_input_counts.plot(kind='bar', ax=ax_audio, color='#ff7f0e', alpha=0.8)
                    
                    ax_audio.set_xlabel('Audio Input')
                    ax_audio.set_ylabel('Frequency')
                    ax_audio.grid(axis='y', linestyle='--', alpha=0.5)
                    plt.xticks(rotation=45, ha='right')  # Rotar las etiquetas para mejor legibilidad
                    st.pyplot(fig_audio)

            # --- Primera fila: RAG ---
            st.header("RAG Statistics")
            col1, col2, col3 = st.columns(3)

            # Gráfico 1: Distribución del tiempo de respuesta (frecuencia en intervalos de 1 segundo)
            with col1:
                if 'RAG Response Time' in df.columns and df['RAG Response Time'].notna().any():
                    st.markdown("<h4 style='text-align: center;'>Response Time Distribution</h4>", unsafe_allow_html=True)
                    fig_rt, ax_rt = plt.subplots(figsize=(4, 4))
                    df['RAG Response Time'].dropna().plot(kind='hist', bins=range(0, int(df['RAG Response Time'].max()) + 2), ax=ax_rt, color=palette[0], alpha=0.8)
                    ax_rt.set_xlabel('Seconds')
                    ax_rt.set_ylabel('Frequency')
                    ax_rt.grid(axis='y', linestyle='--', alpha=0.5)
                    st.pyplot(fig_rt)

            # Gráfico 2: Frecuencia de códigos de estado
            with col2:
                if 'RAG Status Code' in df.columns:
                    st.markdown("<h4 style='text-align: center;'>Status Code Frequency</h4>", unsafe_allow_html=True)
                    fig_bar, ax_bar = plt.subplots(figsize=(4, 4))
                    rag_status_code_counts = df['RAG Status Code'].value_counts()
                    rag_status_code_counts.plot(kind='bar', ax=ax_bar, color=palette[0], alpha=0.8)
                    ax_bar.set_xlabel('Status Code')
                    ax_bar.set_ylabel('Frequency')
                    ax_bar.grid(axis='y', linestyle='--', alpha=0.5)
                    st.pyplot(fig_bar)

            # Gráfico 3: Porcentaje de estados (no códigos de estado)
            with col3:
                if 'RAG Status' in df.columns:
                    st.markdown("<h4 style='text-align: center;'>Status Percentage</h4>", unsafe_allow_html=True)
                    rag_status_counts = df['RAG Status'].value_counts()
                    if not rag_status_counts.empty:
                        fig_pie, ax_pie = plt.subplots(figsize=(4, 4))
                        rag_status_counts.plot(
                            kind='pie',
                            ax=ax_pie,
                            autopct='%1.1f%%',
                            startangle=90,
                            colors=palette[:len(rag_status_counts)],  # Usar colores dinámicos de la paleta
                            textprops={'fontsize': 10}
                        )
                        ax_pie.set_ylabel('')
                        st.pyplot(fig_pie)

            st.markdown("---")
            
            # --- Segunda fila: Agent React ---
            st.header("Agent React Statistics")
            col1, col2, col3 = st.columns(3)

            # Gráfico 1: Distribución del tiempo de respuesta (frecuencia en intervalos de 1 segundo)
            with col1:
                if 'AgentReact Response Time' in df.columns and df['AgentReact Response Time'].notna().any():
                    st.markdown("<h4 style='text-align: center;'>Response Time Distribution</h4>", unsafe_allow_html=True)
                    fig_rt, ax_rt = plt.subplots(figsize=(4, 4))
                    df['AgentReact Response Time'].dropna().plot(kind='hist', bins=range(0, int(df['AgentReact Response Time'].max()) + 2), ax=ax_rt, color=palette[0], alpha=0.8)
                    ax_rt.set_xlabel('Seconds')
                    ax_rt.set_ylabel('Frequency')
                    ax_rt.grid(axis='y', linestyle='--', alpha=0.5)
                    st.pyplot(fig_rt)

            # Gráfico 2: Frecuencia de códigos de estado
            with col2:
                if 'AgentReact Status Code' in df.columns:
                    st.markdown("<h4 style='text-align: center;'>Status Code Frequency</h4>", unsafe_allow_html=True)
                    fig_bar, ax_bar = plt.subplots(figsize=(4, 4))
                    agent_status_code_counts = df['AgentReact Status Code'].value_counts()
                    agent_status_code_counts.plot(kind='bar', ax=ax_bar, color=palette[0], alpha=0.8)
                    ax_bar.set_xlabel('Status Code')
                    ax_bar.set_ylabel('Frequency')
                    ax_bar.grid(axis='y', linestyle='--', alpha=0.5)
                    st.pyplot(fig_bar)

            # Gráfico 3: Porcentaje de estados (no códigos de estado)
            with col3:
                if 'AgentReact Status' in df.columns:
                    st.markdown("<h4 style='text-align: center;'>Status Percentage</h4>", unsafe_allow_html=True)
                    agent_status_counts = df['AgentReact Status'].value_counts()
                    if not agent_status_counts.empty:
                        fig_pie, ax_pie = plt.subplots(figsize=(4, 4))
                        agent_status_counts.plot(
                            kind='pie',
                            ax=ax_pie,
                            autopct='%1.1f%%',
                            startangle=90,
                            colors=palette[:len(agent_status_counts)],  # Usar colores dinámicos de la paleta
                            textprops={'fontsize': 10}
                        )
                        ax_pie.set_ylabel('')
                        st.pyplot(fig_pie)

            # --- Tablas finales ---
            st.markdown("---")            
            st.header("Error Messages")
            # Dos tablas en la misma fila
            col_1, col_2 = st.columns(2)
            with col_1:
                st.markdown("### RAG")
                if 'RAG Error Message' in df.columns:
                    rag_error_counts = df['RAG Error Message'].value_counts()
                    st.table(rag_error_counts)

            with col_2:
                st.markdown("### Agent React")
                if 'AgentReact Error Message' in df.columns:
                    agent_error_counts = df['AgentReact Error Message'].value_counts()
                    st.table(agent_error_counts)
            
            st.markdown("---")

            # Dos tablas en la misma fila            
            st.header("Contexts")
            col_1, col_2 = st.columns(2)
            with col_1:
                st.markdown("### RAG")
                if 'RAG Context' in df.columns:
                    rag_context_counts = df['RAG Context'].value_counts().head(5)
                    st.table(rag_context_counts)
            with col_2:
                st.markdown("### Agent React")
                if 'AgentReact Context' in df.columns:
                    agent_context_counts = df['AgentReact Context'].value_counts().head(5)
                    st.table(agent_context_counts)
            
            st.markdown("---")
            # Descargar CSV
            st.header("All Interactions")
            st.download_button(
                label="Download CSV",
                data=df.to_csv(index=False).encode('utf-8'),
                file_name="statistics.csv",
                mime="text/csv"
            )
            st.dataframe(df, width='stretch')
        else:
            st.info("No statistics available yet.")

# =====================
# 5. Visualización de la base de datos vectorial
# =====================
elif menu == "Vector Database":
    tabs = st.tabs(["Statistics", "Chunks"])
    try:
        logger.info("Conectando a ChromaDB local...")
        if not (CHROMADB_URL.startswith("http://") or CHROMADB_URL.startswith("https://")):
            raise ValueError("CHROMADB_URL debe ser una URL HTTP para ChromaDB remoto (microservicio)")
        parsed = urlparse(CHROMADB_URL)
        host = parsed.hostname
        port = parsed.port or 8000
        client = chromadb.HttpClient(host=host, port=port)
        collections = client.list_collections()
        if not collections:
            tabs[1].info("No hay colecciones en la base de datos vectorial.")
            logger.info("No hay colecciones en la base de datos vectorial.")
        else:
            # --- TAB 1: Estadísticas ---
            with tabs[0]:
                st.markdown("## Vector Database Statistics")
                total_chunks = 0
                doc_filenames = {}
                col_names = []
                for col in collections:
                    col_names.append(col.name)
                    collection = client.get_collection(col.name)
                    docs = collection.get()
                    embeddings = docs.get("embeddings", [])
                    metadatas = docs.get("metadatas", [])
                    total_chunks += len(metadatas)
                    for meta in metadatas:
                        if isinstance(meta, dict):
                            if "origin" in meta:
                                origin = meta.get("origin")
                                filename = None
                                import json
                                if origin:
                                    try:
                                        if isinstance(origin, str):
                                            origin_dict = json.loads(origin)
                                        else:
                                            origin_dict = origin
                                        filename = origin_dict.get("filename")
                                    except Exception:
                                        filename = None
                                if filename:
                                    doc_filenames.setdefault(filename, 0)
                                    doc_filenames[filename] += 1
                            elif "filename" in meta:
                                filename = meta.get("filename")
                                if filename:
                                    doc_filenames.setdefault(filename, 0)
                                    doc_filenames[filename] += 1
                # Gráficos visuales
                st.markdown(f"**Total collections:** {len(col_names)}")
                st.markdown(f"**Collections:** {', '.join(col_names)}")
                st.markdown(f"**Total chunks:** {total_chunks}")
                st.markdown(f"**Total unique documents:** {len(doc_filenames)}")
                # Chunks per document - two charts in the same row
                if doc_filenames:
                    df_chunks = pd.DataFrame(list(doc_filenames.items()), columns=["Document", "Chunks"])
                    st.markdown("### Chunks per document:")
                    col_bar, col_pie = st.columns(2)
                    with col_bar:
                        fig_bar, ax_bar = plt.subplots()
                        df_chunks.plot(kind='bar', x='Document', y='Chunks', ax=ax_bar, legend=False, color='#1f77b4')
                        ax_bar.set_ylabel('Chunks')
                        ax_bar.set_title('Chunks per Document')
                        ax_bar.grid(axis='y', linestyle='--', alpha=0.5)
                        plt.xticks(rotation=45, ha='right')
                        st.pyplot(fig_bar)
                    with col_pie:
                        fig_pie, ax_pie = plt.subplots()
                        colors = plt.cm.Paired(range(len(df_chunks)))
                        ax_pie.pie(df_chunks["Chunks"], labels=df_chunks["Document"], autopct='%1.1f%%', startangle=90, colors=colors)
                        ax_pie.set_title('Chunks Distribution per Document')
                        ax_pie.axis('equal')
                        st.pyplot(fig_pie)
            # --- TAB 2: Chunks ---
            with tabs[1]:
                # Obtener lista de colecciones
                collection_names = [col.name for col in collections]
                selected_collection = st.selectbox("Select a collection", collection_names, key="collection_selector")

                if selected_collection:
                    # Obtener la colección seleccionada
                    collection = client.get_collection(selected_collection)
                    docs = collection.get()
                    ids = docs.get("ids", [])
                    metadatas = docs.get("metadatas", [])
                    documents = docs.get("documents", [])

                    # --- Filtros ---
                    # Obtener lista de filenames únicos
                    filenames = []
                    for meta in metadatas:
                        if isinstance(meta, dict):
                            if "origin" in meta:
                                origin = meta.get("origin")
                                import json
                                filename = None
                                if origin:
                                    try:
                                        if isinstance(origin, str):
                                            origin_dict = json.loads(origin)
                                        else:
                                            origin_dict = origin
                                        filename = origin_dict.get("filename")
                                    except Exception:
                                        filename = None
                                if filename:
                                    filenames.append(filename)
                            elif "filename" in meta:
                                filename = meta.get("filename")
                                if filename:
                                    filenames.append(filename)
                    filenames = sorted(list(set(filenames)))
                    selected_filename = st.selectbox("Filter by document (filename)", ["All"] + filenames, key=f"filename_{selected_collection}")
                    keyword = st.text_input("Filter by keyword in chunk", value="", key=f"keyword_{selected_collection}")

                    # --- Mostrar chunks filtrados ---
                    filtered_idxs = []
                    for idx, meta in enumerate(metadatas):
                        # Filtrar por filename
                        show = True
                        filename = None
                        if isinstance(meta, dict):
                            origin = meta.get("origin")
                            import json
                            if origin:
                                try:
                                    if isinstance(origin, str):
                                        origin_dict = json.loads(origin)
                                    else:
                                        origin_dict = origin
                                    filename = origin_dict.get("filename")
                                except Exception:
                                    filename = None
                        if selected_filename != "All" and filename != selected_filename:
                            show = False
                        # Filtrar por palabra clave
                        doc_text = documents[idx] if idx < len(documents) else ''
                        if keyword and keyword.lower() not in doc_text.lower():
                            show = False
                        if show:
                            filtered_idxs.append(idx)
                    n = len(filtered_idxs)
                    for i in range(0, n, 3):
                        cols = st.columns(3)
                        for j in range(3):
                            if i + j < n:
                                idx = filtered_idxs[i + j]
                                with cols[j]:
                                    st.markdown(f"**ID:** {ids[idx]}")
                                    doc_text = documents[idx] if idx < len(documents) else ''
                                    st.markdown(f"**Chunk (raw):**\n\n{doc_text}")
                                    # Metadata como antes
                                    meta = metadatas[idx] if idx < len(metadatas) else {}
                                    if isinstance(meta, dict):
                                        sorted_meta = dict(sorted(meta.items()))
                                        with st.expander("Metadata", expanded=False):
                                            for k, v in sorted_meta.items():
                                                st.markdown(f"- **{k}:** {v}")
                                    else:
                                        st.markdown(f"**Metadata:** {meta}")
                                    st.markdown("---")
    except Exception as e:
        logger.exception(f"Error querying ChromaDB: {e}")
        st.error(f"Error querying ChromaDB: {e}")