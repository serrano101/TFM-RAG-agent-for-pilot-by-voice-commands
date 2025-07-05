from langchain.text_splitter import RecursiveCharacterTextSplitter

class Chunker:
    def chunk(self, text, chunk_size=1000, chunk_overlap=100):
        # Elimina espacios en blanco al inicio y final del texto
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
        # Filtra chunks vacíos o solo con espacios
        return splitter.split_text(text)