
import os
import logging
from src.ocr.ocr_service import OCRService
from src.chunker.chunker import Chunker
from src.database.chromadb_repository import VectorDBRepository

# Logger para el módulo actual
logger = logging.getLogger(__name__)

def run_ingestion(file_folder: str, ocr_service: OCRService, chunker: Chunker, vector_db_repo: VectorDBRepository) -> None:
    """
    Procesa todos los archivos de una carpeta, convirtiéndolos en documentos, generando chunks y almacenándolos en la base de datos vectorial.

    Args:
        file_folder (str): Ruta a la carpeta con los archivos a procesar.
        ocr_service (OCRService): Servicio OCR para convertir archivos a documentos.
        chunker (Chunker): Servicio para dividir documentos en chunks.
        vector_db_repo (VectorDBRepository): Repositorio para almacenar los chunks y metadatos.

    Returns:
        None

    Manejo de errores:
        - Si ocurre un error al procesar un archivo, se registra con logger.error y se continúa con el resto.
        - Si ocurre un error inesperado fuera del bucle, se propaga la excepción.
    """
    try:
        for filename in os.listdir(file_folder):
            file_path = os.path.join(file_folder, filename)
            try:
                logger.info(f"Procesando archivo: {file_path}")
                dl_doc = ocr_service.convert_document(file_path)
                chunks, metadatas = chunker.chunk_docling(dl_doc)
                vector_db_repo.add_chunks(chunks, metadatas)
                logger.info(f"Archivo procesado y almacenado correctamente: {filename}")
            except Exception as e:
                logger.error(f"Error al procesar el archivo '{filename}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error inesperado en run_ingestion: {e}", exc_info=True)
        raise RuntimeError(f"Error inesperado en run_ingestion: {e}") from e