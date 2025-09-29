# =====================
# 1. Cargar configuración y logging
# =====================
import time, requests, streamlit as st
from urllib.parse import urlparse
import os
import csv
import yaml
import logging
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

def wait_ready(base_url: str, timeout: int = 300, label: str = "Inicializando..."):
    base = base_url.rstrip("/")
    key = f"warmup_sent::{base}"
    if key not in st.session_state:
        st.session_state[key] = False

    with st.spinner(label):
        start = time.time()
        while time.time() - start < timeout:
            try:
                if not st.session_state[key]:
                    logger.info(f"[INIT] warmup -> {base}/warmup")
                    requests.post(f"{base}/warmup", timeout=timeout)
                    st.session_state[key] = True
                r = requests.get(f"{base}/readyz", timeout=timeout)
                if r.ok and r.json().get("ready"):
                    logger.info(f"[INIT] {base} listo")
                    return True
            except Exception as ex:
                logger.warning(f"[INIT] error contactando {base}: {ex}")
            time.sleep(1.5)
    st.error(f"Timeout inicializando {base}")
    return False

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

# Inicializar
if not wait_ready("http://asr:8000", label="Inicializando ASR..."):
    st.stop()
if not wait_ready("http://rag:8000", label="Inicializando RAG..."):
    st.stop()
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

            # Valores de entrada
            input_text = st.session_state.get('last_text_input', '')
            input_audio = st.session_state.get('last_audio_input', '')
            transcription_time = st.session_state.get('last_transcription_time', '')

            # Extraer métricas de RAG
            rag_status_code = results.get('rag_status_code', None)
            rag_status = results.get('rag_status', '')
            rag_error_message = results.get('rag_error_message', None)
            rag_answer = results.get('rag_answer', '')
            rag_context = results.get('rag_context', None) or []
            rag_time = results.get('rag_time', '')

            # Nuevas métricas: scores y páginas
            rag_scores = [float(x.get("score", 0) or 0) for x in rag_context if isinstance(x, dict)]
            rag_pages_list = [x.get("page_number", "unknown") for x in rag_context if isinstance(x, dict)]
            rag_context_size = len(rag_context)
            rag_top_score = max(rag_scores) if rag_scores else None
            rag_avg_score = (sum(rag_scores) / len(rag_scores)) if rag_scores else None
            # Página más frecuente (excluye unknown si hay otras)
            from collections import Counter
            pages_counter = Counter([p for p in rag_pages_list if p is not None])
            if pages_counter:
                # Si hay páginas válidas distintas de 'unknown', priorízalas
                pages_no_unknown = Counter([p for p in rag_pages_list if p not in (None, "", "unknown")])
                rag_top_page = (pages_no_unknown or pages_counter).most_common(1)[0][0]
            else:
                rag_top_page = None
            # Serializa páginas para el CSV (p.ej. "3;4;4;5")
            rag_pages_serialized = ";".join([str(p) for p in rag_pages_list]) if rag_pages_list else ""

            today = time.strftime('%d/%m/%Y')

            # Esquema del CSV (solo RAG + nuevas métricas)
            headers = [
                'Text Input', 'Audio Input', 'Transcription Time',
                'RAG Status Code', 'RAG Status', 'RAG Error Message',
                'RAG Answer', 'RAG Response Time',
                'RAG Context Size', 'RAG Top Score', 'RAG Avg Score',
                'RAG Top Page', 'RAG Pages',
                'Date'
            ]

            row = [
                input_text, input_audio, transcription_time,
                rag_status_code, rag_status, rag_error_message,
                rag_answer, rag_time,
                rag_context_size, rag_top_score, rag_avg_score,
                rag_top_page, rag_pages_serialized,
                today
            ]

            # Escribir CSV con rotación si cambia el esquema
            write_mode = 'a'
            write_header = False
            if not os.path.exists(STATS_FILE):
                write_mode, write_header = 'w', True
            else:
                try:
                    with open(STATS_FILE, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                    existing_cols = [c.strip() for c in first_line.split(',')] if first_line else []
                    if existing_cols != headers:
                        write_mode, write_header = 'w', True
                except Exception:
                    write_mode, write_header = 'w', True

            with open(STATS_FILE, write_mode, newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(headers)
                writer.writerow(row)

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
                # 'RAG Context Size',  # eliminado: el contexto siempre es 3-4, no aporta
                'RAG Top Score',
                'RAG Avg Score'
            ]:
                if col_name in df.columns:
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

            # KPIs
            st.subheader("Overview")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            with kpi1:
                st.metric("Total Interactions", len(df))
            with kpi2:
                st.metric("Today", df['Date'].eq(time.strftime('%d/%m/%Y')).sum() if 'Date' in df.columns else 0)
            with kpi3:
                avg_transc = df['Transcription Time'].mean() if 'Transcription Time' in df.columns else None
                st.metric("Avg Transcription (s)", f"{avg_transc:.2f}" if avg_transc is not None and not pd.isna(avg_transc) else "—")
            with kpi4:
                avg_rag = df['RAG Response Time'].mean() if 'RAG Response Time' in df.columns else None
                st.metric("Avg RAG (s)", f"{avg_rag:.2f}" if avg_rag is not None and not pd.isna(avg_rag) else "—")

            # Solo mantenemos Avg Top Score (quitamos Avg Context Size)
            kpi5 = st.container()
            with kpi5:
                avg_top_score = df['RAG Top Score'].mean() if 'RAG Top Score' in df.columns else None
                st.metric("Avg Top Score", f"{avg_top_score:.3f}" if avg_top_score is not None and not pd.isna(avg_top_score) else "—")

            st.markdown("---")
            palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

            # Top Score Distribution (a ancho completo). Eliminada la gráfica de Context Size.
            if 'RAG Top Score' in df.columns and df['RAG Top Score'].notna().any():
                st.markdown("<h4 style='text-align: center;'>Top Score Distribution</h4>", unsafe_allow_html=True)
                fig_ts, ax_ts = plt.subplots(figsize=(8, 4))
                df['RAG Top Score'].dropna().plot(kind='hist', bins=20, ax=ax_ts, color=palette[0], alpha=0.85)
                ax_ts.set_xlabel('Score')
                ax_ts.set_ylabel('Frequency')
                ax_ts.grid(axis='y', linestyle='--', alpha=0.5)
                st.pyplot(fig_ts)
            else:
                st.info("No data to plot Top Score Distribution.")

            # Response time vs top score (left) AND Pages frequency (right) side by side
            col_left, col_right = st.columns(2)

            with col_left:
                if {'RAG Response Time', 'RAG Top Score'}.issubset(df.columns):
                    st.markdown("<h4 style='text-align: center;'>Response Time vs Top Score</h4>", unsafe_allow_html=True)
                    mask = df['RAG Response Time'].notna() & df['RAG Top Score'].notna()
                    if mask.any():
                        fig_sc, ax_sc = plt.subplots(figsize=(5, 4))
                        ax_sc.scatter(df.loc[mask, 'RAG Response Time'], df.loc[mask, 'RAG Top Score'], color=palette[2], alpha=0.7)
                        ax_sc.set_xlabel('RAG Response Time (s)')
                        ax_sc.set_ylabel('Top Score')
                        ax_sc.grid(axis='both', linestyle='--', alpha=0.4)
                        st.pyplot(fig_sc)
                    else:
                        st.info("No data to plot.")
                else:
                    st.info("Missing columns to plot.")

            with col_right:
                if 'RAG Pages' in df.columns and df['RAG Pages'].notna().any():
                    st.markdown("<h4 style='text-align: center;'>Pages Frequency (across all responses)</h4>", unsafe_allow_html=True)
                    all_pages = []
                    for s in df['RAG Pages'].dropna().astype(str).tolist():
                        all_pages.extend([p for p in s.split(';') if p])
                    if all_pages:
                        import collections
                        page_counts = collections.Counter(all_pages)
                        # Ordenar por número de página ascendente; no numéricos al final
                        df_pages = pd.DataFrame(page_counts.items(), columns=["Page", "Count"])
                        df_pages["Page_num"] = pd.to_numeric(df_pages["Page"], errors="coerce")
                        df_pages = df_pages.sort_values(by=["Page_num", "Page"], ascending=[True, True])
                        fig_pg, ax_pg = plt.subplots(figsize=(5, 4))
                        ax_pg.bar(df_pages["Page"].astype(str), df_pages["Count"], color=palette[3])
                        ax_pg.set_xlabel('Page')
                        ax_pg.set_ylabel('Count')
                        ax_pg.grid(axis='y', linestyle='--', alpha=0.5)
                        plt.xticks(rotation=45, ha='right')
                        st.pyplot(fig_pg)
                    else:
                        st.info("No pages data.")
                else:
                    st.info("No 'RAG Pages' data.")

            # --- Nueva fila: Response Time y Frecuencia por Status Code ---
            st.markdown("---")
            st.markdown("### Response Time and Frequency by Status Code")
            col_sleft, col_sright = st.columns(2)

            with col_sleft:
                if {'RAG Response Time', 'RAG Status Code'}.issubset(df.columns):
                    # Filtra válidos
                    df_rt = df[['RAG Response Time', 'RAG Status Code']].dropna()
                    if not df_rt.empty:
                        # Agrupa por status code
                        grouped = df_rt.groupby('RAG Status Code')['RAG Response Time'].apply(list)
                        if not grouped.empty:
                            st.markdown("<h4 style='text-align: center;'>Response Time by Status Code</h4>", unsafe_allow_html=True)
                            labels = [str(int(k)) if pd.notna(k) else "NaN" for k in grouped.index]
                            data = [v for v in grouped.values]
                            fig_box, ax_box = plt.subplots(figsize=(5, 4))
                            ax_box.boxplot(data, labels=labels, patch_artist=True,
                                           boxprops=dict(facecolor="#cfe2f3", color="#1f77b4"),
                                           medianprops=dict(color="#d62728"),
                                           whiskerprops=dict(color="#1f77b4"),
                                           capprops=dict(color="#1f77b4"))
                            ax_box.set_xlabel('Status Code')
                            ax_box.set_ylabel('RAG Response Time (s)')
                            ax_box.grid(axis='y', linestyle='--', alpha=0.4)
                            st.pyplot(fig_box)
                        else:
                            st.info("No data to plot Response Time by Status Code.")
                    else:
                        st.info("No data to plot Response Time by Status Code.")
                else:
                    st.info("Missing columns to plot Response Time by Status Code.")

            with col_sright:
                if 'RAG Status Code' in df.columns:
                    st.markdown("<h4 style='text-align: center;'>Status Code Distribution</h4>", unsafe_allow_html=True)
                    counts = df['RAG Status Code'].value_counts(dropna=False).sort_index()
                    if not counts.empty:
                        # Pie chart
                        fig_pie, ax_pie = plt.subplots(figsize=(5, 3.6))
                        labels = [str(int(i)) if pd.notna(i) else "NaN" for i in counts.index]
                        colors = plt.cm.Pastel1(range(len(counts)))
                        ax_pie.pie(counts.values, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
                        ax_pie.axis('equal')
                        st.pyplot(fig_pie)

                        # Bar chart (frecuencias)
                        st.markdown("<h5 style='text-align: center;'>Status Code Frequency</h5>", unsafe_allow_html=True)
                        fig_bar, ax_bar = plt.subplots(figsize=(5, 3.6))
                        ax_bar.bar(labels, counts.values, color='#8c564b', alpha=0.9)
                        ax_bar.set_xlabel('Status Code')
                        ax_bar.set_ylabel('Count')
                        ax_bar.grid(axis='y', linestyle='--', alpha=0.5)
                        st.pyplot(fig_bar)
                    else:
                        st.info("No status code data.")
                else:
                    st.info("No 'RAG Status Code' column.")

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

# Ejemplo de uso al inicio de la app Streamlit:
# rag_url = "http://rag:8000"  # o desde config
# if not wait_ready(rag_url):
#     st.stop()