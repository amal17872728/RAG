from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.article import router as article_router
from app.api.summary import router as summary_router
from app.api.ask import router as ask_router
from app.api.ingest import router as ingest_router
from app.core.config import settings

app = FastAPI(
    title="Wikipedia RAG API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(article_router)
app.include_router(summary_router)
app.include_router(ask_router)
app.include_router(ingest_router)


@app.get("/")
def root():
    return {
        "message": "Wikipedia RAG API is running"
    }


@app.get("/config")
def public_config():
    return {
        "enable_streaming": settings.enable_streaming,
        "enable_background_ingestion": settings.enable_background_ingestion,
    }
