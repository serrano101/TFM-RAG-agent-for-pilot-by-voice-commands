# from langchain.text_splitter import RecursiveCharacterTextSplitter

from docling.chunking import HybridChunker
import json
import os
import tiktoken
import logging
from docling_core.types import DoclingDocument
from typing import List, Tuple, Dict
import fitz  # PyMuPDF
logger = logging.getLogger(__name__)

class Chunker:
    """
    Clase para dividir documentos Docling en chunks de texto y metadatos usando Docling HybridChunker.
    """
    def __init__(self):
        self.chunker = HybridChunker()

    # def chunk_langchain(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    #     """
    #     Divide un texto plano en chunks usando LangChain.
    #
    #     Args:
    #         text (str): Texto a dividir.
    #         chunk_size (int): Tamaño máximo de cada chunk.
    #         chunk_overlap (int): Número de tokens de solapamiento entre chunks.
    #
    #     Returns:
    #         List[str]: Lista de chunks de texto.
    #     """
    #     ...existing code...

    def chunk_docling(self, dl_doc: DoclingDocument) -> Tuple[List[str], List[Dict]]:
        """
        Divide un DoclingDocument en chunks de texto enriquecido y metadatos.

        Args:
            dl_doc (DoclingDocument): Documento estructurado de docling a chunkear.

        Returns:
            Tuple[List[str], List[dict]]: Una tupla con la lista de chunks de texto y la lista de metadatos asociados.

        Manejo de errores:
            - Si ocurre un error durante el chunking, se registra con logger.error y se lanza una excepción RuntimeError.
        """
        try:
            logger.info(f"[Chunker] Iniciando chunking del documento...")
            # Utiliza HybridChunker de Docling para chunking
            chunk_iter = self.chunker.chunk(dl_doc=dl_doc)
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
                enriched_text = self.chunker.contextualize(chunk=chunk)
                logger.debug(f"[Chunker] Chunk {i+1}: {enriched_text[:50]}... (tokens: {count_tokens(enriched_text)})")
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
                logger.debug(f"[Chunker] Metadatos del chunk {i+1}: {meta}")
                documents.append(enriched_text)
                metadatas.append(meta)
            logger.info(f"[Chunker] Documento chunked correctamente. Chunks generados: {len(documents)}")
            return documents, metadatas
        except Exception as e:
            logger.error(f"[Chunker] Error al chunkear el documento: {e}", exc_info=True)
            raise RuntimeError(f"[Chunker] Error al chunkear el documento: {e}") from e

    def chunk_pymupdf(self, pdf_path:str) -> Tuple[List[str], List[Dict]]:
        chunks = []
        metadata = []
        chunk_index = 0
        current_procedure = None
        current_section = None
        procedure_data = {}
        filename = os.path.basename(pdf_path)

        try:
            doc = fitz.open(pdf_path)

            for page_number, page in enumerate(doc, start=1):
                lines = page.get_text("text").split("\n")

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith("PROCEDURE:"):
                        # Guardar procedimiento anterior
                        if current_procedure and procedure_data:
                            content_str = f"PROCEDURE: {current_procedure}\n\n"
                            for section, values in procedure_data.items():
                                content_str += f"{section}:\n"
                                for v in values:
                                    content_str += f" {v}\n"
                                content_str += "\n"  # salto de línea extra entre secciones

                            chunks.append(content_str.strip())
                            metadata.append({
                                "procedure": current_procedure,
                                "page_number": page_number,
                                "chunk_index": chunk_index,
                                "filename": filename
                            })
                            chunk_index += 1

                        # Nuevo procedimiento
                        current_procedure = line.replace("PROCEDURE:", "").strip()
                        procedure_data = {}
                        current_section = None

                    elif line.endswith(":"):  # Ej: CONDITIONS:, STEPS:, NOTES:
                        current_section = line.replace(":", "").strip()
                        procedure_data[current_section] = []

                    else:
                        if current_section:
                            procedure_data[current_section].append(line)

            # Guardar el último procedimiento
            if current_procedure and procedure_data:
                content_str = f"PROCEDURE: {current_procedure}\n\n"
                for section, values in procedure_data.items():
                    content_str += f"{section}:\n"
                    for v in values:
                        content_str += f" {v}\n"
                    content_str += "\n"

                chunks.append(content_str.strip())
                metadata.append({
                    "procedure": current_procedure,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "filename": filename
                })

        except Exception as e:
            print(f"[ERROR] Error parsing {pdf_path}: {e}")

        return chunks, metadata

