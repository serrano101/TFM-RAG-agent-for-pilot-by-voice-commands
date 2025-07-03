from src.domain.asr_service import ASRService

def transcribe_audio(audio_bytes: bytes, asr_service: ASRService) -> str:
    return asr_service.transcribe(audio_bytes)