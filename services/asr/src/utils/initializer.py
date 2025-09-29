from __future__ import annotations
import asyncio
import logging
import yaml
from src.transcribers.whisper import ASRWhisper

async def initialize_services(app):
    """
    Idempotente. Inicializa ASRWhisper y lo guarda en app.state.asr_service.
    Marca app.state.ready = True.
    """
    # Si ya está listo, no rehacer
    if getattr(app.state, "ready", False):
        return {"initialized": True, "skipped": True}

    # Lock de inicialización (singleton en app.state)
    lock = getattr(app.state, "init_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        app.state.init_lock = lock

    async with lock:
        # Doble verificación tras adquirir el lock
        if getattr(app.state, "ready", False):
            return {"initialized": True, "skipped": True}

        app.state.initializing = True
        logger: logging.Logger = getattr(app.state, "logger", logging.getLogger("src.app"))
        try:
            config = getattr(app.state, "config", None)
            if config is None:
                with open("/app/config.yaml", "r") as f:
                    config = yaml.safe_load(f)
                app.state.config = config

            logger.info("Inicializando ASRWhisper...")
            model_name = config["ASR"]["WHISPER_MODEL_NAME"]
            asr_service = ASRWhisper(model_name=model_name)

            app.state.asr_service = asr_service
            app.state.ready = True
            logger.info("ASR inicializado correctamente.")
            return {"initialized": True, "skipped": False}
        finally:
            app.state.initializing = False