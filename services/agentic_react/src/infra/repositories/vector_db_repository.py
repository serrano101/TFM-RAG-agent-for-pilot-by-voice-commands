from src.infra.config import Config
import chromadb

class VectorDBRepository:
    def __init__(self):
        # Inicializa el cliente ChromaDB usando la URL HTTP si está definida
        if hasattr(Config, "VECTOR_DB_URL") and Config.VECTOR_DB_URL.startswith("http"):
            self.client = chromadb.HttpClient(host=Config.VECTOR_DB_URL)
        else:
            self.client = chromadb.PersistentClient(path=getattr(Config, "VECTOR_DB_PATH", "/app/common/vector_db"))
        # Ajusta el nombre de la colección según tu proyecto
        self.collection = self.client.get_or_create_collection("documentos")

    def search_embedding(self, embedding, top_k=5):
        # Realiza la búsqueda en la colección de ChromaDB
        results = self.collection.query(query_embeddings=[embedding], n_results=top_k)
        # Devuelve los documentos encontrados (ajusta según tu estructura)
        return results.get("documents", [])
    def search_text(self, text, top_k=5):
        # Realiza la búsqueda en la colección de ChromaDB
        results = self.collection.query(query_texts=[text], n_results=top_k)
        # Devuelve los documentos encontrados (ajusta según tu estructura)
        return results.get("documents", [])