# --- Load configuration ---
import yaml
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- Basic Logging Configuration ---
import logging
from src.utils.logger import setup_logger
level = config["RUNNING"]["LOG_LEVEL"]
setup_logger(level)
logger = logging.getLogger(__name__)

# --- FastAPI Application Setup ---
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse

# --- Imports ---
from src.embedders.sentence_transformers_embedders import Embedder
from src.database.chromadb_repository import VectorDBRepository
from src.agents.RAG import RAG
from src.agents.ReActAgent import ReActAgentService
from src.llm.ollama_service import LLMClientOllama
from src.prompts.open_prompt import open_prompt

# --- Initialize Dependencies ---
try:
    logger.info("Inicializando dependencias de la aplicación")

    # Embedder
    embedder_name = config["VECTOR_DB"]["EMBEDDER_NAME"]
    embedder = Embedder(model_name=embedder_name)
    
    # Base de datos vectorial --> chromadb
    db_path = config["VECTOR_DB"]["URL"]
    collection_name = config["VECTOR_DB"]["COLLECTION_NAME"]
    vector_db = VectorDBRepository(db_path=db_path, collection_name=collection_name, embedding_function=embedder)

    # LLM
    base_url = config["LLM"]["URL"]
    # llm_name = config["LLM"]["MODEL_NAME"]
    llm_name = config["LLM"]["OLLAMA"]    
    llm = LLMClientOllama(model=llm_name, base_url=base_url)
    
    # Inicializa el agente ReAct
    prompt_react_agent_path = config["RAG"]["REACT_AGENT_PROMPT"]    
    prompt_content_react_agent = open_prompt(prompt_path=prompt_react_agent_path)
    react_agent_service = ReActAgentService(
        # embedder, 
        vector_db = vector_db, 
        llm = llm, 
        prompt = prompt_content_react_agent
    )

    # Iniciliza el servicio de RAG
    prompt_rag_path = config["RAG"]["RAG_PROMPT"]
    prompt_rag_extract_heading_path = config["RAG"]["RAG_EXTRACT_HEADING_PROMPT"]
    prompt_content_rag = open_prompt(prompt_path=prompt_rag_path)
    prompt_content_rag_extract_heading = open_prompt(prompt_path=prompt_rag_extract_heading_path)
    search_type = config["RAG"]["SEARCH_TYPE"]
    search_kwargs = config["RAG"]["SEARCH_KWARGS"]
    rag_service = RAG(
        # embedder, 
        vector_db = vector_db,
        llm = llm,
        prompt = prompt_content_rag,
        prompt_heading = prompt_content_rag_extract_heading,
        search_type = search_type,
        search_kwargs = search_kwargs
    )

except Exception as e:
    logger.error(f"Error al inicializar las dependencias de la aplicación: {str(e)}", exc_info=True)
    raise RuntimeError(f"Application initialization failed: {str(e)}")


# --- Instancia de la aplicación FastAPI ---
app = FastAPI()

# Clase para el resultado de ASR
class ASRResult(BaseModel):
    transcription: str

# Variable global para guardar el último resultado
last_react_agent_result = None
last_rag_result = None

# POST: procesa una transcripción y ejecuta el RAG
@app.post("/rag_result")
async def receive_asr_rag_result(request: Request) -> JSONResponse:
    """
    Procesa una transcripción recibida y ejecuta el pipeline RAG para obtener una respuesta.

    Args:
        request (Request): Solicitud HTTP con el JSON que contiene la transcripción.

    Returns:
        JSONResponse: Respuesta con el resultado del pipeline RAG o el error correspondiente.
    """
    global last_rag_result

    try:
        logger.info("Esperando resultado de ASR para ser analizado por el RAG...")
        data = await request.json()
        logger.debug(f"Datos recibidos de ASR: {data}")
    except Exception as e:
        logger.error(f"Error al parsear el JSON de la solicitud: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={"status": "json_error", "message": "Invalid JSON in request body", "response": None}
        )

    transcription = data.get("transcription", "")

    # Validate transcription
    if not transcription or not transcription.strip():
        logger.warning("Se recibió una transcripción vacía")
        return JSONResponse(
            status_code=400,
            content={"status": "validation_error", "message": "Transcription cannot be empty", "response": None}
        )

    logger.info(f"Procesando transcripción: {transcription[:100]}...")

    # Execute RAG
    try:
        rag_result = rag_service.execute(transcription, use_custom_search = False)
        last_rag_result = rag_result
        if not rag_result:
            logger.warning("La ejecución de RAG devolvió un resultado vacío")
            return JSONResponse(
                status_code=500,
                content={"status": "processing_error", "message": "RAG execution failed", "response": None}
            )
        if not rag_result.get("context"):
            rag_result["context"] = None            
            return JSONResponse(
                status_code=422,
                content={"status": "no_results", "message": "No relevant documents found.", "response": rag_result}
            )
        return JSONResponse(
            status_code=200, 
            content={"status": "success", "response": rag_result}
        )

    except Exception as e:
        logger.error(f"Error en la ejecución de RAG: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "processing_error", "message": f"RAG execution failed: {str(e)}", "response": None}
        )

