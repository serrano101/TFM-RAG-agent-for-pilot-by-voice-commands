import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.utils.initializer import initialize_services

router = APIRouter()

@router.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})

@router.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    logger = getattr(request.app.state, "logger", logging.getLogger("rag.routes"))
    ready = bool(getattr(request.app.state, "ready", False))
    logger.debug(f"GET /readyz -> ready={ready}")
    return JSONResponse(status_code=200, content={"ready": ready})

@router.post("/warmup")
def warmup(request: Request) -> JSONResponse:
    logger = getattr(request.app.state, "logger", logging.getLogger("rag.routes"))
    try:
        logger.info("POST /warmup received. Initializing RAG dependencies...")
        result = initialize_services(request.app)
        logger.info(f"/warmup completed: {result}")
        return JSONResponse(status_code=200, content={"status": "ok", **result})
    except Exception as e:
        logger.exception("Warmup failed")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})