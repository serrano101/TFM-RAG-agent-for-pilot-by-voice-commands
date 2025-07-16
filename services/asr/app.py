# Importar las librerias de FastAPI
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from src.infrastructure.asr_service_impl import ASRServiceImpl
from src.application.transcribe_audio import transcribe_audio
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
asr_service = ASRServiceImpl()

def notify_agentic_react(transcription: str):
    webhook_url = os.getenv("AGENTIC_REACT_WEBHOOK_URL")
    try:
        response = requests.post(webhook_url, json={"transcription": transcription})
        response.raise_for_status()
    except Exception as e:
        print("Error notificando a agentic_react:", e)

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
    notify_agentic_react(transcription)  # Notifica al microservicio agentic_react
    return JSONResponse(content={"transcription": transcription})
