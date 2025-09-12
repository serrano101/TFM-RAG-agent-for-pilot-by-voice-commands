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
import requests
import chromadb
from src.utils.logger import setup_logger
import threading
from queue import Queue
import pandas as pd
import matplotlib.pyplot as plt
from fastapi import UploadFile, File
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


STATS_FILE = '/data/statistics_response/statistics.csv'

# =====================
# 2. Definir endpoints de los microservicios
# =====================
ASR_URL = config.get("ASR", {}).get("URL", "http://asr:8000") + "/transcribe"
RAG_URL = config.get("RAG", {}).get("WEBHOOK_RAG_URL", "http://rag:8000/rag_result")
AGENT_REACT_URL = config.get("RAG", {}).get("WEBHOOK_AGENT_REACT_URL", "http://rag:8000/react_agent_result")
CHROMADB_URL = config.get("VECTOR_DB", {}).get("URL", "http://chromadb:8000")

# =====================
# 3. Configuración de la interfaz Streamlit
# =====================
st.set_page_config(page_title="RAG Pilot Chatbot", layout="wide")
st.title("🛩️ RAG Pilot Chatbot")

# Menú lateral para navegación
menu = st.sidebar.radio("Navegación", ["Chatbot", "Vector Database"])

# =====================
# 4. Lógica del Chatbot
# =====================
if menu == "Chatbot":
    tabs = st.tabs(["Chat", "History", "Statistics"])
    with tabs[0]:
        st.header("Interactive Chatbot")
        st.write("Type your query below. You will get responses from RAG and Agent React in parallel.")

        # Function definitions and logic must be inside this block
        def _query_services(user_input:str):
            col_rag, col_agent = st.columns(2)
            rag_placeholder = col_rag.empty()
            agent_placeholder = col_agent.empty()
            queue = Queue()
            def fetch_rag_async(user_input, queue):
                try:                    
                    logger.info(f"Enviando consulta a RAG: {user_input}")
                    start_rag = time.time()
                    response_rag = requests.post(RAG_URL, json={"transcription": user_input}, timeout=60)
                    response_rag.raise_for_status()
                    end_rag = time.time()
                    rag_json = response_rag.json()
                    status = rag_json.get("status", "")
                    resp = rag_json.get("response", {})                    
                    queue.put(("rag", resp, status, None, end_rag - start_rag))
                except Exception as e:
                    queue.put(("rag", None, None, str(e), None))
            def fetch_agent_async(user_input, queue):
                try:                    
                    logger.info(f"Enviando consulta a Agent React: {user_input}")
                    start_agent = time.time()
                    response_agent = requests.post(AGENT_REACT_URL, json={"transcription": user_input}, timeout=60)
                    response_agent.raise_for_status()                    
                    end_agent = time.time()
                    agent_json = response_agent.json()
                    status = agent_json.get("status", "")
                    resp = agent_json.get("response", {})
                    queue.put(("agent", resp, status, None, end_agent - start_agent))
                except Exception as e:
                    queue.put(("agent", None, None, str(e), None))
            thread_rag = threading.Thread(target=fetch_rag_async, args=(user_input, queue))
            thread_agent = threading.Thread(target=fetch_agent_async, args=(user_input, queue))
            thread_rag.start()
            thread_agent.start()
            shown = {"rag": False, "agent": False}
            results = {"rag": None, "agent": None}
            errors = {"rag": None, "agent": None}
            statuses = {"rag": None, "agent": None}
            times = {"rag": None, "agent": None}
            # Mostrar título y spinner inicial en ambos
            with rag_placeholder.container():
                st.subheader("RAG")
                st.info("Waiting for RAG response...")
            with agent_placeholder.container():
                st.subheader("Agent React")
                st.info("Waiting for Agent React response...")
            # Variables para guardar en CSV
            rag_answer, rag_status, rag_time = None, None, None
            agent_answer, agent_status, agent_time = None, None, None
            input_text, input_audio, transcription_time = None, None, None
            today = time.strftime('%d/%m/%Y')
            for _ in range(2):
                who, resp, status, error, elapsed = queue.get()
                results[who] = resp
                errors[who] = error
                statuses[who] = status
                times[who] = elapsed
                shown[who] = True
                # Actualizar el chat_history con la respuesta real
                if who == "rag":
                    rag_answer = resp.get("answer", "") if resp else ""
                    rag_status = status
                    rag_time = elapsed
                    rag_placeholder.empty()
                    with rag_placeholder.container():
                        st.subheader("RAG")
                        if error:
                            st.error(error)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] Error: {error}"})
                        else:
                            st.chat_message("assistant").write(rag_answer)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] {rag_answer}"})
                            with st.expander("RAG Details", expanded=False):
                                st.markdown(f"**🟢 Status:** {rag_status}")
                                st.markdown(f"**📝 Input:** {resp.get('input', '') if resp else ''}")
                                st.markdown(f"**📚 Context:** {resp.get('context', '') if resp else ''}")
                                if rag_time is not None:
                                    st.markdown(f"**⏱️ Response Time:** {rag_time:.1f} seconds")
                elif who == "agent":
                    agent_answer = resp.get("output", "") if resp else ""
                    agent_status = status
                    agent_time = elapsed
                    agent_placeholder.empty()
                    with agent_placeholder.container():
                        st.subheader("Agent React")
                        if error:
                            st.error(error)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent React] Error: {error}"})
                        else:
                            st.chat_message("assistant").write(agent_answer)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent React] {agent_answer}"})
                            with st.expander("Agent React Details", expanded=False):
                                st.markdown(f"**🟢 Status:** {agent_status}")
                                st.markdown(f"**📝 Input:** {resp.get('input', '') if resp else ''}")
                                if resp and 'context' in resp:
                                    st.markdown(f"**📚 Context:** {resp.get('context', '')}")
                                if agent_time is not None:
                                    st.markdown(f"**⏱️ Agent React Response Time:** {agent_time:.1f} seconds")
            # Return collected values so caller can write CSV or further process
            return {
                'rag_answer': rag_answer,
                'rag_status': rag_status,
                'rag_time': rag_time,
                'agent_answer': agent_answer,
                'agent_status': agent_status,
                'agent_time': agent_time,
                'input_text': user_input,
                'input_audio': st.session_state.get('last_audio_input', ''),
                'transcription_time': st.session_state.get('last_transcription_time', '')
            }

        def _transcribe_audio(
            audio_name: str = "default_audio", 
            audio_file: UploadFile = File(...),
            audio_type: str = "audio/wav"
        ) -> str:
            try:
                if hasattr(audio_file, "read"):
                    audio_bytes = audio_file.read()
                    st.audio(audio_bytes, format=audio_type)
                    # Volver al paso anterior para que se pueda mandar a transcribir
                    if hasattr(audio_file, "seek"):
                        audio_file.seek(0)
                else:
                    st.warning("Could not get audio to play.")
                with st.spinner("Transcribing audio..."):
                    logger.info("Sending audio to ASR for transcription")
                    files = {"file": (audio_name, audio_file, audio_type)}
                    start_transcription = time.time()
                    response = requests.post(ASR_URL, files=files, timeout=300)
                    response.raise_for_status()
                    end_transcription = time.time()
                    transcribed = response.json().get("transcription")
                    transcription_time = end_transcription - start_transcription
                    # Guardar info para estadísticas
                    st.session_state['last_text_input'] = ''
                    st.session_state['last_audio_input'] = transcribed
                    st.session_state['last_transcription_time'] = f"{transcription_time:.1f}"
                    st.chat_message("user").write(f"[Audio]: {st.session_state['last_audio_input']}")
                    st.session_state.chat_history.append({"role": "user", "content": f"[Audio]: {st.session_state['last_audio_input']}"})
                    logger.info(f"Transcription received: {transcribed}")
                    st.info(f"Transcription time: {transcription_time:.1f} seconds", icon="⏱️")
                    return transcribed
            except Exception as e:
                st.error(f"Error in audio transcription: {e}")

        # Inicializar historial de chat en la sesión si no existe
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Input y audio en dos columnas, input más grande y audio bien visible
        col_input, col_audio = st.columns([4, 1])
        with col_input:
            user_input = st.chat_input(
                "Type your query...",
                accept_file=True,
                file_type=["wav", "mp3"],
            )
        with col_audio:
            recorded_audio = st.audio_input(
                label="Record audio",
                help="Record your query by voice",
                label_visibility="visible",
                width=180
            )
            logger.info(f"recorded_audio: {recorded_audio}")
        # Procesar entrada del usuario (texto y/o audio)
        text_input = None
        # Si el usuario envía solo texto
        if user_input and user_input["text"] and not user_input["files"]:
            st.session_state['last_text_input'] = user_input["text"]
            st.session_state['last_audio_input'] = ''
            st.session_state['last_transcription_time'] = ''
            st.chat_message("user").write(user_input["text"])
            st.session_state.chat_history.append({"role": "user", "content": user_input["text"]})
            text_input = user_input["text"]
        # Si el usuario sube  solo audio
        elif user_input and user_input["files"] and not user_input["text"]:
            audio_name = user_input["files"][0].name
            audio_file = user_input["files"][0]
            audio_type = user_input["files"][0].type
            text_input = _transcribe_audio(audio_name, audio_file, audio_type)
            if not text_input:
                raise ValueError("No se pudo transcribir el audio subido.")
        # Si el usuario sube audio y texto, los combinamos
        elif user_input and user_input["text"] and user_input["files"]:
            audio_name = user_input["files"][0].name
            audio_file = user_input["files"][0]
            audio_type = user_input["files"][0].type
            text_audio = _transcribe_audio(audio_name, audio_file, audio_type)
            # Asegurar que el texto escrito por el usuario quede registrado como tal
            st.session_state['last_text_input'] = user_input['text']
            # Mostrar también el texto escrito en el historial del chat
            st.chat_message("user").write(user_input["text"])
            st.session_state.chat_history.append({"role": "user", "content": user_input["text"]})
            if text_audio:
                text_input = f"{user_input['text']} and {text_audio}"
            else:
                text_input = user_input['text']

        # Si el usuario graba audio, lo transcribimos y lo añadimos al historial
        if recorded_audio and not user_input:
            audio_name = recorded_audio.name
            audio_file = recorded_audio
            audio_type = recorded_audio.type
            text_input = _transcribe_audio(audio_name, audio_file, audio_type)
            if not text_input:
                raise ValueError("No se pudo transcribir el audio grabado.")

        # Si hay input (texto o audio transcrito), consultar RAG y Agent React
        if text_input:
            logger.info(f"Usuario ha enviado la consulta: {text_input}")
            # Use centralized _query_services to perform calls and update UI
            results = _query_services(text_input)
            # Guardar info de la interacción en CSV usando los resultados retornados
            stats_file = STATS_FILE
            os.makedirs(os.path.dirname(stats_file), exist_ok=True)
            # Para el CSV, distinguir correctamente:
            # - Text Input: solo el texto escrito por el usuario
            # - Audio Input: solo la transcripción del audio
            # Estos valores se mantienen en session_state por _transcribe_audio y por las ramas de input
            input_text = st.session_state.get('last_text_input', '')
            input_audio = st.session_state.get('last_audio_input', '')
            transcription_time = st.session_state.get('last_transcription_time', '')
            rag_answer = results.get('rag_answer', '')
            rag_time = results.get('rag_time', '')
            rag_status = results.get('rag_status', '')
            agent_answer = results.get('agent_answer', '')
            agent_time = results.get('agent_time', '')
            agent_status = results.get('agent_status', '')
            today = time.strftime('%d/%m/%Y')
            write_header = not os.path.exists(stats_file)
            with open(stats_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow([
                        'Text Input', 'Audio Input', 'Transcription Time',
                        'RAG Answer', 'RAG Response Time', 'RAG Status',
                        'AgentReact Answer', 'AgentReact Response Time', 'AgentReact Status', 'Date'
                    ])
                writer.writerow([
                    input_text, input_audio, transcription_time,
                    rag_answer, rag_time, rag_status,
                    agent_answer, agent_time, agent_status, today
                ])

    with tabs[1]:
        st.header("Conversation History")
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])
    
    # --- TAB 2: Estadísticas del chatbot ---
    with tabs[2]:
        st.header("Statistics")
        if os.path.exists(STATS_FILE):
            df = pd.read_csv(STATS_FILE)

            # Convert numeric columns safely
            for col_name in [
                'Transcription Time',
                'RAG Response Time',
                'AgentReact Response Time'
            ]:
                if col_name in df.columns:
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

            # KPIs
            st.subheader("Overview")
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.metric("Total Interactions", len(df))
            with kpi2:
                avg_transc = df['Transcription Time'].mean() if 'Transcription Time' in df.columns else None
                st.metric("Avg Transcription (s)", f"{avg_transc:.2f}" if avg_transc is not None and not pd.isna(avg_transc) else "—")
            with kpi3:
                avg_rag = df['RAG Response Time'].mean() if 'RAG Response Time' in df.columns else None
                st.metric("Avg RAG (s)", f"{avg_rag:.2f}" if avg_rag is not None and not pd.isna(avg_rag) else "—")

            kpi4, kpi5, _ = st.columns(3)
            with kpi4:
                avg_agent = df['AgentReact Response Time'].mean() if 'AgentReact Response Time' in df.columns else None
                st.metric("Avg AgentReact (s)", f"{avg_agent:.2f}" if avg_agent is not None and not pd.isna(avg_agent) else "—")
            with kpi5:
                st.metric("Today", df['Date'].eq(time.strftime('%d/%m/%Y')).sum() if 'Date' in df.columns else 0)

            # Two-column layout: left = time histograms, right = status pies
            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("Response Time Distributions")
                if 'RAG Response Time' in df.columns and df['RAG Response Time'].notna().any():
                    fig_rt, ax_rt = plt.subplots()
                    df['RAG Response Time'].dropna().plot(kind='hist', bins=15, ax=ax_rt, color='#1f77b4', alpha=0.8)
                    ax_rt.set_title('RAG Response Time (s)')
                    ax_rt.set_xlabel('Seconds')
                    ax_rt.grid(axis='y', linestyle='--', alpha=0.4)
                    st.pyplot(fig_rt)
                if 'AgentReact Response Time' in df.columns and df['AgentReact Response Time'].notna().any():
                    fig_at, ax_at = plt.subplots()
                    df['AgentReact Response Time'].dropna().plot(kind='hist', bins=15, ax=ax_at, color='#ff7f0e', alpha=0.8)
                    ax_at.set_title('AgentReact Response Time (s)')
                    ax_at.set_xlabel('Seconds')
                    ax_at.grid(axis='y', linestyle='--', alpha=0.4)
                    st.pyplot(fig_at)

            with col_right:
                st.subheader("Status Distribution")
                if 'RAG Status' in df.columns:
                    rag_counts = df['RAG Status'].value_counts()
                    if not rag_counts.empty:
                        fig_rs, ax_rs = plt.subplots()
                        colors = plt.cm.Set2(range(len(rag_counts)))
                        ax_rs.pie(rag_counts.values, labels=rag_counts.index, autopct='%1.1f%%', startangle=90, colors=colors)
                        ax_rs.set_title('RAG Status')
                        ax_rs.axis('equal')
                        st.pyplot(fig_rs)
                if 'AgentReact Status' in df.columns:
                    agent_counts = df['AgentReact Status'].value_counts()
                    if not agent_counts.empty:
                        fig_as, ax_as = plt.subplots()
                        colors = plt.cm.Set3(range(len(agent_counts)))
                        ax_as.pie(agent_counts.values, labels=agent_counts.index, autopct='%1.1f%%', startangle=90, colors=colors)
                        ax_as.set_title('AgentReact Status')
                        ax_as.axis('equal')
                        st.pyplot(fig_as)

            # Download and full table at the end
            st.subheader("All Interactions")
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
                for col in collections:
                    st.markdown(f"### Collection: {col.name}")
                    collection = client.get_collection(col.name)
                    docs = collection.get()
                    ids = docs.get("ids", [])
                    metadatas = docs.get("metadatas", [])
                    documents = docs.get("documents", [])
                    # --- Filtros ---
                    # Obtener lista de filenames únicos
                    filenames = []
                    for meta in metadatas:
                        if isinstance(meta, dict):
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
                    filenames = sorted(list(set(filenames)))
                    selected_filename = st.selectbox("Filter by document (filename)", ["All"] + filenames, key=f"filename_{col.name}")
                    keyword = st.text_input("Filter by keyword in chunk", value="", key=f"keyword_{col.name}")
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