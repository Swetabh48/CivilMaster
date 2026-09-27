from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import assignments, auth, corpus
from app.core.config import get_settings
from app.database import init_db

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="CivilMaster API",
    description="Formula-verified Civil Engineering assignment solver",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def on_startup() -> None:
    Path(settings.resolved_upload_dir()).mkdir(parents=True, exist_ok=True)
    Path(settings.resolved_corpus_dir()).mkdir(parents=True, exist_ok=True)
    init_db()


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    adapter = settings.resolved_lora_adapter_path()
    llm_backend = "registry"
    lora_ready = adapter is not None
    ollama_ok = False
    try:
        import httpx

        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=1.5)
        ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False
    if lora_ready:
        try:
            import torch

            if torch.cuda.is_available():
                llm_backend = "lora"
            elif ollama_ok:
                llm_backend = "ollama"
            else:
                llm_backend = "registry"
        except Exception:
            llm_backend = "ollama" if ollama_ok else "registry"
    elif ollama_ok:
        llm_backend = "ollama"
    return {
        "status": "ok",
        "service": "civilmaster",
        "llm_backend": llm_backend,
        "lora_adapter": str(adapter) if adapter else None,
        "ollama": ollama_ok,
        "ocr_enabled": settings.ocr_enabled,
    }


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


app.include_router(auth.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(corpus.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
