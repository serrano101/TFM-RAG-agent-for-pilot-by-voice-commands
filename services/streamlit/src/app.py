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
from src.utils.interaction import query_services, manager_input, fetch_supported_languages, synthesize_tts 
from src.utils.cleaning import clean_rag_answer, format_clean_answer
import pandas as pd
import matplotlib.pyplot as plt
import json
import re
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
TTS_URL = os.environ.get("TTS_URL") or config.get("TTS_URL") or "http://tts:8000"

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
if not wait_ready("http://tts:8000", label="Inicializando TTS..."):
    st.stop()
# =====================
# 4. Lógica del Chatbot
# =====================
if menu == "Chatbot":
    tabs = st.tabs(["Chat", "History", "Statistics"])
    with tabs[0]:
        st.header("Interactive Chatbot")
        st.write("Type your query below. You will get responses from RAG.")

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
        # Si hay input (texto o audio transcrito), consultar RAG
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
            # Tras obtener resultados del RAG
            if results.get("rag_answer", ""):
                raw_answer = results.get("rag_answer", "")
                clean_dict = clean_rag_answer(raw_answer)
                pretty_text = format_clean_answer(clean_dict)
                # Opción de generar audio
                st.markdown("### Audio de la respuesta (TTS)")
                cache_key = f"tts_audio::{hash(pretty_text)}"
                if cache_key not in st.session_state:
                    audio_bytes, tts_time = synthesize_tts(pretty_text, TTS_URL, None)
                    st.session_state[cache_key] = {
                        "audio": audio_bytes,
                        "time": tts_time
                    }
                cached = st.session_state.get(cache_key, {})
                audio_bytes = cached.get("audio")
                tts_time = cached.get("time")
                st.session_state["last_tts_time"] = tts_time
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/wav")
                    if tts_time is not None:
                        st.info(f"TTS generation time: {tts_time:.2f} s", icon="⏱️")
                else:
                    st.info("No se pudo generar audio TTS.")
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
                'TTS Generation Time',  # nueva columna
                'Date'
            ]

            # Truncar TTS para persistencia
            tts_time_trunc = round(float(tts_time), 3) if tts_time is not None else None

            row = [
                input_text, input_audio, transcription_time,
                rag_status_code, rag_status, rag_error_message,
                rag_answer, rag_time,
                rag_context_size, rag_top_score, rag_avg_score,
                rag_top_page, rag_pages_serialized,
                tts_time_trunc,                # <- truncado
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

            # --- Normalización columnas numéricas ---
            num_cols_map = {
                'Transcription Time': 'ASR Time',
                'RAG Response Time': 'RAG Time',
                'TTS Generation Time': 'TTS Time'
            }
            for col in num_cols_map.keys():
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # --- Métricas base ---
            total_interactions = len(df)
            today_str = time.strftime('%d/%m/%Y')
            today_interactions = df['Date'].eq(today_str).sum() if 'Date' in df.columns else 0

            avg_asr = df['Transcription Time'].mean() if 'Transcription Time' in df.columns else None
            avg_rag = df['RAG Response Time'].mean() if 'RAG Response Time' in df.columns else None
            avg_tts = df['TTS Generation Time'].mean() if 'TTS Generation Time' in df.columns else None

            # --- Tema más repetido (se toma la cadena completa) ---
            most_text = None
            if 'Text Input' in df.columns and df['Text Input'].notna().any():
                most_text = df['Text Input'].value_counts().idxmax()

            most_audio = None
            if 'Audio Input' in df.columns and df['Audio Input'].notna().any():
                most_audio = df['Audio Input'].value_counts().idxmax()

            # --- Procedimientos más repetidos ---
            proc_counter = {}
            if 'RAG Answer' in df.columns:
                for raw in df['RAG Answer'].astype(str).tolist():
                    proc = None
                    # Intentar JSON
                    raw_strip = raw.strip()
                    if raw_strip.startswith("{") or raw_strip.startswith("["):
                        try:
                            obj = json.loads(raw_strip)
                            if isinstance(obj, dict) and 'procedure' in obj:
                                proc = obj.get('procedure')
                        except Exception:
                            pass
                    if not proc:
                        # Regex estilo "Procedure: LANDING"
                        m = re.search(r'(?i)procedure\s*[:\-]\s*([A-Za-z0-9 _\-\/]+)', raw)
                        if m:
                            proc = m.group(1).strip()
                    if proc:
                        proc_counter[proc] = proc_counter.get(proc, 0) + 1
            top_procs = sorted(proc_counter.items(), key=lambda x: x[1], reverse=True)[:10]

            # --- Clasificación status success / no_match ---
            status_col = df.get('RAG Status')
            status_counts = {}
            if status_col is not None:
                # Normalizamos no_match
                def norm_status(s):
                    if isinstance(s, str):
                        s_low = s.lower().strip()
                        if 'no_match' in s_low or 'not_match' in s_low or 'not match' in s_low:
                            return 'no_match'
                        if 'success' in s_low:
                            return 'success'
                    return s
                norm_statuses = status_col.apply(norm_status)
                status_counts = norm_statuses.value_counts(dropna=False)

            # --- Páginas (hist) ---
            page_freq = {}
            if 'RAG Pages' in df.columns:
                for entry in df['RAG Pages'].dropna().astype(str):
                    for p in entry.split(';'):
                        p_clean = p.strip()
                        if not p_clean:
                            continue
                        page_freq[p_clean] = page_freq.get(p_clean, 0) + 1
            pages_items = sorted(page_freq.items(), key=lambda x: (pd.to_numeric(x[0], errors='coerce'), x[0]))

            # =============== LAYOUT ===============
            st.subheader("KPI Overview")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Total Interactions", total_interactions)
            with c2:
                st.metric("Interactions Today", today_interactions)
            with c3:
                st.metric("Avg RAG (s)", f"{avg_rag:.2f}" if avg_rag is not None and not pd.isna(avg_rag) else "—")
            with c4:
                st.metric("Avg TTS (s)", f"{avg_tts:.2f}" if avg_tts is not None and not pd.isna(avg_tts) else "—")
            with c5:
                st.metric("Avg ASR (s)", f"{avg_asr:.2f}" if avg_asr is not None and not pd.isna(avg_asr) else "—")

            st.markdown("### Most Frequent Themes")
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.write("Most repeated Text Input:")
                st.code(most_text or "—", language="text")
            with col_t2:
                st.write("Most repeated Audio Input:")
                st.code(most_audio or "—", language="text")
            with col_t3:
                if top_procs:
                    st.write("Top Procedures:")
                    for p, cnt in top_procs:
                        st.markdown(f"- {p} ({cnt})")
                else:
                    st.write("No procedures detected.")

            st.markdown("---")
            col_pie, col_pages = st.columns([1,1])

            # Pie chart status (success vs no_match vs otros)
            with col_pie:
                st.markdown("#### Status Distribution (success vs no_match)")
                if not status_counts.empty:
                    # Map unify
                    labels = []
                    values = []
                    for k, v in status_counts.items():
                        label = k if k in ('success', 'no_match') else 'other'
                        labels.append(label)
                        values.append(v)
                    # Aggregate duplicates (success / no_match / other)
                    agg = {}
                    for l, val in zip(labels, values):
                        agg[l] = agg.get(l, 0) + val
                    fig_status, ax_status = plt.subplots(figsize=(4, 4))
                    ax_status.pie(agg.values(), labels=agg.keys(), autopct='%1.1f%%', startangle=90,
                                  colors=['#2ca02c', '#d62728', '#7f7f7f'][:len(agg)])
                    ax_status.axis('equal')
                    st.pyplot(fig_status)
                else:
                    st.info("No status data.")

            # Histograma (en realidad bar) de páginas
            with col_pages:
                st.markdown("#### Page Query Frequency")
                if pages_items:
                    pages_df = pd.DataFrame(pages_items, columns=['Page', 'Count'])
                    fig_pages, ax_pages = plt.subplots(figsize=(5, 4))
                    ax_pages.bar(pages_df['Page'].astype(str), pages_df['Count'], color='#1f77b4')
                    ax_pages.set_xlabel("Page")
                    ax_pages.set_ylabel("Frequency")
                    ax_pages.grid(axis='y', linestyle='--', alpha=0.5)
                    plt.xticks(rotation=45, ha='right')
                    st.pyplot(fig_pages)
                else:
                    st.info("No pages data.")

            st.markdown("---")
            col1, col2 = st.columns([1,1])
            with col1:
                st.markdown("### Boxplots of Response Times (RAG / TTS / ASR)")
                time_data = []
                time_labels = []
                
                if 'RAG Response Time' in df.columns and df['RAG Response Time'].notna().any():
                    time_data.append(df['RAG Response Time'].dropna().tolist())
                    time_labels.append("RAG")
                if 'TTS Generation Time' in df.columns and df['TTS Generation Time'].notna().any():
                    time_data.append(df['TTS Generation Time'].dropna().tolist())
                    time_labels.append("TTS")
                if 'Transcription Time' in df.columns and df['Transcription Time'].notna().any():
                    time_data.append(df['Transcription Time'].dropna().tolist())
                    time_labels.append("ASR")

                if time_data:
                    fig_box_all, ax_box_all = plt.subplots(figsize=(6,4))
                    ax_box_all.boxplot(time_data, labels=time_labels, patch_artist=True,
                                    boxprops=dict(facecolor="#cfe2f3", color="#1f77b4"),
                                    medianprops=dict(color="#d62728"),
                                    whiskerprops=dict(color="#1f77b4"),
                                    capprops=dict(color="#1f77b4"))
                    ax_box_all.set_ylabel("Time (s)")
                    ax_box_all.grid(axis='y', linestyle='--', alpha=0.4)
                    st.pyplot(fig_box_all)
                else:
                    st.info("No time data for boxplots.")
            with col2:
                st.markdown("### RAG Time by Status (success vs no_match)")
                if 'RAG Response Time' in df.columns and 'RAG Status' in df.columns:
                    norm_status_series = df['RAG Status'].astype(str).str.lower()
                    mask_success = norm_status_series.str.contains("success")
                    mask_nomatch = norm_status_series.str.contains("no_match") | norm_status_series.str.contains("not match") | norm_status_series.str.contains("not_match")
                    data_box2 = []
                    labels_box2 = []
                    if mask_success.any():
                        data_box2.append(df.loc[mask_success, 'RAG Response Time'].dropna().tolist())
                        labels_box2.append("success")
                    if mask_nomatch.any():
                        data_box2.append(df.loc[mask_nomatch, 'RAG Response Time'].dropna().tolist())
                        labels_box2.append("no_match")
                    if data_box2:
                        fig_box2, ax_box2 = plt.subplots(figsize=(5,4))
                        ax_box2.boxplot(data_box2, labels=labels_box2, patch_artist=True,
                                        boxprops=dict(facecolor="#e0d4f7", color="#6a3d9a"),
                                        medianprops=dict(color="#ff7f0e"),
                                        whiskerprops=dict(color="#6a3d9a"),
                                        capprops=dict(color="#6a3d9a"))
                        ax_box2.set_ylabel("RAG Time (s)")
                        ax_box2.grid(axis='y', linestyle='--', alpha=0.4)
                        st.pyplot(fig_box2)
                    else:
                        st.info("No success/no_match data for RAG boxplot.")
                else:
                    st.info("Missing columns for RAG status boxplot.")

            st.markdown("### RAG Time vs Top Score (Scatter)")
            if {'RAG Response Time', 'RAG Top Score', 'RAG Status'}.issubset(df.columns):
                mask_scatter = df['RAG Response Time'].notna() & df['RAG Top Score'].notna()
                if mask_scatter.any():
                    fig_sc, ax_sc = plt.subplots(figsize=(6,4))
                    norm_status_series = df['RAG Status'].astype(str).str.lower()
                    colors = []
                    for s in norm_status_series[mask_scatter]:
                        if 'success' in s:
                            colors.append('#2ca02c')
                        elif 'no_match' in s or 'not match' in s or 'not_match' in s:
                            colors.append('#d62728')
                        else:
                            colors.append('#7f7f7f')
                    x_vals = df.loc[mask_scatter, 'RAG Response Time']
                    y_vals = df.loc[mask_scatter, 'RAG Top Score']
                    ax_sc.scatter(x_vals, y_vals, c=colors, alpha=0.75, edgecolor='k', linewidth=0.4)
                    ax_sc.set_xlabel("RAG Response Time (s)")
                    ax_sc.set_ylabel("Top Score")
                    ax_sc.grid(axis='both', linestyle='--', alpha=0.4)
                    # Etiquetas (limitamos a 40 puntos para no saturar)
                    max_labels = 40
                    label_indices = x_vals.index[:max_labels]
                    for idx in label_indices:
                        txt_short = str(df.loc[idx, 'Text Input'])[:18] + ("..." if len(str(df.loc[idx, 'Text Input'])) > 18 else "")
                        ax_sc.annotate(txt_short, (df.loc[idx, 'RAG Response Time'], df.loc[idx, 'RAG Top Score']),
                                       textcoords="offset points", xytext=(4,4), fontsize=7, alpha=0.8)
                    legend_handles = [
                        plt.Line2D([0],[0], marker='o', color='w', label='success', markerfacecolor='#2ca02c', markersize=8),
                        plt.Line2D([0],[0], marker='o', color='w', label='no_match', markerfacecolor='#d62728', markersize=8),
                        plt.Line2D([0],[0], marker='o', color='w', label='other', markerfacecolor='#7f7f7f', markersize=8),
                    ]
                    ax_sc.legend(handles=legend_handles, title="Status", loc='best')
                    st.pyplot(fig_sc)
                else:
                    st.info("Insufficient data for scatter.")
            else:
                st.info("Missing columns for RAG scatter plot.")

            st.markdown("---")
            st.markdown("### All Interactions (raw CSV)")
            preferred_order = [
                'Date',
                'Text Input', 'Audio Input', 'Transcription Time',
                'RAG Status Code', 'RAG Status', 'RAG Error Message',
                'RAG Answer', 'RAG Response Time',
                'RAG Context Size', 'RAG Top Score', 'RAG Avg Score',
                'RAG Top Page', 'RAG Pages',
                'TTS Generation Time'
            ]
            cols_existing = [c for c in preferred_order if c in df.columns]
            cols_remaining = [c for c in df.columns if c not in cols_existing]
            df_display = df[cols_existing + cols_remaining]
            st.dataframe(df_display, width='stretch')

            csv_bytes = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name="statistics.csv",
                mime="text/csv",
                width='stretch'
            )
        else:
            st.info("No statistics data yet.")
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