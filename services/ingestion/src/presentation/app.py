from dotenv import load_dotenv
import os
from src.presentation.components.ingest_runner import run_ingestion


def main():
    load_dotenv()
    pdf_folder = os.getenv("PDF_FOLDER", "/../../../../../docs/dataset_procedures")
    vector_db_folder = os.getenv("VECTOR_DB_FOLDER", "/../../../../../common/vector_db")
    run_ingestion(pdf_folder, vector_db_folder)


if __name__ == "__main__":
    main()