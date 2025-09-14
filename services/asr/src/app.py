# --- Load configuration ---
import yaml
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- Basic Logging Configuration ---
import logging
from src.utils.logger import setup_logger
level = config["RUNNING"]["LOG_LEVEL"]
setup_logger(level)
logger = logging.getLogger(__name__)

# --- FastAPI Application Setup ---
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import httpx
import asyncio

# --- Imports ---
from src.transcribers.whisper import ASRWhisper
from deprecated import deprecated

# --- Initialize Dependencies ---
try:
    whisper_model = config["ASR"]["WHISPER_MODEL_NAME"]
    asr_service = ASRWhisper(model_name=whisper_model)
except Exception as e:
    logger.error(f"Error initializing ASRWhisper: {str(e)}", exc_info=True)
    raise RuntimeError(f"Application initialization failed: {str(e)}")

# --- Instancia de la aplicación FastAPI ---
app = FastAPI()

# Notifica a los microservicios de forma asíncrona
@deprecated(reason="Este método ya no se utiliza. La notificación se gestiona desde Streamlit.")
async def notify_rag_microservice(transcription: str) -> None:
    """
    Notifica en paralelo y de forma asíncrona a los endpoints de Agentic ReAct y RAG con la transcripción recibida.

    Args:
        transcription (str): Texto transcrito que se enviará a los microservicios.

    Returns:
        None: No se devuelven valores, solo notifica. 
    """
    webhook_agent_react_url = config["RAG"]["WEBHOOK_AGENT_REACT_URL"]
    webhook_rag_url = config["RAG"]["WEBHOOK_RAG_URL"]

    async def notify_agentic():
        try:
            logger.info("Notificando al microservicio Agentic ReAct...")
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_agent_react_url, json={"transcription": transcription})
            logger.debug(f"Respuesta del microservicio Agentic ReAct: {response.status_code} - {response.text}")
            response.raise_for_status()
            logger.info("Notificación al microservicio Agentic ReAct enviada correctamente.")
        except Exception as e:
            logger.error(f"Error notificando a Agente ReAct: {str(e)}", exc_info=True)

    async def notify_rag():
        try:
            logger.info("Notificando al microservicio RAG...")
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_rag_url, json={"transcription": transcription})
            logger.debug(f"Respuesta del microservicio RAG: {response.status_code} - {response.text}")
            response.raise_for_status()
            logger.info("Notificación al microservicio RAG enviada correctamente.")
        except Exception as e:
            logger.error(f"Error notificando a RAG: {str(e)}", exc_info=True)

    await asyncio.gather(notify_agentic(), notify_rag())

@app.get("/")
def read_root() -> JSONResponse:
    """
    Endpoint de bienvenida para el servicio de ASR.

    Returns:
        JSONResponse: Mensaje de bienvenida.
    """
    return JSONResponse(
        status_code=200, 
        content={"message": "Welcome to the ASR Service!"}
    )

@app.post("/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...), language: str | None = Form(default=None)) -> JSONResponse:
    """
    Endpoint para transcribir audio a texto.

    Args:
        file (UploadFile): Archivo de audio recibido vía formulario multipart.

    Returns:
        JSONResponse: Respuesta con la transcripción o el error correspondiente.
    """
    try:
        # Leer el archivo de audio
        audio_bytes = await file.read()
        if not audio_bytes:
            logger.warning("Archivo de audio vacío o no recibido")
            return JSONResponse(
                status_code=400,
                content={"status": "validation_error", "message": "Audio file is empty or missing", "transcription": None}
            )
        # Transcribir el audio
        transcription = asr_service.transcribe(audio_bytes, language=language)
        if not transcription or not transcription.strip():
            logger.warning("Transcripción vacía")
            return JSONResponse(
                status_code=400,
                content={"status": "validation_error", "message": "Transcription is empty", "transcription": None}
            )

        # await notify_rag_microservice(transcription)  # Deprecated: la notificación se gestiona desde Streamlit

        return JSONResponse(
            status_code=200,
            content={"status": "success", "transcription": transcription}
        )
    except Exception as e:
        logger.error(f"Error en transcribe_endpoint: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "processing_error", "message": f"Error processing audio: {str(e)}", "transcription": None}
        )

@app.get("/languages")
def languages_options() -> JSONResponse:
    """
    Endpoint para obtener las opciones de idiomas soportados por Whisper.

    Returns:
        JSONResponse: Respuesta con la lista de idiomas soportados.{"status": "success", "languages": {Name->Code}}
    """
    try:
        languages = asr_service.languages_options()        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "languages": languages}
        )
    except Exception as e:
        logger.error(f"Error en languages_options: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error retrieving languages: {str(e)}", "languages": []}
        )