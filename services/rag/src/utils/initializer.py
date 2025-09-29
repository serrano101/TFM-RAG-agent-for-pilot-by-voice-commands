from __future__ import annotations
import logging
import yaml

from src.embedders.sentence_transformers_embedders import Embedder
from src.database.chromadb_repository import VectorDBRepository
from src.agents.RAG import RAG
from src.llm.ollama_service import LLMClientOllama  # ajusta si tu clase LLM tiene otro nombre/ruta
from src.prompts.open_prompt import open_prompt     # ajusta si tu helper de prompts está en otra ruta

def initialize_services(app):
    logger: logging.Logger = getattr(app.state, "logger", logging.getLogger(__name__))
    if getattr(app.state, "ready", False):
        logger.info("RAG already initialized. Skipping.")
        return {"initialized": True, "skipped": True}

    logger.info("Loading configuration...")
    config = getattr(app.state, "config", None)
    if config is None:
        with open("/app/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        app.state.config = config

    logger.info("Creating Embedder...")
    # Embedder
    embedder_name = config["VECTOR_DB"]["EMBEDDER_NAME"]
    embedder = Embedder(model_name=embedder_name)

    logger.info("Connecting Vector DB...")
    # Vector DB
    db_url = config["VECTOR_DB"]["URL"]
    collection = config["VECTOR_DB"]["COLLECTION_NAME"]
    vector_db = VectorDBRepository(db_path=db_url, collection_name=collection, embedding_function=embedder)

    logger.info("Creating LLM client...")
    # LLM (Ollama)
    base_url = config["LLM"]["URL"]
    model_name = config["LLM"]["MODEL_NAME"]
    temperature = config["LLM"]["TEMPERATURE"]
    top_k = config["LLM"]["TOP_K"]
    top_p = config["LLM"]["TOP_P"]
    llm = LLMClientOllama(model=model_name, base_url=base_url, temperature=temperature, top_k=top_k, top_p=top_p)

    logger.info("Loading prompts and building RAG service...")
    # Prompts
    prompt_rag_path = config["RAG"]["RAG_PROMPT"]
    prompt_content_rag = open_prompt(prompt_path=prompt_rag_path)

    # RAG config
    num_documents = config["RAG"]["NUM_DOCUMENTS"]
    output_no_context_answer = config["RAG"]["OUTPUT_NO_CONTEXT_ANSWER"]
    output_not_match_answer_context = config["RAG"]["OUTPUT_NOT_MATCH_ANSWER_CONTEXT"]

    # Servicio RAG
    rag_service = RAG(
        vector_db=vector_db,
        llm=llm,
        prompt=prompt_content_rag,
        output_no_context_answer=output_no_context_answer,
        output_not_match_answer_context=output_not_match_answer_context,
        k=num_documents
    )

    # Persistir en app.state
    app.state.embedder = embedder
    app.state.vector_db = vector_db
    app.state.llm = llm
    app.state.rag_service = rag_service
    app.state.output_no_context_answer = output_no_context_answer
    app.state.output_not_match_answer_context = output_not_match_answer_context
    app.state.ready = True
    logger.info("RAG services initialized successfully.")
    return {"initialized": True, "skipped": False}