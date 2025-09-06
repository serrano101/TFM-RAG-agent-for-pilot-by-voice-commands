import logging
from sentence_transformers import SentenceTransformer
from typing import List

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class Embedder:
    """
    Wrapper para modelos sentence-transformer que genera embeddings de texto y es compatible con ChromaDB.
    """
    def __init__(self, model_name: str) -> None:
        """
        Inicializa el objeto Embedder cargando el modelo sentence-transformer especificado.

        Args:
            model_name (str): Nombre del modelo de sentence-transformers a cargar.
        
        Returns:
            None: No se devuelven valores. 

        Raises:
            RuntimeError: Si no se puede cargar el modelo SentenceTransformer.
        """
        logger.debug(f"[Embedder] Intentando inicializar Embedder con el modelo: {model_name}")
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"[Embedder] Embedder inicializado correctamente con el modelo: {model_name}")
        except Exception as e:
            logger.error(f"[Embedder] Error al cargar el modelo SentenceTransformer '{model_name}': {e}")
            raise RuntimeError(f"No se pudo cargar el modelo SentenceTransformer '{model_name}': {e}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Genera los embeddings para una lista de textos/documentos.

        Args:
            texts (List[str]): Lista de textos a embeder.

        Returns:
            List[List[float]]: Lista de embeddings (uno por cada texto).

        Raises:
            RuntimeError: Si ocurre un error al generar los embeddings.
        """
        if not texts:
            logger.warning("[Embedder] El método embed_documents fue llamado con una lista vacía de textos.")
            return []
        logger.info(f"[Embedder] Creando embeddings para {len(texts)} documento(s) (embed_documents).")
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False).tolist()
            logger.info(f"[Embedder] Se crearon correctamente {len(embeddings)} embeddings (embed_documents).")
            return embeddings
        except Exception as e:
            logger.error(f"[Embedder] Ocurrió un error durante el proceso de embedding (embed_documents): {e}")
            raise RuntimeError(f"Error durante el proceso de embedding (embed_documents): {e}")

    def embed_query(self, text: str) -> List[float]:
        """
        Genera el embedding para una consulta individual.

        Args:
            text (str): Texto de la consulta a embeder.

        Returns:
            List[float]: Embedding de la consulta.

        Raises:
            RuntimeError: Si ocurre un error al generar el embedding de la consulta.
        """
        if not text:
            logger.warning("[Embedder] El método embed_query fue llamado con un texto vacío.")
            return []
        logger.info("[Embedder] Creando embedding para una consulta (embed_query).")
        try:
            embedding = self.model.encode([text], convert_to_tensor=False)[0].tolist()
            logger.info("[Embedder] Se creó correctamente el embedding para la consulta (embed_query).")
            return embedding
        except Exception as e:
            logger.error(f"[Embedder] Ocurrió un error durante el proceso de embedding (embed_query): {e}")
            raise RuntimeError(f"Error durante el proceso de embedding (embed_query): {e}") 