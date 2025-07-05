# Importar las librerias de FastAPI
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from src.infrastructure.asr_service_impl import ASRServiceImpl
from src.application.transcribe_audio import transcribe_audio

app = FastAPI()
asr_service = ASRServiceImpl()
@app.get("/")
def read_root():
    """
    Endpoint de bienvenida para el servicio de ASR.
    """
    return {"message": "Welcome to the ASR Service!"}

@app.post("/transcribe/")
async def transcribe_endpoint(file: UploadFile = File(...)):
    """
    Endpoint para transcribir audio a texto.
    """
    audio_bytes = await file.read()
    transcription = transcribe_audio(audio_bytes, asr_service)
    return JSONResponse(content={"transcription": transcription})
