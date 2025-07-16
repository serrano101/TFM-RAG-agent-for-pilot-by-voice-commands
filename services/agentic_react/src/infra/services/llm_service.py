from src.infra.config import Config
from langchain_ollama import ChatOllama

class LLMClientOllama:
    def __init__(self, model="mistral:instruct", base_url=None):
        if base_url is None:
            base_url = Config.OLLAMA_SERVICE_URL
        self.llm = ChatOllama(model=model, base_url=base_url)