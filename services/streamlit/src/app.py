# =====================
# 1. Cargar configuración y logging
# =====================
from datetime import datetime
from urllib.parse import urlparse
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
menu = st.sidebar.radio("Navegación", ["Chatbot", "Base de Datos Vectorial"])

# =====================
# 4. Lógica del Chatbot
# =====================
if menu == "Chatbot":
    tabs = st.tabs(["Chat", "Historial"])
    with tabs[0]:
        st.header("Chatbot Interactivo")
        st.write("Escribe tu consulta abajo. Obtendrás respuesta de RAG y Agent React en paralelo.")

        def _query_services(user_input:str):
            col_rag, col_agent = st.columns(2)
            rag_placeholder = col_rag.empty()
            agent_placeholder = col_agent.empty()
            queue = Queue()
            def fetch_rag_async(user_input, queue):
                try:
                    logger.info(f"Enviando consulta a RAG: {user_input}")
                    response_rag = requests.post(RAG_URL, json={"transcription": user_input}, timeout=300)
                    response_rag.raise_for_status()
                    rag_json = response_rag.json()
                    status = rag_json.get("status", "")
                    resp = rag_json.get("response", {})
                    queue.put(("rag", resp, status, None))
                except Exception as e:
                    queue.put(("rag", None, None, str(e)))
            def fetch_agent_async(user_input, queue):
                try:
                    logger.info(f"Enviando consulta a Agent React: {user_input}")
                    response_agent = requests.post(AGENT_REACT_URL, json={"transcription": user_input}, timeout=300)
                    response_agent.raise_for_status()
                    agent_json = response_agent.json()
                    status = agent_json.get("status", "")
                    resp = agent_json.get("response", {})
                    queue.put(("agent", resp, status, None))
                except Exception as e:
                    queue.put(("agent", None, None, str(e)))
            thread_rag = threading.Thread(target=fetch_rag_async, args=(user_input, queue))
            thread_agent = threading.Thread(target=fetch_agent_async, args=(user_input, queue))
            thread_rag.start()
            thread_agent.start()
            shown = {"rag": False, "agent": False}
            results = {"rag": None, "agent": None}
            errors = {"rag": None, "agent": None}
            statuses = {"rag": None, "agent": None}
            # Mostrar título y spinner inicial en ambos
            with rag_placeholder.container():
                st.subheader("RAG")
                st.info("Esperando respuesta de RAG...")
            with agent_placeholder.container():
                st.subheader("Agent React")
                st.info("Esperando respuesta de Agent React...")
            for _ in range(2):
                who, resp, status, error = queue.get()
                results[who] = resp
                errors[who] = error
                statuses[who] = status
                shown[who] = True
                # Actualizar el chat_history con la respuesta real
                if who == "rag":
                    rag_placeholder.empty()
                    with rag_placeholder.container():
                        st.subheader("RAG")
                        if error:
                            st.error(error)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] Error: {error}"})
                        else:
                            st.chat_message("assistant").write(resp.get("answer", "") if resp else "")
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[RAG] {resp.get('answer', '') if resp else ''}"})
                            with st.expander("Detalles RAG", expanded=False):
                                st.markdown(f"**Status:** {status}")
                                st.markdown(f"**Input:** {resp.get('input', '') if resp else ''}")
                                st.markdown(f"**Contexto:** {resp.get('context', '') if resp else ''}")
                elif who == "agent":
                    agent_placeholder.empty()
                    with agent_placeholder.container():
                        st.subheader("Agent React")
                        if error:
                            st.error(error)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent React] Error: {error}"})
                        else:
                            st.chat_message("assistant").write(resp.get("output", "") if resp else "")
                            st.session_state.chat_history.append({"role": "assistant", "content": f"[Agent React] {resp.get('output', '') if resp else ''}"})
                            with st.expander("Detalles Agent React", expanded=False):
                                st.markdown(f"**Status:** {status}")
                                st.markdown(f"**Input:** {resp.get('input', '') if resp else ''}")

        def _transcribe_audio(
            audio_name: str = "default_audio", 
            audio_file: UploadFile = File(...),
            audio_type: str = "audio/wav"
        ) -> str:
            try:
                with st.spinner("Transcribiendo audio..."):
                    logger.info("Enviando audio a ASR para transcripción")
                    files = {"file": (audio_name, audio_file, audio_type)}
                    response = requests.post(ASR_URL, files=files, timeout=300)
                    response.raise_for_status()
                    transcribed = response.json().get("transcription")
                    st.chat_message("user").write(f"[Audio]: {transcribed}")
                    st.session_state.chat_history.append({"role": "user", "content": f"[Audio]: {transcribed}"})               
                    logger.info(f"Transcripción recibida: {transcribed}")
                    return transcribed
            except Exception as e:
                st.error(f"Error en la transcripción de audio: {e}")

        # Inicializar historial de chat en la sesión si no existe
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Input y audio en dos columnas, input más grande y audio bien visible
        col_input, col_audio = st.columns([4, 1])
        with col_input:
            user_input = st.chat_input(
                "Escribe tu consulta...",
                accept_file=True,
                file_type=["wav", "mp3"],
            )
        with col_audio:
            recorded_audio = st.audio_input(
                label="Grabar audio",
                help="Graba tu consulta por voz",
                label_visibility="visible",
                width=180
            )
            logger.info(f"recorded_audio: {recorded_audio}")
        # Procesar entrada del usuario (texto y/o audio)
        text_input = None
        # Si el usuario envía solo texto
        if user_input and user_input["text"] and not user_input["files"]:
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
            _query_services(user_input=text_input)
        # Mostrar historial de mensajes
        # for msg in st.session_state.chat_history:
        #     st.chat_message(msg["role"]).write(msg["content"])

    with tabs[1]:
        st.header("Historial de la conversación")
        for msg in st.session_state.chat_history:
            st.chat_message(msg["role"]).write(msg["content"])


