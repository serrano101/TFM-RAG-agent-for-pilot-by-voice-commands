import logging

# --- Watchdog Setup ---
import os
from watchdog.events import FileSystemEventHandler, FileSystemEvent

# --- Imports ---
from src.chunker.chunker import Chunker
from src.ocr.ocr_service import OCRService
from src.ingest.ingest_runner import run_ingestion
from src.database.chromadb_repository import VectorDBRepository

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

class PDFHandler(FileSystemEventHandler):  
    def __init__(self, db_path: str, db_repo: VectorDBRepository, ocr_service: OCRService, chunker: Chunker) -> None:
        """
        Inicializa el manejador de eventos para PDFs.

        Args:
            db_repo (VectorDBRepository): Repositorio para comprobar si un PDF ya fue procesado.

        Returns:
            None
        """
        super().__init__() # Llama al constructor de la clase base (padre)
        self.db_path = db_path
        self.db_repo = db_repo
        self.ocr = ocr_service
        self.chunker = chunker

    def on_created(self, event: FileSystemEvent) -> None:
        """
        Evento que se dispara cuando se crea un archivo en la carpeta vigilada. No se llama directamente,
        pero cuando Watchdog detecta un nuevo archivo (observer.schedule), se invoca este método.

        Args:
            event (FileSystemEvent): Evento de watchdog con información del archivo creado.

        Returns:
            None
        """
        try:
            if event.is_directory:
                return
            if event.src_path.endswith('.pdf'):
                pdf_name = os.path.basename(event.src_path)
                logger.info(f"Nuevo PDF detectado: {event.src_path}")
                try:
                    if not self.db_repo.is_document_processed(pdf_name):
                        run_ingestion(file_folder=os.path.dirname(event.src_path), ocr_service=self.ocr, chunker=self.chunker, vector_db_repo=self.db_repo)
                        logger.info(f"PDF procesado correctamente: {pdf_name}")
                    else:
                        logger.info(f"PDF ya procesado, se omite: {pdf_name}")
                except Exception as e:
                    logger.error(f"Error al procesar el PDF '{pdf_name}': {e}", exc_info=True)
                    raise RuntimeError(f"Error al procesar el PDF '{pdf_name}': {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado en on_created: {e}", exc_info=True)
            raise RuntimeError(f"Error inesperado en on_created: {e}") from e

    def execute(self, docs_path: str) -> None:
        """
        Procesa todos los archivos PDF existentes en la ruta especificada.

        Args:
            docs_path (str): Ruta absoluta a la carpeta donde buscar los PDFs.

        Returns:
            None

        Manejo de errores:
            - Si ocurre un error al procesar un PDF individual, se registra con logger.error y se continúa con el resto.
            - Si ocurre un error inesperado fuera del bucle, se propaga la excepción.
        """
        try:
            # Buscar todos los archivos PDF en la ruta indicada
            pdfs_existentes = [
                f for f in os.listdir(docs_path)
                if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(docs_path, f))
            ]
            if pdfs_existentes:
                logger.info(f"Procesando PDFs existentes: {pdfs_existentes}")
                for pdf in pdfs_existentes:
                    try:
                        # Comprobar si el PDF ya ha sido procesado
                        if not self.db_repo.is_document_processed(pdf):
                            logger.info(f"Procesando PDF nuevo: {pdf}")
                            # Ejecutar el proceso de ingestión
                            run_ingestion(file_folder=docs_path, ocr_service=self.ocr, chunker=self.chunker, vector_db_repo=self.db_repo)
                            logger.info(f"PDF procesado correctamente: {pdf}")
                        else:
                            logger.info(f"PDF ya procesado, se omite: {pdf}")
                    except Exception as e:
                        logger.error(f"Error al procesar el PDF '{pdf}': {e}", exc_info=True)
                        raise RuntimeError(f"Error al procesar el PDF '{pdf}': {e}") from e
            else:
                logger.info("No hay PDFs existentes para procesar.")
        except Exception as e:
            logger.error(f"Error inesperado en execute: {e}", exc_info=True)
            raise RuntimeError(f"Error inesperado en execute: {e}") from e