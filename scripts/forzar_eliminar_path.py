import subprocess
def delete_path():
    try:
        path = "/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/services/ingestion/docs"
        subprocess.run(["sudo", "rm", "-rf", path], check=True, capture_output=True, text=True)
        print(f"Path eliminado correctamente: {path}")
    except subprocess.CalledProcessError as e:
        print("Error al eliminar el path:", e)
        print("Salida estándar:", e.stdout)
        print("Error estándar:", e.stderr)
    except Exception as e:
        print("Error inesperado:", e)  

def delete_pycache():
    try:
        subprocess.run(
            ["sudo", "find", ".", "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"],
            check=True, capture_output=True, text=True
        )
        print("Todos los __pycache__ eliminados correctamente.")
    except subprocess.CalledProcessError as e:
        print("Error al eliminar __pycache__:", e)
        print("Salida estándar:", e.stdout)
        print("Error estándar:", e.stderr)
    except Exception as e:
        print("Error inesperado:", e)
    
if __name__ == "__main__":
    delete_path()
    # delete_pycache()