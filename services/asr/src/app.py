# --- Load configuration ---
import yaml, logging
from src.utils.logger import setup_logger

with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- Basic Logging Configuration ---
level = config["RUNNING"]["LOG_LEVEL"]
setup_logger(level)
logger = logging.getLogger(__name__)

# --- FastAPI Application Setup ---
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from deprecated import deprecated
import asyncio

app = FastAPI()
app.state.config = config
app.state.logger = logger
app.state.ready = False
app.state.initializing = False

# Rutas bootstrap
from src.routes import router as bootstrap_router
app.include_router(bootstrap_router)

# Endpoint de ejemplo que requiere ASR inicializado
from src.transcribers.whisper import ASRWhisper

@app.post("/transcribe")
async def transcribe_endpoint(request: Request, file: UploadFile = File(...), language: str | None = Form(default=None)) -> JSONResponse:
    """
    Endpoint para transcribir audio a texto.

    Args:
        file (UploadFile): Archivo de audio recibido vía formulario multipart.

    Returns:
        JSONResponse: Respuesta con la transcripción o el error correspondiente.
    """
    # Verifica que ASR esté inicializado
    if not getattr(request.app.state, "ready", False):
        return JSONResponse(status_code=503, content={"status": "not_ready", "message": "ASR not initialized. Call /warmup first.", "transcription": None})

    asr_service: ASRWhisper = request.app.state.asr_service

    # Leer el archivo de audio
    audio_bytes = await file.read()
    if not audio_bytes:
        return JSONResponse(status_code=400, content={"status": "validation_error", "message": "Audio file is empty or missing", "transcription": None})

    try:
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
        logger.error(f"Error transcribing: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "processing_error", "message": str(e), "transcription": None}
        )

@app.get("/languages")
def languages_options(request: Request) -> JSONResponse:
    """
    Endpoint para obtener las opciones de idiomas soportados por Whisper.

    Returns:
        JSONResponse: Respuesta con la lista de idiomas soportados.{"status": "success", "languages": {Name->Code}}
    """
    if not getattr(request.app.state, "ready", False):
        return JSONResponse(status_code=503, content={"status": "not_ready", "message": "ASR not initialized. Call /warmup first.", "languages": {}})
    try:
        asr_service: ASRWhisper = request.app.state.asr_service
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