import logging
from langchain_ollama import ChatOllama

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class LLMClientOllama:
    """
    Cliente para conectarse a un modelo LLM usando Ollama.
    """
    def __init__(self, model: str, base_url: str) -> None:
        """
        Inicializa el cliente Ollama con el modelo y la URL base proporcionados.

        Args:
            model (str): Nombre del modelo a utilizar en Ollama.
            base_url (str): URL base del servicio Ollama.

        Returns:
            None: No se devuelven valores. 

        Raises:
            RuntimeError: Si ocurre un error al inicializar el cliente Ollama.
        """
        try:
            # Intenta crear el cliente de Ollama con el modelo y la URL proporcionados
            self.client = ChatOllama(model=model, base_url=base_url)
            logger.info("[LLMClientOllama] LLM client initialized successfully")
        except Exception as e:
            # Si ocurre un error, lo registra con el logger y relanza la excepción
            logger.error(f"[LLMClientOllama] Error al inicializar: {str(e)}", exc_info=True)
            raise RuntimeError(f"No se pudo inicializar el cliente Ollama: {str(e)}")