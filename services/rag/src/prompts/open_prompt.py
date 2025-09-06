import logging

# Obtiene un logger para el módulo actual
logger = logging.getLogger(__name__)

def open_prompt(prompt_path: str) -> str:
    """
    Abre un archivo de prompt y devuelve su contenido como string.

    Args:
        prompt_path (str): Ruta al archivo del prompt.

    Returns:
        str: Contenido del prompt como cadena de texto.

    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta indicada.
        RuntimeError: Si ocurre cualquier otro error al leer el archivo.
    """
    try:
        with open(prompt_path, 'r') as file:
            prompt_content = file.read()
        logger.debug(f"Prompt cargado correctamente desde {prompt_path}, longitud: {len(prompt_content)} caracteres")
        return prompt_content
    except FileNotFoundError:
        logger.error(f"Archivo de prompt no encontrado: {prompt_path}")
        raise FileNotFoundError(f"Archivo de prompt no encontrado: {prompt_path}")
    except Exception as e:
        logger.error(f"Error al cargar el archivo de prompt: {str(e)}")
        raise RuntimeError(f"Error al cargar el archivo de prompt: {str(e)}")