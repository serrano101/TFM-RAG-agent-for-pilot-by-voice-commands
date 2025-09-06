import whisper
import tempfile
import torch

import logging
# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)


# Verifica si hay una GPU disponible y establece el dispositivo
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

logger.info(f"CUDA available: {torch.cuda.is_available()}")
logger.info(f"CUDA device count: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    logger.debug(f"CUDA device name: {torch.cuda.get_device_name(0)}")
else:
    logger.info("No GPU detected")


class ASRWhisper:
    """
    Transcriptor de audio a texto usando el modelo Whisper.

    Esta clase permite cargar un modelo Whisper y transcribir archivos de audio, utilizando GPU si está disponible.
    """

    def __init__(self, model_name: str) -> None:
        """
        Inicializa el transcriptor Whisper con el modelo especificado.

        Args:
            model_name (str): Nombre del modelo Whisper a cargar.

        Returns:
            None

        Raises:
            RuntimeError: Si ocurre un error al cargar el modelo.
        """
        try:
            logger.info(f"[ASRWhisper] Cargando modelo Whisper '{model_name}' en dispositivo: {DEVICE}")
            self.model = whisper.load_model(model_name, device=DEVICE)
            logger.info("[ASRWhisper] Modelo Whisper cargado correctamente.")
        except Exception as e:
            logger.error(f"[ASRWhisper] Error al cargar el modelo Whisper: {e}", exc_info=True)
            raise RuntimeError(f"Error al cargar el modelo Whisper: {e}")

    def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe un archivo de audio a texto usando el modelo Whisper.

        Args:
            audio_bytes (bytes): Audio en formato bytes (WAV).

        Returns:
            str: Texto transcrito del audio.

        Raises:
            ValueError: Si el audio está vacío.
            RuntimeError: Si ocurre un error durante la transcripción.
        """
        if not audio_bytes:
            logger.warning("[ASRWhisper] El audio recibido está vacío.")
            raise ValueError("El audio recibido para transcripción está vacío.")
        try:
            logger.info("[ASRWhisper] Iniciando transcripción de audio...")
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                result = self.model.transcribe(tmp.name)
                logger.debug(f"[ASRWhisper] Resultado de la transcripción: {result}")
            logger.info("[ASRWhisper] Transcripción completada correctamente.")
            return result["text"]
        except Exception as e:
            logger.error(f"[ASRWhisper] Error en la transcripción: {e}", exc_info=True)
            raise RuntimeError(f"Error en la transcripción de audio: {e}")