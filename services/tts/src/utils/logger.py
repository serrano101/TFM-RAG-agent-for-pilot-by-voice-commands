
import logging
import os
from datetime import date

def setup_logger(log_level: str) -> None:
    """
    Configura el sistema de logging para el microservicio.

    Crea un archivo de log diario en la carpeta 'logs' y también muestra los logs por consola.
    El nivel de logging se puede ajustar (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Args:
        log_level (str): Nivel de logging como texto ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").

    Returns:
        None
    """
    # Define la carpeta absoluta donde se guardarán los logs (robusto para contenedores)
    directory = "/app/logs/"
    # Si la carpeta no existe, la crea
    if not os.path.exists(directory):
        os.makedirs(directory)
    # Define el nombre del archivo de log con la fecha actual (ej: 2025-8-8.log)
    log_file_root = directory + str(date.today().year) + "-" + str(date.today().month) + "-" + str(date.today().day) + ".log"
    
    # Define el formato de los mensajes de log
    log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    # Configura el logging:
    # - level: nivel de severidad de los mensajes
    # - format: formato de cada línea de log
    # - handlers: dónde se envían los logs (archivo y consola)
    logging.basicConfig(
        level=getattr(logging, log_level, 10),  # Convierte el texto del nivel a valor numérico
        format=log_format,
        handlers=[
            # Guarda los logs en el archivo del día, en modo 'append' (no sobreescribe)
            logging.FileHandler(filename=log_file_root, mode='a'),
            # Muestra los logs en la consola
            logging.StreamHandler()
        ]
    )
