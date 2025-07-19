import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.presentation.components.ingest_runner import run_ingestion
from src.infra.repositories.chromadb_repository import ChromaDBRepository
from dotenv import load_dotenv

class PDFHandler(FileSystemEventHandler):
    def __init__(self, db_repo):
        super().__init__()
        self.db_repo = db_repo

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.pdf'):
            pdf_name = os.path.basename(event.src_path)
            print(f"Nuevo PDF detectado: {event.src_path}")
            load_dotenv()
            if not self.db_repo.is_document_processed(pdf_name):
                run_ingestion(os.path.dirname(event.src_path), os.getenv("VECTOR_DB_URL"))
            else:
                print(f"PDF ya procesado, se omite: {pdf_name}")

if __name__ == "__main__":
    # Cargar variables de entorno desde .env
    load_dotenv()
    path = os.getenv("PDF_FOLDER")
    print(f"Ruta de PDFs a vigilar: {path}")
    os.makedirs(path, exist_ok=True)

    # Procesar PDFs existentes al arrancar solo si no están ya en la base de datos
    db_path = os.getenv("VECTOR_DB_URL")
    db_repo = ChromaDBRepository(db_path)

    pdfs_existentes = [f for f in os.listdir(path) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(path, f))]
    if pdfs_existentes:
        print(f"Procesando PDFs existentes: {pdfs_existentes}")
        for pdf in pdfs_existentes:
            if not db_repo.is_document_processed(pdf):
                print(f"Procesando PDF nuevo: {pdf}")
                run_ingestion(path, db_path)
            else:
                print(f"PDF ya procesado, se omite: {pdf}")
    else:
        print("No hay PDFs existentes para procesar.")

    event_handler = PDFHandler(db_repo)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    print(f"Vigilando la carpeta: {path}")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()