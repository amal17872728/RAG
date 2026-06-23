from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.article import router as article_router
from app.api.summary import router as summary_router
from app.api.ask import router as ask_router
from app.api.ingest import router as ingest_router

app = FastAPI(
    title="Wikipedia RAG API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
