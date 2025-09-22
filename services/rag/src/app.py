import logging, yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.utils.logger import setup_logger
from src.routes import router as bootstrap_router

# --- Load configuration ---
with open("/app/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- Basic Logging Configuration ---
level = config["RUNNING"]["LOG_LEVEL"]
setup_logger(level)
logger = logging.getLogger(__name__)

# --- FastAPI app and state ---
app = FastAPI()
app.state.config = config
app.state.logger = logger
app.state.ready = False  # se pondrá a True tras /warmup

# Monta endpoints de health/ready/warmup
app.include_router(bootstrap_router)
logger.info("RAG routes mounted (healthz/readyz/warmup).")
# Si tienes modelos Pydantic ya definidos, conserva; ejemplo:
class ASRResult(BaseModel):
    transcription: str

# Ejemplo de endpoint que usa rag_service
@app.post("/rag_result")
async def receive_asr_rag_result(request: Request) -> JSONResponse:
    """
    Procesa una transcripción recibida y ejecuta el pipeline RAG para obtener una respuesta.

    Args:
        request (Request): Solicitud HTTP con el JSON que contiene la transcripción.

    Returns:
        JSONResponse: Respuesta con el resultado del pipeline RAG o el error correspondiente.
    """
    if not getattr(request.app.state, "ready", False):
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "message": "RAG not initialized. Call /warmup first."}
        )
    rag_service = request.app.state.rag_service
    output_not_match_answer_context = request.app.state.output_not_match_answer_context

    try:
        logger.info("Esperando resultado de ASR para ser analizado por el RAG...")
        data = await request.json()
        logger.debug(f"Datos recibidos de ASR: {data}")
        transcription = data.get("transcription", "")
    except Exception as e:
        logger.error(f"Error al parsear el JSON de la solicitud: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={"status": "json_error", "message": "Invalid JSON in request body", "response": None}
        )

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
        rag_result = rag_service.execute(query=transcription)
        if not rag_result:
            logger.warning("La ejecución de RAG devolvió un resultado vacío")
            return JSONResponse(
                status_code=500,
                content={"status": "processing_error", "message": "RAG execution failed", "response": None}
            )
        if not rag_result.get("context"):
            logger.warning("La ejecución de RAG no devolvió contexto relevante")
            return JSONResponse(
            status_code=200, 
            content={"status": "no_results", "response": rag_result}
        )
        if rag_result.get("answer") == output_not_match_answer_context:
            logger.warning("La ejecución de RAG indica que la pregunta no coincide con el contexto")
            return JSONResponse(
            status_code=200, 
            content={"status": "no_match", "response": rag_result}
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
# @app.post("/react_agent_result")
# async def receive_asr_react_agent_result(request: Request) -> JSONResponse:
#     """
#     Procesa una transcripción recibida y ejecuta el agente ReAct para obtener una respuesta.

#     Args:
#         request (Request): Solicitud HTTP con el JSON que contiene la transcripción.

#     Returns:
#         JSONResponse: Respuesta con el resultado del agente ReAct o el error correspondiente.
#     """
#     global last_react_agent_result

#     try:
#         try:
#             logger.info("Esperando resultado para ser analizado por el Agente ReAct...")
#             data = await request.json()
#             logger.debug(f"Datos recibidos: {data}")
#         except Exception as e:
#             logger.error(f"Error al parsear el JSON de la solicitud: {str(e)}")
#             return JSONResponse(
#                 status_code=400,
#                 content={"status": "json_error", "message": "Invalid JSON in request body", "response": None}
#             )
        
#         transcription = data.get("transcription", "")
        
#         # Validate transcription
#         if not transcription or not transcription.strip():
#             logger.warning("Se recibió una transcripción vacía")
#             return JSONResponse(
#                 status_code=400,
#                 content={"status": "validation_error", "message": "Transcription cannot be empty", "response": None}
#             )
        
#         logger.info(f"Procesando transcripción: {transcription[:100]}...")
        
#         # Execute React Agent
#         try:
#             react_agent_result = react_agent_service.execute(transcription)
#             if not react_agent_result["output"]:
#                 logger.warning("La ejecución de React Agent devolvió un resultado vacío")
#                 return JSONResponse(
#                     status_code=500,
#                     content={"status": "processing_error", "message": "React Agent execution failed", "response": None}
#                 )

#             last_react_agent_result = react_agent_result

#             return JSONResponse(
#                 status_code=200, 
#                 content={"status": "success", "response": react_agent_result}
#             )

#         except Exception as e:
#             logger.error(f"Error en la ejecución de React Agent: {str(e)}", exc_info=True)
#             return JSONResponse(
#                 status_code=500,
#                 content={"status": "processing_error", "message": f"React Agent execution failed: {str(e)}", "response": None}
#             )
            
#     except Exception as e:
#         logger.error(f"Error inesperado en receive_react_agent_result: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"status": "unexpected_error", "message": f"An unexpected error occurred: {str(e)}", "response": None}
#         )

@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        status_code=200, 
        content={"status": "ok", "message": "Service is healthy"}
    )