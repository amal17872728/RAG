from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

from app.services.scraper import extract_wikipedia_article
from app.services.chunker import chunk_text
from app.services.embedder import generate_embedding, generate_embeddings
from app.services.vector_store import (
    create_collection,
    article_exists,
    store_chunks
)
from app.services.llm import summarize_article

router = APIRouter()


class IngestRequest(BaseModel):
    url: str


@router.post("/ingest")
def ingest(req: IngestRequest):
    url = req.url

    article = extract_wikipedia_article(url)

    if "error" in article:
        raise HTTPException(status_code=400, detail=article["error"])

    if article_exists(url):
        return {"status": "exists", "message": "Article already ingested", "title": article.get("title")}

    chunks = chunk_text(article.get("content", ""))

    if not chunks:
        raise HTTPException(status_code=400, detail="No article content to ingest")

    points = []

    # Try batched concurrent embeddings with cache; fallback to sync per-chunk if it fails
    try:
        embs = generate_embeddings(chunks, concurrency=8)

        if not embs or not embs[0]:
            raise RuntimeError("Empty embeddings returned from batch call")

        create_collection(len(embs[0]))

        for i, chunk in enumerate(chunks):
            emb = embs[i]
            points.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{i}")),
                "vector": emb,
                "text": chunk,
                "title": article.get("title"),
                "chunk_number": i,
                "url": url
            })

    except Exception as exc:
        # Fallback: synchronous embedding per chunk
        print(f"Batched embeddings failed, falling back to sync: {exc}")
        first_embedding = generate_embedding(chunks[0])
        create_collection(len(first_embedding))

        for i, chunk in enumerate(chunks):
            emb = generate_embedding(chunk)
            points.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{i}")),
                "vector": emb,
                "text": chunk,
                "title": article.get("title"),
                "chunk_number": i,
                "url": url
            })

    store_chunks(points)

    summary = summarize_article(article.get("content", ""))

    return {
        "status": "ok",
        "title": article.get("title"),
        "summary": summary,
        "chunks_stored": len(points)
    }