# =====================
# 5. Visualización de la base de datos vectorial
# =====================
elif menu == "Base de Datos Vectorial":
    st.header("Base de Datos Vectorial (ChromaDB)")
    tabs = st.tabs(["Estadísticas", "Chunks"])
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
                st.markdown("## Estadísticas de la Base de Datos Vectorial")
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
                st.markdown(f"**Total de colecciones:** {len(col_names)}")
                st.markdown(f"**Colecciones:** {', '.join(col_names)}")
                st.markdown(f"**Total de chunks:** {total_chunks}")
                st.markdown(f"**Total de documentos únicos:** {len(doc_filenames)}")
                # Chunks por documento - dos gráficos en la misma fila
                if doc_filenames:
                    df_chunks = pd.DataFrame(list(doc_filenames.items()), columns=["Documento", "Chunks"])
                    st.markdown("### Chunks por documento:")
                    col_bar, col_pie = st.columns(2)
                    with col_bar:
                        fig_bar, ax_bar = plt.subplots()
                        df_chunks.plot(kind='bar', x='Documento', y='Chunks', ax=ax_bar, legend=False, color='#1f77b4')
                        ax_bar.set_ylabel('Chunks')
                        ax_bar.set_title('Chunks por Documento')
                        ax_bar.grid(axis='y', linestyle='--', alpha=0.5)
                        plt.xticks(rotation=45, ha='right')
                        st.pyplot(fig_bar)
                    with col_pie:
                        fig_pie, ax_pie = plt.subplots()
                        colors = plt.cm.Paired(range(len(df_chunks)))
                        ax_pie.pie(df_chunks["Chunks"], labels=df_chunks["Documento"], autopct='%1.1f%%', startangle=90, colors=colors)
                        ax_pie.set_title('Distribución de Chunks por Documento')
                        ax_pie.axis('equal')
                        st.pyplot(fig_pie)
            # --- TAB 2: Chunks ---
            with tabs[1]:
                for col in collections:
                    st.markdown(f"### Colección: {col.name}")
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
                    selected_filename = st.selectbox("Filtrar por documento (filename)", ["Todos"] + filenames, key=f"filename_{col.name}")
                    keyword = st.text_input("Filtrar por palabra clave en chunk", value="", key=f"keyword_{col.name}")
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
                        if selected_filename != "Todos" and filename != selected_filename:
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
                                        with st.expander("Metadatos", expanded=False):
                                            for k, v in sorted_meta.items():
                                                st.markdown(f"- **{k}:** {v}")
                                    else:
                                        st.markdown(f"**Metadatos:** {meta}")
                                    st.markdown("---")
    except Exception as e:
        logger.exception(f"Error consultando ChromaDB: {e}")
        st.error(f"Error consultando ChromaDB: {e}")