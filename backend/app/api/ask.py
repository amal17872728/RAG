from fastapi import APIRouter, HTTPException, Query
import time

from app.services.embedder import generate_embedding
from app.services.vector_store import search_chunks
from app.services.llm import answer_question

router = APIRouter()


@router.get("/ask")
def ask(question: str = Query(min_length=1), top_k: int = Query(5, ge=1, le=10)):
    start_total = time.time()

    t0 = time.time()
    query_embedding = generate_embedding(question)
    t_embedding = time.time() - t0

    t0 = time.time()
    chunks = search_chunks(query_embedding, limit=top_k)
    t_search = time.time() - t0

    if not chunks:
        raise HTTPException(status_code=404, detail="No ingested article content was found")

    # build a single context window from top chunks
    context_pieces = [
        f"Title: {c.get('title') if c.get('title') else 'Unknown'}\nChunk {c.get('chunk_number')}:\n{c.get('text')}"
        for c in chunks
        if c.get("text")
    ]

    context = "\n\n---\n\n".join(context_pieces)

    t0 = time.time()
    answer = answer_question(question, context)
    t_generation = time.time() - t0

    t_total = time.time() - start_total

    return {
        "question": question,
        "answer": answer,
        "context": chunks,
        "timings": {
            "embedding": round(t_embedding, 3),
            "search": round(t_search, 3),
            "generation": round(t_generation, 3),
            "total": round(t_total, 3)
        }
    }
