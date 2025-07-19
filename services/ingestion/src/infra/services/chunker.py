# from langchain.text_splitter import RecursiveCharacterTextSplitter
from docling.chunking import HybridChunker
import json
import tiktoken
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
        # Intentar importar tiktoken para contar tokens
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            def count_tokens(text):
                return len(enc.encode(text))
        except ImportError:
            def count_tokens(text):
                return len(text.split())
        MAX_TOKENS = 512
        for i, chunk in enumerate(chunk_iter):
            enriched_text = chunker.contextualize(chunk=chunk)
            # Limita el tamaño del chunk a MAX_TOKENS tokens
            if count_tokens(enriched_text) > MAX_TOKENS:
                # Recorta el texto al límite de tokens
                if 'enc' in locals():
                    tokens = enc.encode(enriched_text)[:MAX_TOKENS]
                    enriched_text = enc.decode(tokens)
                else:
                    enriched_text = ' '.join(enriched_text.split()[:MAX_TOKENS])
            meta = chunk.meta.export_json_dict()
            # Convierte los valores que no sean tipos simples a string
            for k, v in meta.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    meta[k] = json.dumps(v)
            documents.append(enriched_text)
            metadatas.append(meta)
        return documents, metadatas