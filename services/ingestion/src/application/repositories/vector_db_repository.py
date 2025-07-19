from abc import ABC, abstractmethod

class VectorDBRepository(ABC):
    @abstractmethod
    def add_chunks(self, chunks, metadatas):
        pass

    @abstractmethod
    def is_document_processed(self, document_name):
        pass