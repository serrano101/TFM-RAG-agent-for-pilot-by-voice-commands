import yaml
import logging
from langchain_chroma.vectorstores import Chroma
from urllib.parse import urlparse
# Configurar el logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> dict:
    """
    Carga la configuración desde un archivo YAML.

    Args:
        config_path (str): Ruta al archivo de configuración.

    Returns:
        dict: Configuración cargada.
    """
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Error al cargar la configuración: {e}")
        raise RuntimeError(f"No se pudo cargar la configuración: {e}")

def delete_collection(db_url: str, collection_name: str) -> None:
    """
    Elimina una colección de ChromaDB utilizando la clase Chroma.

    Args:
        db_url (str): URL del servicio ChromaDB.
        collection_name (str): Nombre de la colección a eliminar.

    Returns:
        None
    """
    try:
        logger.info(f"Conectando a ChromaDB en '{db_url}' para eliminar la colección '{collection_name}'...")
        
        # Inicializar la conexión con ChromaDB
        if not (db_url.startswith("http://") or db_url.startswith("https://")):
            raise ValueError("db_url debe ser una URL HTTP para ChromaDB remoto (microservicio)")
        parsed = urlparse(db_url)
        host = parsed.hostname
        port = parsed.port or 8000  # Usa 8000 por defecto si no está en la URL
        
        chroma_instance = Chroma(
            collection_name=collection_name,
            host=host,
            port=port
        )

        # Eliminar la colección
        chroma_instance.delete_collection()
        logger.info(f"Colección '{collection_name}' eliminada correctamente.")
    except Exception as e:
        logger.error(f"Error al eliminar la colección '{collection_name}': {e}")
        raise RuntimeError(f"No se pudo eliminar la colección: {e}")

if __name__ == "__main__":
    # Ruta al archivo de configuración
    config_path = "/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/infrastructure/config.yaml"

    # Cargar configuración
    config = load_config(config_path)

    # Obtener parámetros de la configuración
    db_url = "http://localhost:8003"
    collection_name = config["VECTOR_DB"]["COLLECTION_NAME"]

    # Eliminar la colección
    delete_collection(db_url, collection_name)