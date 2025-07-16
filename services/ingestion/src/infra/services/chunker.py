# from langchain.text_splitter import RecursiveCharacterTextSplitter
from docling.chunking import HybridChunker
class Chunker:
    # def chunk_langchain(self, text, chunk_size=1000, chunk_overlap=100):
    #     # Elimina espacios en blanco al inicio y final del texto
    #     splitter = RecursiveCharacterTextSplitter(
    #         chunk_size=chunk_size,
    #         chunk_overlap=chunk_overlap,
    #         separators=["\n\n", "\n", " ", ""]
    #     )
    #     # Filtra chunks vacíos o solo con espacios
    #     return splitter.split_text(text)

    def chunk_docling(self, dl_doc):
        # Utiliza HybridChunker de Docling para chunking
        chunker = HybridChunker()
        chunk_iter = chunker.chunk(dl_doc=dl_doc)
        documents, metadatas = [], []
        for i, chunk in enumerate(chunk_iter):
            enriched_text = chunker.contextualize(chunk=chunk)
            documents.append(enriched_text)
            metadatas.append(chunk.meta.export_json_dict())
        return documents, metadatas