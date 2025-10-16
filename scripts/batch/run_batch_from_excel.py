"""
- Crear carpeta para scripts si no existe: mkdir -p scripts/batch
- Ejecutar con tu venv activo y servicios levantados: python3 scripts/batch/run_batch_from_excel.py --excel scripts/batch/casos.xlsx --out scripts/batch/resultados.csv  --audio-dir scripts/batch/generated_audios
- Opcional: fijar endpoints por env si no usas config.yaml:
    ASR_URL=http://localhost:8001/transcribe
    RAG_URL=http://localhost:8002/rag_result
    TTS_URL=http://localhost:8003
    python3 scripts/batch/run_batch_from_excel.py --excel casos.xlsx --out out.csv
"""

import argparse
import base64
import os
import sys
import time
import json
import re
import logging
import requests
import pandas as pd
from datetime import datetime
from statistics import mean
from urllib.parse import urlparse
from typing import List, Union, Dict, Any
# jiwer para WER
try:
    import jiwer
    JIWER_TRANSFORM = jiwer.Compose([
        jiwer.ExpandCommonEnglishContractions(),
        jiwer.RemoveEmptyStrings(),
        jiwer.ToLowerCase(),
        jiwer.RemoveMultipleSpaces(),
        jiwer.Strip(),
        jiwer.RemovePunctuation(),
        jiwer.ReduceToListOfListOfWords(),
    ])
except Exception:
    JIWER_TRANSFORM = None