# POST: recibe el resultado de ASR y lo procesa por un agente ReAct
@app.post("/react_agent_result")
async def receive_asr_react_agent_result(request: Request) -> JSONResponse:
    """
    Procesa una transcripción recibida y ejecuta el agente ReAct para obtener una respuesta.

    Args:
        request (Request): Solicitud HTTP con el JSON que contiene la transcripción.

    Returns:
        JSONResponse: Respuesta con el resultado del agente ReAct o el error correspondiente.
    """
    global last_react_agent_result

    try:
        try:
            logger.info("Esperando resultado para ser analizado por el Agente ReAct...")
            data = await request.json()
            logger.debug(f"Datos recibidos: {data}")
        except Exception as e:
            logger.error(f"Error al parsear el JSON de la solicitud: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={"status": "json_error", "message": "Invalid JSON in request body", "response": None}
            )
        
        transcription = data.get("transcription", "")
        
        # Validate transcription
        if not transcription or not transcription.strip():
            logger.warning("Se recibió una transcripción vacía")
            return JSONResponse(
                status_code=400,
                content={"status": "validation_error", "message": "Transcription cannot be empty", "response": None}
            )
        
        logger.info(f"Procesando transcripción: {transcription[:100]}...")
        
        # Execute React Agent
        try:
            react_agent_result = react_agent_service.execute(transcription)
            if not react_agent_result["output"]:
                logger.warning("La ejecución de React Agent devolvió un resultado vacío")
                return JSONResponse(
                    status_code=500,
                    content={"status": "processing_error", "message": "React Agent execution failed", "response": None}
                )

            last_react_agent_result = react_agent_result

            return JSONResponse(
                status_code=200, 
                content={"status": "success", "response": react_agent_result}
            )

        except Exception as e:
            logger.error(f"Error en la ejecución de React Agent: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "processing_error", "message": f"React Agent execution failed: {str(e)}", "response": None}
            )
            
    except Exception as e:
        logger.error(f"Error inesperado en receive_react_agent_result: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "unexpected_error", "message": f"An unexpected error occurred: {str(e)}", "response": None}
        )

# GET: devuelve el último resultado procesado para el Agente ReAct
@app.get("/react_last_result")
def get_react_last_result() -> JSONResponse:
    """
    Devuelve el último resultado procesado por el agente ReAct.

    Returns:
        JSONResponse: Último resultado disponible o estado vacío/error.
    """
    try:
        logger.info("Solicitud para último resultado React recibida")
        global last_react_agent_result

        if last_react_agent_result is not None:
            logger.info("Devolviendo el último resultado React")
            return JSONResponse(
                status_code=200, 
                content={"status": "last_result", "response": last_react_agent_result}
            )
        else:
            logger.info("No hay resultado previo disponible")
            return JSONResponse(
                status_code=200, 
                content={"status": "empty", "response": None}
            )

    except Exception as e:
        logger.error(f"Error al recuperar el último resultado: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to retrieve last result: {str(e)}", "response": None}
        )

# GET: devuelve el último resultado procesado para el RAG
@app.get("/rag_last_result")
def get_rag_last_result() -> JSONResponse:
    """
    Devuelve el último resultado procesado por el pipeline RAG.

    Returns:
        JSONResponse: Último resultado disponible o estado vacío/error.
    """
    try:
        logger.info("Solicitud para último resultado RAG recibida")
        global last_rag_result

        if last_rag_result is not None:
            logger.info("Devolviendo el último resultado RAG")
            return JSONResponse(
                status_code=200, 
                content={"status": "last_result", "response": last_rag_result}
            )
        else:
            logger.info("No hay resultado previo disponible")
            return JSONResponse(
                status_code=200, 
                content={"status": "empty", "response": None}
            )

    except Exception as e:
        logger.error(f"Error al recuperar el último resultado: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to retrieve last result: {str(e)}", "response": None}
        )

@app.get("/health")
def health() -> JSONResponse:
    """
    Endpoint de health check para comprobar el estado del servicio.

    Returns:
        JSONResponse: Estado de salud del servicio.
    """
    try:
        logger.debug("Solicitud de health check recibida")
        return JSONResponse(
            status_code=200, 
            content={"status": "ok", "message": "Service is healthy"}
        )
    except Exception as e:
        logger.error(f"Error en el health check: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Health check failed: {str(e)}"}
        )