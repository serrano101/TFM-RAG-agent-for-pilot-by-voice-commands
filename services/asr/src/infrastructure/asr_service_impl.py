from src.domain.asr_service import ASRService
import whisper
import tempfile
import torch

# Verifica si hay una GPU disponible y establece el dispositivo
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("CUDA available:", torch.cuda.is_available())
print("CUDA device count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("CUDA device name:", torch.cuda.get_device_name(0))
else:
    print("No GPU detected")
class ASRServiceImpl(ASRService):

    def __init__(self, model_name="large-v3-turbo"):
        self.model = whisper.load_model(model_name, device=DEVICE) #  Cargar el modelo en GPU si está disponible

    def transcribe(self, audio_bytes: bytes) -> str:
        # Guardar el audio temporalmente
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            result = self.model.transcribe(tmp.name)
        return result["text"]