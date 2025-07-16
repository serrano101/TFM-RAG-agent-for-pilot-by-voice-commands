import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
    ASR_SERVICE_URL = os.getenv("ASR_SERVICE_URL")
    OLLAMA_SERVICE_URL = os.getenv("OLLAMA_SERVICE_URL")
    # HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
