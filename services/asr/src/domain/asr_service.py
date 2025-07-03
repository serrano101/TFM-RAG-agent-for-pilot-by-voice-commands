from abc import ABC, abstractmethod

class ASRService(ABC):
    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> str:
        pass