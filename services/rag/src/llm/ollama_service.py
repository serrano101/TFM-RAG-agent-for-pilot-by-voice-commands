import logging
from typing import Optional
from langchain_ollama import ChatOllama
from pydantic import BaseModel
# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)
class ProcedureFormat(BaseModel):
    procedure: str
    conditions: list[str]
    steps: list[str]
    notes: list[str]
class LLMClientOllama:
    """
    Cliente para conectarse a un modelo LLM usando Ollama.
    """

    def __init__(
        self, 
        model: str, 
        base_url: str, 
        temperature: Optional[float]= None,
        top_k: Optional[int]= 40,
        top_p: Optional[float]= 0.9
    ) -> None:
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
            self.client = ChatOllama(
                model=model, 
                base_url=base_url, 
                format=ProcedureFormat.model_json_schema(), 
                temperature=temperature,
                top_k=top_k,
                top_p=top_p
            )
            logger.info("[LLMClientOllama] LLM client initialized successfully")
            self._warmup()  # Llama al método de calentamiento para asegurar que el modelo está listo
            logger.info("[LLMClientOllama] Warmup completed successfully")
        except Exception as e:
            # Si ocurre un error, lo registra con el logger y relanza la excepción
            logger.error(f"[LLMClientOllama] Error al inicializar: {str(e)}", exc_info=True)
            raise RuntimeError(f"No se pudo inicializar el cliente Ollama: {str(e)}")
        
    def _warmup(self):
            """
            Realiza una llamada de calentamiento al modelo para asegurar que está listo para su uso.
            """
            try:
                self.client.invoke("Hello, world!")
                logger.info("[LLMClientOllama] Warmup call successful")
            except Exception as e:
                logger.error(f"[LLMClientOllama] Error en la llamada de calentamiento: {str(e)}", exc_info=True)