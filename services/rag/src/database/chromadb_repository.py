import logging
from src.embedders.sentence_transformers_embedders import Embedder
from typing import Dict, List, Optional, Union, Any
from langchain_chroma.vectorstores import Chroma
from langchain_core.documents import Document
from urllib.parse import urlparse

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class VectorDBRepository:
    """
    Repositorio para gestionar la base de datos vectorial.
    """
    def __init__(self, db_path: str, collection_name: str, embedding_function: Embedder) -> None:
        """
        Inicializa el repositorio vectorial conectando con ChromaDB como microservicio HTTP y la colección indicada.

        Args:
            db_path (str): URL HTTP del microservicio ChromaDB.
            collection_name (str): Nombre de la colección de ChromaDB.
            embedding_function (Embedder): Objeto para generar embeddings.
        
        Returns:
            None: No se devuelven valores. 

        Raises:
            RuntimeError: Si no se puede inicializar la base de datos o la colección.
        """
        try:
            if not (db_path.startswith("http://") or db_path.startswith("https://")):
                raise ValueError("db_path debe ser una URL HTTP para ChromaDB remoto (microservicio)")
            parsed = urlparse(db_path)
            host = parsed.hostname
            port = parsed.port or 8000  # Usa 8000 por defecto si no está en la URL

            def custom_relevance_score_fn(similarity_score: float) -> float:
                # Example calculation (customize as needed)
                relevance_score = 1 / (1 + similarity_score)
                return relevance_score

            self.vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=embedding_function,
                host=host,
                port=port,
                create_collection_if_not_exists=False, # Aqui no interesa crear una colección ya que se asume que ya existe y solo se realizan consultas
                relevance_score_fn=custom_relevance_score_fn
            )
            logger.info(f"[VectorDBRepository] Conectado a ChromaDB remoto en '{db_path}'")
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error al inicializar: {e}", exc_info=True)
            raise RuntimeError(f"No se pudo inicializar VectorDBRepository: {e}")

    def search(
        self,
        query: Union[str, List[float]],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        return_score: bool = False,
        **kwargs
    ) -> Union[List[Document], List[tuple[Document, float]]]:
        """
        Realiza una búsqueda unificada por texto o embedding en la base de datos vectorial.

        Args:
            query (str | List[float]): Texto de consulta o embedding.
            top_k (int, opcional): Número de documentos a devolver. Por defecto 5.
            filter (dict, opcional): Filtro por metadatos.
            where_document (dict, opcional): Filtro por contenido del documento.
            return_score (bool, opcional): Si es True, devuelve también la puntuación de similitud.
            **kwargs: Otros argumentos adicionales para la búsqueda.

        Returns:
            List[Document] o List[tuple[Document, float]]: Resultados de la búsqueda.

        Raises:
            RuntimeError: Si ocurre un error durante la búsqueda.
        """
        try:
            # Busqueda por texto
            if isinstance(query, str):
                if return_score:
                    results = self.vector_store.similarity_search_with_score(
                        query=query, k=top_k, filter=filter, where_document=where_document, **kwargs
                    )
                else:
                    results = self.vector_store.similarity_search(
                        query=query, k=top_k, filter=filter, where_document=where_document, **kwargs
                    )
            # Busqueda por embedding
            else:
                if return_score:
                    results = self.vector_store.similarity_search_by_vector_with_relevance_scores(
                        embedding=query, k=top_k, filter=filter, where_document=where_document, **kwargs
                    )
                else:
                    results = self.vector_store.similarity_search_by_vector(
                        embedding=query, k=top_k, filter=filter, where_document=where_document, **kwargs
                    )
            logger.info(f"[VectorDBRepository] Búsqueda realizada correctamente. Resultados: {len(results)} documentos encontrados.")
            return results
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error en la búsqueda: {e}", exc_info=True)
            raise RuntimeError(f"Error en la búsqueda: {e}")