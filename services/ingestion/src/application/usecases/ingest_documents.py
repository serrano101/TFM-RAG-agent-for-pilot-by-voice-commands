import os
from datetime import datetime
class IngestDocumentsUseCase:
    def __init__(self, ocr_service, chunker, embedder, vector_db_repo):
        self.ocr_service = ocr_service
        self.chunker = chunker
        self.embedder = embedder
        self.vector_db_repo = vector_db_repo

    def execute(self, pdf_path):
        page_texts = self.ocr_service.extract_text(pdf_path)  # [(page_num, text), ...]
        document_name = os.path.basename(pdf_path)
        chunks = []
        chunk_page_numbers = []
        # Para cada página, hacer chunking y asociar el número de página a cada chunk
        for page_num, text in page_texts:
            page_chunks = self.chunker.chunk(text)
            chunks.extend(page_chunks)
            chunk_page_numbers.extend([page_num] * len(page_chunks))
        embeddings = self.embedder.embed(chunks)
        # Metadata extendida por chunk
        metadatas = []
        for i, page_num in enumerate(chunk_page_numbers):
            meta = {
                "id": f"{document_name}_{i}",  # id único por documento y chunk
                "document_name": document_name,
                "chunk_index": i,
                "page_number": page_num,
                "ingest_time": datetime.now().isoformat()
            }
            metadatas.append(meta)
        self.vector_db_repo.add_chunks(chunks, embeddings, metadatas)