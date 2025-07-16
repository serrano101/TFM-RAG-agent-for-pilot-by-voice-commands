import chromadb
import uuid
class ChromaDBRepository:
    def __init__(self, db_path):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.create_collection("documentos")

    def add_chunks(self, chunks, metadatas):
        self.collection.add(
            ids=[uuid.uuid4() for _ in range(len(chunks))],
            documents=chunks,
            metadatas=metadatas,
        )

    # def is_document_processed(self, document_name):
    #     results = self.collection.get()
    #     if "metadatas" in results:
    #         for meta in results["metadatas"]:
    #             if meta and meta.get("document_name") == document_name:
    #                 return True
    #     return False