import os
from src.application.usecases.ingest_documents import IngestDocumentsUseCase
from src.infra.services.ocr_service import OCRService
from src.infra.services.chunker import Chunker
# from common.embedders.embedders import MpnetBaseEmbedder
from src.infra.repositories.chromadb_repository import ChromaDBRepository

def run_ingestion(pdf_folder, db_path):
    ocr_service = OCRService()
    chunker = Chunker()
    # embedder = MpnetBaseEmbedder()
    vector_db_repo = ChromaDBRepository(db_path)
    usecase = IngestDocumentsUseCase(ocr_service, chunker, vector_db_repo)

    for filename in os.listdir(pdf_folder):
        if filename.endswith('.pdf'):
            usecase.execute(os.path.join(pdf_folder, filename))