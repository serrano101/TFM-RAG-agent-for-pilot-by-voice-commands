import chromadb

client = chromadb.PersistentClient(path="/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/common/vector_db")
collection = client.get_or_create_collection("documentos")
results = collection.get()  # Obtiene todos los documentos

print("Número de documentos:", len(results["ids"]))

# Mostrar los primeros 5 ejemplos completos
for i in range(min(10, len(results["ids"]))):
    print(f"\nEjemplo {i+1}:")
    print("ID:", results["ids"][i])
    print("Texto:", results["documents"][i])
    if "metadatas" in results and results["metadatas"]:
        print("Metadata:", results["metadatas"][i])