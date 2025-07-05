import chromadb

class ChromaDBRepository:
    def __init__(self, db_path):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection("documentos")

    def add_chunks(self, chunks, embeddings, metadatas):
        self.collection.add(
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
            ids=[meta["id"] for meta in metadatas]  # Usa el id único por chunk
        )

    def is_document_processed(self, document_name):
        results = self.collection.get()
        if "metadatas" in results:
            for meta in results["metadatas"]:
                if meta and meta.get("document_name") == document_name:
                    return True
        return False