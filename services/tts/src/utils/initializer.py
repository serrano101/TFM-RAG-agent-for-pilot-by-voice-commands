from __future__ import annotations
import asyncio
import logging
import yaml
import os
from typing import Any, Dict
from src.synthesizers.coqui_tts import CoquiTTS

async def initialize_services(app) -> Dict[str, Any]:
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

        logger: logging.Logger = getattr(app.state, "logger", logging.getLogger("tts.app"))
        app.state.initializing = True
        try:
            config = getattr(app.state, "config", None)
            if config is None:
                with open("/app/config.yaml", "r") as f:
                    config = yaml.safe_load(f)
                app.state.config = config

            tcfg = config["TTS"]
            model_name = tcfg.get("MODEL_NAME")
            default_speaker = tcfg.get("DEFAULT_SPEAKER")
            sample_rate = tcfg.get("SAMPLE_RATE")
            warmup_text = tcfg.get("WARMUP_TEXT", "Warmup.")
            logger.info(f"Initializing CoquiTTS model={model_name}")

            engine = CoquiTTS(
                model_name=model_name,
                default_speaker=default_speaker,
                sample_rate=sample_rate
            )
            engine.load()
            engine.warmup(warmup_text)

            app.state.tts_engine = engine
            app.state.ready = True
            logger.info("TTS initialized successfully.")
            return {"initialized": True, "skipped": False}
        finally:
            app.state.initializing = False