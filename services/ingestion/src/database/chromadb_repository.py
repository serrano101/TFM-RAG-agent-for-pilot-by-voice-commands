import logging
from src.embedders.sentence_transformers_embedders import Embedder
from typing import Dict, List, Any
from langchain_chroma.vectorstores import Chroma
from langchain_core.documents import Document
import uuid
from urllib.parse import urlparse

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class VectorDBRepository:
    """
    Repositorio para gestionar la base de datos vectorial.
    """
    def __init__(self, db_path: str, collection_name: str, embedding_function: Embedder) -> None:
        """
        Inicializa el repositorio vectorial conectando con ChromaDB y la colección indicada.
        Si no existe, se creará automáticamente.

        Args:
            db_path (str): Ruta al directorio de persistencia de la base de datos.
            collection_name (str): Nombre de la colección de ChromaDB.
            embedding_function (Embedder): Objeto para generar embeddings.
        
        Returns:
            None: No se devuelven valores. 

        Raises:
            RuntimeError: Si no se puede inicializar la base de datos o la colección.
        """
        try:
            logger.info(f"[VectorDBRepository] Inicializando con la colección '{collection_name}' en '{db_path}' (solo modo HTTP)")
            # Solo conexión HTTP a ChromaDB como microservicio
            if not (db_path.startswith("http://") or db_path.startswith("https://")):
                raise ValueError("db_path debe ser una URL HTTP para ChromaDB remoto (microservicio)")
            parsed = urlparse(db_path)
            host = parsed.hostname
            port = parsed.port or 8000  # Usa 8000 por defecto si no está en la URL
            # Define your custom similarity calculation function
            def custom_relevance_score_fn(similarity_score: float) -> float:
                # Example calculation (customize as needed)
                relevance_score = 1 / (1 + similarity_score)
                return relevance_score
            
            self.vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=embedding_function,
                host=host,
                port=port,
                create_collection_if_not_exists=True,
                relevance_score_fn=custom_relevance_score_fn
            )
            logger.info(f"[VectorDBRepository] Conectado a ChromaDB remoto en '{db_path}'")
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error al inicializar: {e}", exc_info=True)
            raise RuntimeError(f"No se pudo inicializar VectorDBRepository: {e}")
    
    def add_chunks(self, chunks: List[str], metadatas: List[Dict[str, Any]]) -> None:
        """
        Añade fragmentos de texto y sus metadatos a la base de datos vectorial.

        Args:
            chunks (List[str]): Lista de fragmentos de texto a añadir.
            metadatas (List[Dict[str, Any]]): Lista de metadatos asociados a cada fragmento.

        Returns:
            None: No se devuelven valores.

        Raises:
            RuntimeError: Si ocurre un error al añadir los fragmentos.
        """
        try:
            logger.info(f"[VectorDBRepository] Añadiendo {len(chunks)} fragmentos a la base de datos.")
            documents = [Document(page_content=chunk, metadata=meta) for chunk, meta in zip(chunks, metadatas)]
            ids = [str(uuid.uuid4()) for _ in range(len(chunks))]
            self.vector_store.add_documents(documents=documents, ids=ids)
            logger.info(f"[VectorDBRepository] Añadidos {len(chunks)} fragmentos a la base de datos.")
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error al añadir fragmentos: {e}", exc_info=True)
            raise RuntimeError(f"Error al añadir fragmentos: {e}")

    def delete_chunks(self, chunk_ids: List[str]) -> None:
        """
        Elimina los fragmentos de la base de datos vectorial.

        Args:
            chunk_ids (List[str]): IDs de los fragmentos a eliminar.

        Returns:
            None: No se devuelven valores.

        Raises:
            RuntimeError: Si ocurre un error al eliminar el fragmento.
        """
        try:
            logger.info(f"[VectorDBRepository] Eliminando fragmentos: {chunk_ids}")
            self.vector_store.delete_document(document_id=chunk_ids)
            logger.info(f"[VectorDBRepository] Fragmentos eliminados correctamente: {chunk_ids}")
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error al eliminar los fragmentos '{chunk_ids}': {e}", exc_info=True)
            raise RuntimeError(f"Error al eliminar los fragmentos: {e}")

    def update_chunks(self, chunk_ids: List[str], new_chunks: List[str], new_metadatas: List[Dict[str, Any]]) -> None:
        """
        Actualiza los fragmentos de la base de datos vectorial.

        Args:
            chunk_ids (List[str]): IDs de los fragmentos a actualizar.
            new_chunks (List[str]): Nuevos fragmentos de texto.
            new_metadatas (List[Dict[str, Any]]): Nuevos metadatos asociados a cada fragmento.

        Returns:
            None: No se devuelven valores.

        Raises:
            RuntimeError: Si ocurre un error al actualizar los fragmentos.
        """
        try:
            logger.info(f"[VectorDBRepository] Actualizando fragmentos: {chunk_ids}")
            documents = [Document(page_content=chunk, metadata=meta) for chunk, meta in zip(new_chunks, new_metadatas)]
            # Verificar si documents es una list de Document (list[Document])
            if not isinstance(documents, list) or not all(isinstance(doc, Document) for doc in documents):
                raise TypeError("documents debe ser una lista de Document")
            self.vector_store.update_documents(document_ids=chunk_ids, documents=documents)
            logger.info(f"[VectorDBRepository] Fragmentos actualizados correctamente: {chunk_ids}")
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error al actualizar los fragmentos '{chunk_ids}': {e}", exc_info=True)
            raise RuntimeError(f"Error al actualizar los fragmentos: {e}")
    
    def update_chunk(self, chunk_id: str, new_chunk: str, new_metadata: Dict[str, Any]) -> None:
        """
        Actualiza un fragmento de la base de datos vectorial.

        Args:
            chunk_id (str): ID del fragmento a actualizar.
            new_chunk (str): Nuevo fragmento de texto.
            new_metadata (Dict[str, Any]): Nuevos metadatos asociados al fragmento.

        Returns:
            None: No se devuelven valores.

        Raises:
            RuntimeError: Si ocurre un error al actualizar el fragmento.
        """
        try:
            logger.info(f"[VectorDBRepository] Actualizando fragmento: {chunk_id}")
            document = Document(page_content=new_chunk, metadata=new_metadata)
            # Verificar si document es una instancia de Document
            if not isinstance(document, Document):
                raise TypeError("document debe ser una instancia de Document")
            self.vector_store.update_document(document_id=chunk_id, document=document)
            logger.info(f"[VectorDBRepository] Fragmento actualizado correctamente: {chunk_id}")
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error al actualizar el fragmento '{chunk_id}': {e}", exc_info=True)
            raise RuntimeError(f"Error al actualizar el fragmento: {e}")
    
    def is_document_processed(self, document_name: str) -> bool:
        """
        Comprueba si un documento ya ha sido procesado buscando su nombre en los metadatos de la colección.

        Args:
            document_name (str): Nombre del documento a buscar.

        Returns:
            bool: True si el documento ya está procesado, False en caso contrario.
        """
        try:
            results = self.vector_store.get()
            if "metadatas" in results:
                for meta in results["metadatas"]:
                    if meta and meta.get("origin", {}).get("filename") == document_name:
                        return True
            return False
        except Exception as e:
            logger.error(f"[VectorDBRepository] Error comprobando si el documento '{document_name}' está procesado: {e}", exc_info=True)
            return False