from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uuid

from app.core.config import settings
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
_jobs = {}


class IngestRequest(BaseModel):
    url: str


def _generate_summary_response(content: str) -> dict:
    if not settings.enable_summary_generation:
        return {
            "summary": "Summary generation disabled.",
            "summary_status": "disabled",
            "summary_error": None,
        }

    try:
        return {
            "summary": summarize_article(content),
            "summary_status": "ok",
            "summary_error": None,
        }
    except Exception as exc:
        return {
            "summary": "Summary generation failed or timed out, but article chunks were ingested successfully.",
            "summary_status": "failed",
            "summary_error": str(exc)[:300],
        }


def _run_ingestion(url: str) -> dict:
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

    summary_result = _generate_summary_response(article.get("content", ""))

    return {
        "status": "ok",
        "title": article.get("title"),
        "summary": summary_result["summary"],
        "summary_status": summary_result["summary_status"],
        "summary_error": summary_result["summary_error"],
        "chunks_stored": len(points)
    }


def _run_ingestion_job(job_id: str, url: str):
    _jobs[job_id].update({
        "status": "running",
        "message": "Ingestion started",
        "error": None,
    })

    try:
        result = _run_ingestion(url)
        _jobs[job_id].update({
            "status": "completed",
            "message": "Ingestion completed",
            "result": result,
            "error": None,
        })
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        _jobs[job_id].update({
            "status": "failed",
            "message": "Ingestion failed",
            "result": None,
            "error": str(detail),
        })


@router.post("/ingest")
def ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    if not settings.enable_background_ingestion:
        return _run_ingestion(req.url)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "url": req.url,
        "status": "pending",
        "message": "Ingestion queued",
        "result": None,
        "error": None,
    }
    background_tasks.add_task(_run_ingestion_job, job_id, req.url)
    return _jobs[job_id]


@router.get("/ingest/status/{job_id}")
def ingest_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job
