from langchain_core.prompts import PromptTemplate
from langchain_docling.loader import ExportType
from docling.chunking import HybridChunker
from langchain_docling import DoclingLoader
from docling.chunking import HybridChunker

# CONFIG INICIAL
FILE_PATH = ["/home/serrano101/projects/TFM-RAG-agent-for-pilot-by-voice-commands/docs/dataset_procedures/FBW A32NX SOP.pdf"]  # Docling Technical Report
EXPORT_TYPE = ExportType.MARKDOWN
QUESTION = "Information about the Aircraft Setup"
PROMPT = PromptTemplate.from_template(
    "Context information is below.\n---------------------\n{context}\n---------------------\nGiven the context information and not prior knowledge, answer the query.\nQuery: {input}\nAnswer:\n",
)
TOP_K = 5

# OBTENER EL CONTENIDO DEL TEXTO Y HACER CHUNKING
loader = DoclingLoader(
    file_path=FILE_PATH,
    export_type=EXPORT_TYPE,
    chunker=HybridChunker(),
)

docs = loader.load()

# OBTENER DE FORMA CORRECTA LOS CHUNKS
if EXPORT_TYPE == ExportType.DOC_CHUNKS:
    splits = docs
elif EXPORT_TYPE == ExportType.MARKDOWN:
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "Header_1"),
            ("##", "Header_2"),
            ("###", "Header_3"),
        ],
    )
    splits = [split for doc in docs for split in splitter.split_text(doc.page_content)]
else:
    raise ValueError(f"Unexpected export type: {EXPORT_TYPE}")
for d in splits[:3]:
    print(f"- {d.page_content=}")
print("...")

# DB 