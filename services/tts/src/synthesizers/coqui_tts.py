from __future__ import annotations
import logging
import io
import base64
from typing import Optional, Dict, Any, List
import numpy as np
import soundfile as sf
import torch
from TTS.api import TTS

logger = logging.getLogger(__name__)

class CoquiTTS:
    def __init__(self, model_name: str, default_speaker: Optional[str] = None, sample_rate: Optional[int] = None):
        self.model_name = model_name
        self.default_speaker = default_speaker
        self.sample_rate_cfg = sample_rate
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model: Optional[TTS] = None
        self._multi_speaker = False
        self._speaker_ids: List[str] | None = None

    def load(self):
        if self._model:
            return
        logger.info(f"[CoquiTTS] Loading model '{self.model_name}' on device={self.device}")
        self._model = TTS(self.model_name).to(self.device)
        try:
            speakers = getattr(self._model, "speakers", None)
            if speakers:
                self._multi_speaker = True
                self._speaker_ids = list(speakers)
                logger.info(f"[CoquiTTS] Multi-speaker model. Speakers (first 10): {self._speaker_ids[:10]}")
            else:
                logger.info("[CoquiTTS] Single-speaker model.")
        except Exception:
            logger.debug("[CoquiTTS] Unable to read speakers (assuming single-speaker).")
        if self.sample_rate_cfg:
            logger.info(f"[CoquiTTS] Forced sample_rate={self.sample_rate_cfg}")

    def list_speakers(self) -> list[str]:
        return self._speaker_ids or []

    def synthesize(self, text: str, speaker: Optional[str] = None) -> Dict[str, Any]:
        if not self._model:
            raise RuntimeError("Model not loaded. Call load() first.")
        chosen_speaker = speaker or self.default_speaker
        if self._multi_speaker and chosen_speaker and self._speaker_ids and chosen_speaker not in self._speaker_ids:
            raise ValueError(f"Speaker '{chosen_speaker}' not available.")
        logger.info(f"[CoquiTTS] Synthesizing len={len(text)} speaker={chosen_speaker}")
        if self._multi_speaker and chosen_speaker:
            wav = self._model.tts(text, speaker=chosen_speaker)
        else:
            wav = self._model.tts(text)
        wav = np.array(wav, dtype=np.float32)
        sr = self.sample_rate_cfg or getattr(self._model, "output_sample_rate", 22050)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        buf.seek(0)
        duration = len(wav) / float(sr)
        return {
            "wav_bytes": buf.getvalue(),
            "sample_rate": sr,
            "duration": duration,
            "speaker": chosen_speaker,
        }

    def warmup(self, text: str):
        try:
            logger.info("[CoquiTTS] Warmup start...")
            _ = self.synthesize(text)
            logger.info("[CoquiTTS] Warmup done.")
        except Exception as e:
            logger.warning(f"[CoquiTTS] Warmup failed: {e}")