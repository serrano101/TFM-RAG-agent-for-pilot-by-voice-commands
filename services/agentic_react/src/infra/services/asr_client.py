import time
import requests
from src.infra.config import Config

class ASRClient:
    def __init__(self):
        self.asr_url = Config.ASR_SERVICE_URL

    def get_last_transcription(self, max_retries=10, wait_seconds=2) -> str:
        for _ in range(max_retries):
            response = requests.get(f"{self.asr_url}/transcription")
            if response.status_code == 200:
                return response.json()["transcription"]
            time.sleep(wait_seconds)
        raise Exception("Transcripción no disponible tras varios intentos")