# Permitir importar utils existentes (src.utils.*) sin modificar tu app
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_PATH = os.path.join(PROJECT_ROOT, "services", "streamlit", "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

AUDIOS_TTS_DIR = "scripts/batch/tts_audios" 
from cleaning import clean_rag_answer, format_clean_answer
# Imports opcionales de tus utilidades. Si no existen, se hace fallback a llamadas directas.
try:
    from src.utils.interaction import query_services
except Exception:
    query_services = None
    synthesize_tts = None

logger = logging.getLogger("batch_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
def format_rag_answer(rag_answer: dict) -> str:
    """
    Formatea el contenido de rag_answer como una cadena de texto para mostrar en un mensaje de chat.

    Args:
        rag_answer (dict): Respuesta del RAG con las claves "procedure", "conditions", "steps", y "notes".

    Returns:
        str: Cadena formateada con las claves en negrita y los valores en texto normal.
    """
    if not rag_answer:
        return "No hay respuesta para mostrar."

    formatted_answer = []
    for key, value in rag_answer.items():
        # Agregar la clave en negrita
        formatted_answer.append(f"**{key.capitalize()}:**")

        # Si el valor es una lista, numerar los elementos
        if isinstance(value, list):
            if value:  # Si la lista no está vacía
                if len(value) == 1:  # Si solo hay un elemento, no numerarlo
                    formatted_answer.append(value[0])
                else:  # Numerar los elementos si hay más de uno
                    for i, item in enumerate(value, start=1):
                        formatted_answer.append(f"{i}. {item}")
            else:
                formatted_answer.append("_No data available_")  # Mostrar mensaje si la lista está vacía
        # Si el valor es un string o está vacío
        elif isinstance(value, str):
            if value.strip():  # Si el string no está vacío
                formatted_answer.append(value)
            else:
                formatted_answer.append("_No data available_")  # Mostrar mensaje si el string está vacío
        else:
            formatted_answer.append("_Unsupported data type_")  # Manejar otros tipos de datos

    # Unir las líneas con saltos de línea
    return "\n\n".join(formatted_answer)
# -------------------------
# Config / endpoints
# -------------------------
def load_config(project_root: str):
    # Intenta leer config.yaml del repo (no la de /app del contenedor)
    cfg_path = os.path.join(project_root, "config.yaml")
    conf = {}
    if os.path.exists(cfg_path):
        try:
            import yaml
            with open(cfg_path, "r", encoding="utf-8") as f:
                conf = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"No se pudo leer config.yaml: {e}")
    return conf

def resolve_endpoints(conf: dict):
    ASR_URL = conf.get("ASR", {}).get("TRANSCRIPTION_URL", "http://asr:8000/transcribe")
    RAG_URL = conf.get("RAG", {}).get("WEBHOOK_RAG_URL", "http://rag:8000/rag_result")
    TTS_URL = os.environ.get("TTS_URL") or conf.get("TTS_URL") or "http://tts:8000"

    # Permitir override por env
    ASR_URL = os.environ.get("ASR_URL", ASR_URL)
    RAG_URL = os.environ.get("RAG_URL", RAG_URL)
    TTS_URL = os.environ.get("TTS_URL", TTS_URL)
    return ASR_URL, RAG_URL, TTS_URL
session_state = {}
def wait_ready(base_url: str, timeout: int = 300) -> bool:
    base = base_url.rstrip("/")
    key = f"warmup_sent::{base}"
    if key not in session_state:
        session_state[key] = False

    start = time.time()
    while time.time() - start < timeout:
        try:
            if not session_state[key]:
                logger.info(f"[INIT] warmup -> {base}/warmup")
                requests.post(f"{base}/warmup", timeout=timeout)
                session_state[key] = True
            r = requests.get(f"{base}/readyz", timeout=timeout)
            if r.ok and r.json().get("ready"):
                logger.info(f"[INIT] {base} listo")
                return True
        except Exception as ex:
            logger.warning(f"[INIT] error contactando {base}: {ex}")
        time.sleep(1.5)
    logger.error(f"Timeout inicializando {base}")
    return False

# -------------------------
# Métricas
# -------------------------
def normalize_text(s: str) -> list:
    import re
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9áéíóúüñ'\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.split()

def compute_wer(ref: str, hyp: str) -> float:
    # Usar jiwer con transformaciones similares a normalize_text
    try:
        wer = jiwer.wer(
                ref,
                hyp,
                reference_transform=JIWER_TRANSFORM,
                hypothesis_transform=JIWER_TRANSFORM,
            )
        logger.info(f"Computed WER: {wer} for ref='{ref}' | hyp='{hyp}'")
        return float(wer)
    except TypeError as e:
        logger.warning(f"Error de tipo en compute_wer: {e}")
        # Compatibilidad con versiones antiguas de jiwer sin transforms
        return None

# -------------------------
# ASR / RAG / TTS fallbacks
# -------------------------
def call_asr(asr_url: str, audio_path: str, language: str | None = None, timeout: int = 120):
    # Espera que el microservicio reciba multipart 'file' y devuelva JSON con {text, time}
    files = {"file": open(audio_path, "rb")}
    data = {"language": language} if language else None
    start_transcription = time.time()
    response = requests.post(asr_url, files=files, data=data, timeout=timeout)
    end_transcription = time.time()
    transcription_time = end_transcription - start_transcription
    response_data = response.json()
    status_code = response.status_code
    if status_code != 200:
        error_message = response_data.get("message", "unknown error")
        logger.error(f"Error en transcripción de audio: {error_message}")
        return None
    logger.info(f"Transcripción recibida: {response_data.get('transcription', '')}")
    return response_data.get('transcription', ''), transcription_time

def call_rag_direct(rag_url: str, text: str, timeout: int = 120):
    # Fallback simple si no podemos importar query_services
    payload = {"transcription": text}
    start_rag = time.time()
    r = requests.post(rag_url, json=payload, timeout=timeout)
    end_rag = time.time()
    time_response = end_rag - start_rag
    status_code = r.status_code
    rag_json = r.json()
    if status_code == 200:                
        status = rag_json.get("status", "success")
        error_message = None
        resp = rag_json.get("response", {})
    else:
        status = rag_json.get("status", "unknown_error")
        error_message = rag_json.get("message", f"HTTP {status_code}")
        resp = rag_json.get("response", None)
    # Espera JSON con {answer, context, status...}. Adaptamos a la estructura usada en tu app.
    out = {
        "rag_status_code": status_code,
        "rag_status": status,
        "rag_error_message": error_message,
        "rag_answer": resp.get("answer", "") if resp else "",
        "rag_context": resp.get("context", []) if resp else [],
        "rag_time": time_response,
    }
    return out

def call_tts_direct(tts_url: str, text: str, timeout: int = 120):
    # Envía texto al servicio TTS y devuelve (audio_bytes|None, elapsed_s)
    payload = {"text": text, "speaker": "p245", "raw_wav": False}
    t0 = time.time()
    r = requests.post(f"{tts_url.rstrip('/')}/synthesize", json=payload, timeout=timeout)
    elapsed = time.time() - t0

    if r.status_code != 200:
        try:
            msg = r.text[:200]
        except Exception:
            msg = "unknown"
        logger.warning(f"TTS fallo status={r.status_code}: {msg}")
        return None, elapsed

    ct = (r.headers.get("content-type") or "").lower()

    # Si devuelve audio directamente
    if "audio/" in ct:
        return r.content, elapsed

    # Si devuelve JSON, intenta localizar una cadena base64
    audio_bytes = None
    try:
        data = r.json()
        # Posibles claves con base64
        b64audio = None
        for k in ("audio_base64", "wav_base64", "audio", "wav", "data"):
            v = data.get(k)
            if isinstance(v, str) and len(v) > 0:
                b64audio = v
                break
        if b64audio:
            try:
                audio_bytes = base64.b64decode(b64audio)
            except Exception as e:
                logger.warning(f"TTS: no se pudo decodificar base64: {e}")
                audio_bytes = None
        else:
            # No hay base64; algunos servicios devuelven ruta o metadatos
            audio_bytes = None
    except Exception:
        # No es JSON; devolver None con tiempo
        audio_bytes = None

    return audio_bytes, elapsed

# -------------------------
# Lectura columnas
# -------------------------
EXPECTED_OUTPUT_COLUMNS = [
    "Input Type (Text, audio, text+audio)",
    "Expected Text",
    "Expected Text Audio",
    "Level (N1,N2,N3)",
    "¿Expected answer? (Yes/No)",
    "Date",
    "Text Input",
    "Transcribed Audio Text",
    "ASR time",
    "WER",
    "RAG Answer",
    "Procedure",
    "RAG Status",
    "RAG Error Menssage",
    "¿Answer Correct?(Yes/No)",
    "RAG Time",
    "RAG Avg Score",
    "RAG Pages",
    "TTS Time",
    "Total time",
]

def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.strip(): c for c in df.columns}
    lower_map = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand in cols:
            return cols[cand]
        if cand.lower().strip() in lower_map:
            return lower_map[cand.lower().strip()]
    return None

