import subprocess

db_path = "/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/common/vector_db/*"

try:
    result = subprocess.run(["sudo", "rm", "-rf", db_path], check=True, capture_output=True, text=True)
    print("Base de datos ChromaDB eliminada completamente.")
except subprocess.CalledProcessError as e:
    print("Error al eliminar la base de datos:", e)
    print("Salida estándar:", e.stdout)
    print("Error estándar:", e.stderr)