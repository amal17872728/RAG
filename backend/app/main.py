from fastapi import FastAPI
from app.api.article import router as article_router
from app.api.summary import router as summary_router

app = FastAPI(
    title="Wikipedia RAG API",
    version="1.0.0"
)

app.include_router(article_router)
app.include_router(summary_router)


@app.get("/")
def root():
    return {
        "message": "Wikipedia RAG API is running"
    }