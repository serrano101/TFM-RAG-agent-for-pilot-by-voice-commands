import chromadb
import uuid
class ChromaDBRepository:
    def __init__(self, db_path):
        if db_path.startswith("http"):
            self.client = chromadb.HttpClient(host=db_path)
        else:
            self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection("documentos")

    def add_chunks(self, chunks, metadatas):
        self.collection.add(
            ids=[str(uuid.uuid4()) for _ in range(len(chunks))],
            documents=chunks,
            metadatas=metadatas,
        )

    def is_document_processed(self, document_name):
        results = self.collection.get()
        if "metadatas" in results:
            for meta in results["metadatas"]:
                if meta and meta.get("origin", {}).get("filename") == document_name:
                    return True
        return False