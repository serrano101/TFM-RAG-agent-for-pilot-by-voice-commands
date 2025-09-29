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
    return JSONResponse(
        status_code=200,
        content={
            "ready": bool(getattr(request.app.state, "ready", False)),
            "initializing": bool(getattr(request.app.state, "initializing", False)),
        },
    )

@router.post("/warmup")
async def warmup(request: Request) -> JSONResponse:
    logger = getattr(request.app.state, "logger", logging.getLogger("src.app"))
    try:
        logger.info("POST /warmup recibido")
        result = await initialize_services(request.app)
        logger.info(f"/warmup -> {result}")
        return JSONResponse(status_code=200, content={"status": "ok", **result})
    except Exception as e:
        logger.exception("Warmup falló")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})