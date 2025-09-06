# --- Load configuration ---
import yaml
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- Basic Logging Configuration ---
import logging
from src.utils.logger import setup_logger
level = config["RUNNING"]["LOG_LEVEL"]
setup_logger(level)
logger = logging.getLogger(__name__)

# --- Watchdog Setup ---
import os
import time
from watchdog.observers import Observer

# --- Imports ---
from src.embedders.sentence_transformers_embedders import Embedder
from src.ingest.ingest_runner import run_ingestion
from src.database.chromadb_repository import VectorDBRepository
from src.chunker.chunker import Chunker
from src.ocr.ocr_service import OCRService

# Import handlers for different file types
from src.DocumentHandler.pdf_handler import PDFHandler
# from src.DocumentHandler.word_handler import WordHandler  # Uncomment if implemented


# --- Initialize Dependencies ---
try:
    logger.info("Inicializando dependencias")
    
    # Embedder
    embedder_name = config["VECTOR_DB"]["EMBEDDER_NAME"]
    embedder = Embedder(model_name=embedder_name)

    # Base de datos vectorial --> chromadb
    db_path = config["VECTOR_DB"]["URL"]
    collection_name = config["VECTOR_DB"]["COLLECTION_NAME"]
    vector_db = VectorDBRepository(db_path=db_path, collection_name=collection_name, embedding_function=embedder)

    # Chunk
    chunker = Chunker()

    # OCR
    ocr_service = OCRService()

    # Instanciar handlers para cada tipo de archivo
    pdf_handler = PDFHandler(db_path=db_path, db_repo=vector_db, ocr_service=ocr_service, chunker=chunker)

except Exception as e:
    logger.error(f"Error al inicializar las dependencias: {e}", exc_info=True)

if __name__ == "__main__":
    """
    Script principal que inicializa la vigilancia de la carpeta de PDFs y procesa los existentes.

    Entradas:
        - Lee la configuración desde /app/config.yaml
        - Usa la ruta de PDFs: /app/docs/dataset_procedures

    Salidas:
        - Procesa PDFs nuevos y existentes, ejecutando run_ingestion si corresponde.
        - Logs informativos y de advertencia sobre el procesamiento.
    """
    try:
        # Cargar docs
        docs_path = "/app/docs/dataset_procedures" 
        if not os.path.exists(docs_path):
            os.makedirs(docs_path, exist_ok=True)
        logger.info(f"Ruta de archivos a vigilar: {docs_path}")

        # Procesar archivos existentes al arrancar (puedes añadir más handlers aquí)
        pdf_handler.execute(docs_path)

        # Iniciar el observador y registrar todos los handlers
        observer = Observer()
        observer.schedule(pdf_handler, docs_path, recursive=False)
        # observer.schedule(word_handler, docs_path, recursive=False)  # Si implementas WordHandler
        logger.info(f"Vigilando la carpeta: {docs_path} con múltiples handlers")
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    except Exception as e:
        logger.error(f"Error inesperado en el watcher principal: {e}", exc_info=True)