# -------------------------
# Lógica principal
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Batch runner from Excel to CSV")
    parser.add_argument("--excel", required=True, help="Ruta del Excel de entrada")
    parser.add_argument("--out", required=True, help="Ruta del CSV de salida")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout por servicio (s)")
    parser.add_argument("--language", default=None, help="Idioma forzado para ASR (opcional)")
    # NUEVO: cómo localizar audios
    parser.add_argument("--audio-dir", default="scripts/batch/generated_audios", help="Carpeta base donde están los .wav")
    parser.add_argument("--audio-col", default=None, help="Nombre de columna que contiene ID o filename del audio (opcional)")
    parser.add_argument("--audio-suffix", default=".wav", help="Sufijo/extension para construir el filename si la col es un ID")
    parser.add_argument("--audio-pattern", default="{id}.wav", help="Patrón para construir el filename a partir de un ID")
    args = parser.parse_args()

    conf = load_config(PROJECT_ROOT)
    # Endpoints para host (fuera de Docker); sobreescribibles por ENV
    ASR_URL_BASE = os.environ.get("ASR_URL", "http://localhost:8001")
    RAG_URL_BASE = os.environ.get("RAG_URL", "http://localhost:8002")
    TTS_URL = os.environ.get("TTS_URL", "http://localhost:5003")
    logger.info(f"ASR_URL={ASR_URL_BASE} | RAG_URL={RAG_URL_BASE} | TTS_URL={TTS_URL}")

    # Comprobar disponibilidad de servicios
    for name, url in [("ASR", ASR_URL_BASE), ("RAG", RAG_URL_BASE), ("TTS", TTS_URL)]:
        ok = wait_ready(url, timeout=60)
        logger.info(f"{name} at {url} ready: {ok}")
        if not ok:
            logger.warning(f"[WARN] {name} no confirmó ready en {url}. Se intentará igualmente.")
    ASR_URL = os.environ.get("ASR_URL", "http://localhost:8001/transcribe")
    RAG_URL = os.environ.get("RAG_URL", "http://localhost:8002/rag_result")
    # Leer Excel
    df_in = pd.read_excel(args.excel)
    base_dir = os.path.dirname(os.path.abspath(args.excel))

    # Columnas de entrada
    col_input_type = find_col(df_in, ["Input Type (Text, audio, text+audio)", "Input Type"])
    col_expected_text = find_col(df_in, ["Expected Text", "ExpectedText", "Text"])
    # Texto de referencia del audio
    col_audio_ref_text = find_col(df_in, ["Expected Text Audio", "Audio Expected Text", "Audio Reference Text"])
    col_level = find_col(df_in, ["Level (N1,N2,N3)", "Level"])
    col_expected_answer = find_col(df_in, ["¿Expected answer? (Yes/No)", "Expected answer", "Expected Answer"])

    # Opcionales para localizar audio
    col_audio_path = find_col(df_in, ["Audio", "Audio Path", "Audio File", "Audio Filename", "AudioName"])
    col_audio_id = args.audio_col or find_col(df_in, ["ID", "id", "Audio ID", "AudioId", "Case ID", "case_id"])

    missing = []
    for nm, var in [("Input Type", col_input_type), ("Expected Text", col_expected_text), ("Expected Text, Audio", col_audio_ref_text), ("Level", col_level), ("¿Expected answer?", col_expected_answer)]:
        if var is None:
            missing.append(nm)
    if missing:
        logger.error(f"Faltan columnas requeridas en el Excel: {missing}")
        sys.exit(1)

    out_rows = []
    today_str = datetime.now().strftime("%d/%m/%Y")

    for idx, row in df_in.iterrows():
        input_type = str(row.get(col_input_type, "") or "").strip().lower()
        expected_text = str(row.get(col_expected_text, "") or "").strip()
        expected_text_audio = str(row.get(col_audio_ref_text, "") or "").strip()

        # Determinar ruta del audio (no viene en el Excel)
        audio_path = None
        audio_path_cell = row.get(col_audio_path) if col_audio_path else None
        if isinstance(audio_path_cell, str) and audio_path_cell.strip():
            # Si el Excel trae una ruta/filename opcional, úsala
            ap = audio_path_cell.strip()
            if not os.path.isabs(ap):
                # Preferir base_dir si es una ruta relativa válida, si no, audio-dir
                ap_base = os.path.join(base_dir, ap)
                ap_dir = os.path.join(args.audio_dir, ap)
                ap = ap_base if os.path.exists(ap_base) else ap_dir
            audio_path = ap
        else:
            # Si no hay ruta explícita, construimos con un ID/filename desde col_audio_id
            id_val = None
            if col_audio_id:
                id_raw = row.get(col_audio_id, "")
                if not pd.isna(id_raw):
                    id_val = str(id_raw).strip()
            if id_val:
                # Si el valor ya parece filename con extensión, úsalo tal cual dentro de audio-dir
                if os.path.splitext(id_val)[1]:
                    audio_path = os.path.join(args.audio_dir, id_val)
                else:
                    filename = args.audio_pattern.format(id=id_val)
                    audio_path = os.path.join(args.audio_dir, filename)

        level = str(row.get(col_level, "") or "").strip()
        expected_answer_flag = str(row.get(col_expected_answer, "") or "").strip()

        text_input = ""
        transcribed_text = ""
        asr_time = None
        wer_val = None
        rag_answer = ""
        rag_status = ""
        rag_error = None
        rag_time = None
        rag_avg_score = None
        rag_avg_pages = None
        tts_time = None

        total_t0 = time.time()

        # 1) ASR si procede
        if input_type in ("audio", "audio + text"):
            if not audio_path or not os.path.exists(audio_path):
                rag_status = "error"
                rag_error = f"Audio file not found: {audio_path}"
                logger.warning(rag_error)
            else:
                try:
                    transcribed_text, asr_time = call_asr(ASR_URL, audio_path, language="en", timeout=args.timeout)
                except Exception as ex:
                    rag_status = "error"
                    rag_error = f"ASR failed: {ex}"

        # 2) Texto para RAG y para el CSV
        rag_query = ""
        if input_type == "text":
            text_input = expected_text
            rag_query = expected_text
        elif input_type == "audio":
            text_input = ""                # <- no rellenar Text Input para audio
            rag_query = transcribed_text   # <- RAG usa la transcripción
            # 3) WER entre subtítulo del audio y transcripción del ASR
            try:
                wer_val = compute_wer(expected_text_audio, transcribed_text)
            except Exception as e:
                wer_val = None
                logger.warning(f"Error en compute_wer: {e}")
        elif input_type == "audio + text":
            text_input = expected_text
            rag_query = transcribed_text + expected_text
            # 3) WER entre subtítulo del audio y transcripción del ASR
            try:
                wer_val = compute_wer(expected_text_audio, transcribed_text)
            except Exception as e:
                wer_val = None
                logger.warning(f"Error en compute_wer: {e}")
        else:
            text_input = ""                # desconocido: no llenar Text Input
            rag_query = expected_text or transcribed_text

        # 4) Llamada a RAG
        if rag_query:
            try:
                if query_services:
                    results = query_services(
                        rag_query,
                        rag_url=RAG_URL,
                        rag_timeout=args.timeout,
                        output_not_match_answer_context="The question does not match with the context provided."
                    )
                else:
                    results = call_rag_direct(RAG_URL, rag_query, timeout=args.timeout)

                rag_answer = results.get("rag_answer", "") or results.get("answer", "") or ""
                rag_status = results.get("rag_status", "") or results.get("status", "")
                rag_error = results.get("rag_error_message", None) or results.get("error", None)
                rag_time = results.get("rag_time", None)

                # Scores y páginas
                ctx = results.get("rag_context") or []
                scores = []
                pages = []
                for it in ctx:
                    if not isinstance(it, dict):
                        continue
                    sc = it.get("score")
                    if sc is not None:
                        try:
                            scores.append(float(sc))
                        except Exception:
                            pass
                    pg = it.get("page_number")
                    if pg is not None:
                        try:
                            pages.append(float(pg))
                        except Exception:
                            pass
                rag_avg_score = round(mean(scores), 4) if scores else None
                rag_pages = pages if pages else None

            except Exception as ex:
                rag_status = "error"
                rag_error = f"RAG failed: {ex}"

        # 5) Extraer procedure del answer cuando sea posible
        procedure = None
        try:
            # 5.1) Si la respuesta ya es un dict estructurado
            if isinstance(rag_answer, dict):
                procedure = (
                    rag_answer.get("procedure")
                    or rag_answer.get("title")
                    or rag_answer.get("Procedure")
                )
                if not procedure:
                    steps = rag_answer.get("steps")
                    if isinstance(steps, list) and steps:
                        first = str(steps[0]).strip()
                        if 1 <= len(first.split()) <= 8:
                            procedure = first

            # 5.2) Normalizar con nuestro limpiador universal
            if not procedure:
                raw_text = (
                    rag_answer
                    if isinstance(rag_answer, str)
                    else json.dumps(rag_answer, ensure_ascii=False)
                )
                cleaned = clean_rag_answer(raw_text or "")
                if isinstance(cleaned, dict):
                    p = (cleaned.get("procedure") or "").strip()
                    if p:
                        procedure = p

            # 5.3) Fallback regex (inglés/español)
            if not procedure and isinstance(rag_answer, str):
                m = re.search(
                    r"(?i)\b(procedure|procedimiento)\b\s*[:\-–—]\s*([^\n]+)",
                    rag_answer,
                )
                if m:
                    procedure = m.group(2).strip()

            # 5.4) Último recurso: tomar primera línea corta como título
            if not procedure and isinstance(rag_answer, str):
                first_line = rag_answer.strip().splitlines()[0].strip()
                if 1 <= len(first_line.split()) <= 8:
                    procedure = first_line
        except Exception:
            procedure = None

        # 6) TTS (sólo medimos tiempo; no guardamos el audio)
        try:
            logger.info("Llamando a TTS...")
            if isinstance(rag_answer, dict):
                rag_answer = format_rag_answer(rag_answer)
            clean_dict = clean_rag_answer(rag_answer or "")
            pretty_text = format_clean_answer(clean_dict)
            _, tts_time = call_tts_direct(TTS_URL, pretty_text, None)
            # if audio_bytes:
            #     # Guardar audio en disco si se generó correctamente
            #     if not os.path.exists(AUDIOS_TTS_DIR):
            #         os.makedirs(AUDIOS_TTS_DIR, exist_ok=True)
            #     safe_id = f"{idx+1}"
            #     audio_out_path = os.path.join(AUDIOS_TTS_DIR, f"{safe_id}_tts.wav")
            #     with open(audio_out_path, "wb") as f:
            #         f.write(audio_bytes)
            #     logger.info(f"TTS audio saved: {audio_out_path}")
        except Exception as e:
            logger.warning(f"TTS fallo: {e}")
            tts_time = None

        total_time = (tts_time or 0) + (rag_time or 0) + (asr_time or 0)

        # Reemplaza la construcción de out_rows para usar expected_text_audio en la columna de salida:
        out_rows.append({
            "Input Type (Text, audio, text+audio)": row.get(col_input_type, ""),
            "Expected Text": expected_text,
            "Expected Text Audio": expected_text_audio,  # subtítulos de referencia
            "Level (N1,N2,N3)": level,
            "¿Expected answer? (Yes/No)": expected_answer_flag,
            "Date": today_str,
            "Text Input": text_input,
            "Transcribed Audio Text": transcribed_text,
            "ASR time": round(asr_time, 3) if asr_time is not None else None,
            "WER": round(wer_val, 4) if wer_val is not None else None,
            "RAG Answer": rag_answer,
            "Procedure": procedure,
            "RAG Status": rag_status,
            "RAG Error Menssage": rag_error,
            "¿Answer Correct?(Yes/No)": "",
            "RAG Time": round(float(rag_time), 3) if rag_time is not None else None,
            "RAG Avg Score": rag_avg_score,
            "RAG Pages": rag_pages,
            "TTS Time": round(float(tts_time), 3) if tts_time is not None else None,
            "Total time": round(float(total_time), 3),
        })

    # Asegurar orden de columnas solicitado
    df_out = pd.DataFrame(out_rows)
    for c in EXPECTED_OUTPUT_COLUMNS:
        if c not in df_out.columns:
            df_out[c] = None
    df_out = df_out[EXPECTED_OUTPUT_COLUMNS]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    df_out.to_csv(args.out, index=False, encoding="utf-8")
    logger.info(f"CSV generado: {args.out}")

if __name__ == "__main__":
    main()