# Design

## Architecture

# Design

## Purpose

This document describes the architecture and module contracts for the Wikipedia RAG backend: components, data flow from URL → answered question, chosen runtime(s), chunking/embedding strategy, vector store, and clear contracts between modules. A compact ASCII diagram is included.

## Architecture (components)

- Browser / Vite (frontend) — optional Nginx proxy for same-origin production build.
- FastAPI backend — HTTP API exposing `/ingest` and `/ask`.
- Ollama (local LLM + embedding endpoint) — used for summaries, embeddings, and generation in the integration stack.
- Qdrant — vector database for storing embeddings + payload metadata.

ASCII diagram

        Browser (:3000)
                │  /api/*
                ▼
        Nginx (optional) ──► FastAPI (:8000)
                                                     ├──► Ollama (:11434)  # embeddings & LLM
                                                     └──► Qdrant (:6333)   # vectors + payload

All services can be run with `docker compose` for the full integration environment; unit tests mock external calls.

## Data flow: Ingest (URL → stored vectors)

1. Client POSTs `{ "url": "https://..." }` to `POST /ingest`.
2. `scraper.extract_wikipedia_article(url)` validates URL and fetches article HTML, returning `{title, content, sections, references}` or `{error}`.
3. `chunker.chunk_text(content)` produces deterministic overlapping chunks (see chunking strategy below).
4. For each chunk:
     - Optionally summarize via `llm.summarize_article(chunk)` to produce a short summary stored as metadata.
     - Produce embeddings via `embedder.generate_embedding(chunk)` (calls local Ollama embedding endpoint in integration, mocked in unit tests).
     - `vector_store.store_chunks(points)` upserts vectors with payload: `{id, text, title, chunk_number, url, summary?}`.
5. `vector_store.article_exists(url)` checks for duplicates (by URL/title) and prevents re-ingesting the same article.

## Data flow: Ask (question → answer)

1. Client GETs `/ask?question=...&top_k=K`.
2. Backend calls `embedder.generate_embedding(question)` to get a query vector.
3. `vector_store.search_chunks(vector, limit=K)` returns top-K results (score + payload).
4. If no results → return 404 (avoid hallucinations from empty context).
5. Construct prompt from retrieved chunks (context window aware) and call `llm.answer_question(question, context)`.
6. Return `{answer, context: [chunks], timings: {t_embedding, t_search, t_generation, t_total}}`.

## Choices and trade-offs

- LLM runtime: Ollama (local inference) selected for offline demos and no data egress. Trade-off: large image and resource needs; unit tests mock it so CI does not require Ollama.
- Embedding model: use Ollama's embedding endpoint or `nomic-embed-text` when available. Local embeddings avoid network egress.
- Vector store: Qdrant — Docker-friendly, metadata payloads, filtering and efficient nearest-neighbor search.
- Chunking strategy: character-based deterministic chunks (default 1000 chars, 200 overlap). Rationale: simple, deterministic IDs. Token-aware chunking is preferred for production but out of scope here.

## Module contracts (public functions)

- `scraper.extract_wikipedia_article(url: str) -> dict`  
    returns `{title, content, sections, references}` or `{error: str}`
- `chunker.chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]`
- `embedder.generate_embedding(text: str) -> List[float]`  (sync)
- `embedder.generate_embeddings_async(texts: List[str]) -> List[List[float]]`
- `vector_store.create_collection(dim: int) -> None`
- `vector_store.store_chunks(points: List[dict]) -> None`  # points include id, vector, payload
- `vector_store.search_chunks(vector: List[float], limit: int) -> List[dict]`  # returns payload + score
- `vector_store.article_exists(url: str) -> bool`
- `llm.summarize_article(text: str) -> str`
- `llm.answer_question(question: str, context: str) -> str`

All functions are mocked at unit-test boundaries; the integration test uses the real services behind environment-controlled ports.

## Testing notes

- Unit tests: mock `requests` calls to Ollama and mock `vector_store.client` to verify logic and edge cases.
- API tests: use FastAPI `TestClient` and monkeypatch internal modules to verify request/response behavior.
- Integration: gated test (RUN_INTEGRATION=1) exercises full Compose stack (Ollama + Qdrant).

## Failure & edge-case behavior

- Invalid URLs or fetch errors → `POST /ingest` returns 400 with details.
- Empty chunk list → `POST /ingest` returns 400.
- No retrieval for a question → `GET /ask` returns 404.
- External service errors propagate as 5xx and are visible in logs.

---

Files:
- `app/api/ingest.py`, `app/api/ask.py`, `app/services/{scraper,chunker,embedder,llm,vector_store}`

If you want any additional diagram format (PNG or higher-res SVG) I can add it; otherwise this design doc now matches the spec. 

## Simple ASCII diagram (alternative view)

    [Browser]
       │
    [Nginx]──/api──►[FastAPI]
                  ├──►[Ollama (embeddings/LLM)]
                  └──►[Qdrant (vector DB)]

--
