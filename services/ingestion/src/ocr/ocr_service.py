# import fitz  # PyMuPDF
# import pytesseract
# from PIL import Image
# from docling.document_converter import DocumentConverter
import logging
from docling.document_converter import DocumentConverter
from docling_core.types import DoclingDocument

# import io
logger = logging.getLogger(__name__)

class OCRService:
    """
    Servicio OCR que convierte archivos en documentos estructurados usando docling.
    """
    def __init__(self):
        self.converter = DocumentConverter()
        
    # def extract_text(self, pdf_path):
    #     doc = fitz.open(pdf_path)
    #     page_texts = []
    #     for i, page in enumerate(doc):
    #         page_text = page.get_text()
    #         if not page_text.strip():
    #             pix = page.get_pixmap()
    #             img = Image.open(io.BytesIO(pix.tobytes()))
    #             page_text = pytesseract.image_to_string(img)
    #         page_texts.append((i + 1, page_text))  # (número de página, texto)
    #     return page_texts
    def convert_document(self, file_path: str) -> DoclingDocument:
        """
        Convierte un archivo en un DoclingDocument estructurado usando docling.

        Args:
            file_path (str): Ruta al archivo a convertir.

        Returns:
            DoclingDocument: Documento estructurado resultante.

        Manejo de errores:
            - Si ocurre un error en la conversión, se registra con logger.error y se lanza una excepción RuntimeError.
        """
        try:
            logger.info(f"[OCRService] Convirtiendo archivo a documento: {file_path}")
            document = self.converter.convert(file_path).document
            logger.info(f"[OCRService] Archivo convertido a documento: {file_path}")
            return document
        except Exception as e:
            logger.error(f"[OCRService] Error al convertir el archivo '{file_path}': {e}", exc_info=True)
            raise RuntimeError(f"[OCRService] Error al convertir el archivo '{file_path}': {e}") from e