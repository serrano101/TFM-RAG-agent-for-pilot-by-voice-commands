from fastapi import FastAPI
from pydantic import BaseModel
from common.embedders.embedders import MpnetBaseEmbedder
from src.infra.repositories.vector_db_repository import VectorDBRepository
from src.application.usecases.process_query import ReActAgentService
from src.infra.services.llm_service import LLMClientOllama
# from langchain_community.chat_models import ChatOllama

app = FastAPI()

class ASRResult(BaseModel):
    transcription: str

# Instanciación real de dependencias (ajusta según tu inicialización real)
embedder = MpnetBaseEmbedder()  # Sustituye por tu modelo real
vector_db = VectorDBRepository()  # Sustituye por tu cliente real
llm = LLMClientOllama()
usecase = ReActAgentService(embedder, vector_db, llm.llm)

from fastapi import Request
from fastapi.responses import JSONResponse


# Variable global para guardar el último resultado
last_agentic_result = None

# POST: procesa una transcripción
from fastapi import Request
@app.post("/agentic_result")
async def receive_asr_result(request: Request):
    global last_agentic_result
    data = await request.json()
    transcription = data.get("transcription", "")
    rag_result = usecase.execute(transcription)
    response = {
        "response": rag_result.response,
        "steps": [
            {
                "thought": step.thought,
                "action": step.action,
                "observation": step.observation,
                "tool_used": step.tool_used,
                "tool_input": step.tool_input,
                "tool_output": step.tool_output,
                "metadata": step.metadata,
            }
            for step in (rag_result.steps or [])
        ],
        "success": getattr(rag_result, "success", True),
        "error": getattr(rag_result, "error", None),
    }
    last_agentic_result = response
    return JSONResponse(content={"status": "processed", "response": last_agentic_result})

# GET: devuelve el último resultado procesado
@app.get("/agentic_result")
def get_agentic_last_result():
    global last_agentic_result
    if last_agentic_result is not None:
        return {"status": "last_result", "response": last_agentic_result}
    else:
        return {"status": "empty", "response": None}

@app.get("/health")
def health():
    return {"status": "ok"}