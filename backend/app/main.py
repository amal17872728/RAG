from fastapi import FastAPI
from app.api.article import router as article_router

app = FastAPI(
    title="Wikipedia RAG API",
    version="1.0.0"
)

app.include_router(article_router)


@app.get("/")
def root():
    return {
        "message": "Wikipedia RAG API is running"
    }