import logging
import yaml
import base64
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from src.utils.logger import setup_logger
from src.routes import router as bootstrap_router

# --- Load config ---
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- Logger ---
level = config["RUNNING"]["LOG_LEVEL"]
setup_logger(level)
logger = logging.getLogger("tts.app")
logger.info("TTS service starting...")

app = FastAPI()
app.state.config = config
app.state.logger = logger
app.state.ready = False
app.state.initializing = False

app.include_router(bootstrap_router)

class SynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize")
    speaker: Optional[str] = Field(None, description="Speaker ID (multi-speaker models)")
    raw_wav: Optional[bool] = Field(False, description="If true, returns WAV stream instead of base64 JSON")

@app.post("/synthesize")
async def synthesize_endpoint(req: Request, body: SynthesisRequest):
    if not getattr(req.app.state, "ready", False):
        return JSONResponse(status_code=503, content={"status": "not_ready", "message": "TTS not initialized. Call /warmup first."})

    tcfg = config["TTS"]
    max_len = tcfg.get("MAX_TEXT_LENGTH", 1000)
    if len(body.text) > max_len:
        return JSONResponse(
            status_code=400,
            content={"status": "validation_error", "message": f"Text too long (>{max_len})", "audio_base64": None},
        )

    try:
        engine = req.app.state.tts_engine
        result = engine.synthesize(body.text, speaker=body.speaker)
        wav_bytes = result["wav_bytes"]
        sample_rate = result["sample_rate"]
        duration = result["duration"]
        speaker_used = result["speaker"]

        if body.raw_wav:
            return StreamingResponse(
                content=iter([wav_bytes]),
                media_type="audio/wav",
                headers={
                    "X-Sample-Rate": str(sample_rate),
                    "X-Duration-Seconds": f"{duration:.3f}",
                    "X-Speaker": speaker_used or "",
                },
            )

        if config["TTS"].get("RETURN_BASE64", True):
            as_b64 = base64.b64encode(wav_bytes).decode("utf-8")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "sample_rate": sample_rate,
                    "duration_seconds": duration,
                    "speaker": speaker_used,
                    "audio_base64": as_b64,
                },
            )
        # Fallback: binary length only
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "sample_rate": sample_rate,
                "duration_seconds": duration,
                "speaker": speaker_used,
                "audio_size_bytes": len(wav_bytes),
            },
        )
    except ValueError as ve:
        logger.warning(f"Synthesis validation error: {ve}")
        return JSONResponse(status_code=400, content={"status": "validation_error", "message": str(ve)})
    except Exception as e:
        logger.error(f"Synthesis error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/health")
def health():
    return JSONResponse(status_code=200, content={"status": "ok"})