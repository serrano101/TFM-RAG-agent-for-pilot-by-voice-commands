# import fitz  # PyMuPDF
# import pytesseract
# from PIL import Image
from docling.document_converter import DocumentConverter
import io

class OCRService:
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
    def convert_document(self, file_path):
        converter = DocumentConverter()
        return converter.convert(file_path).document