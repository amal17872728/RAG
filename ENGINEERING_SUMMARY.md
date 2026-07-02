# Engineering Summary

This document summarizes the engineering work completed on the Wikipedia RAG chatbot during development. It is written as a technical review artifact: what changed, why it changed, where it changed, and what tradeoffs remain.

## Project Overview

The project is a containerised Retrieval-Augmented Generation app for Wikipedia articles.

The main stack is:

- React/Vite frontend
- FastAPI backend
- Qdrant vector database
- Ollama for local chat and embedding models
- Docker Compose for local orchestration

The core workflow is:

```text
User ingests Wikipedia URL
-> backend scrapes article
-> article is chunked
-> chunks are embedded with Ollama
-> vectors and metadata are stored in Qdrant
-> user asks a question
-> backend retrieves relevant chunks
-> Ollama answers using retrieved context
-> frontend displays answer and sources
```

## Major Enhancements Implemented

## 1. Environment-Based Configuration

### Problem

The original setup had important runtime values tied too closely to code or Docker Compose. Model names, service URLs, ports, and feature behavior needed to be configurable without editing source code.

### What Changed

Files changed:

- `backend/app/core/config.py`
- `.env`
- `.env.example`
- `docker-compose.yml`

The backend now reads settings from environment variables through a central `Settings` object.

Important settings include:

```text
CHAT_MODEL
EMBED_MODEL
OLLAMA_BASE_URL
QDRANT_COLLECTION
QDRANT_PORT
BACKEND_PORT
FRONTEND_PORT
CORS_ORIGINS
```

Boolean feature flags were also added:

```text
ENABLE_STREAMING
ENABLE_CITATION_REPAIR
ENABLE_QUERY_REWRITING
ENABLE_MULTI_QUERY_RETRIEVAL
ENABLE_SUMMARY_GENERATION
ENABLE_BACKGROUND_INGESTION
ENABLE_PERF_LOGS
ENABLE_CITATION_DEBUG_LOGS
```

### Why

This makes the app easier to test, explain, and tune. For example, the chat model can be switched from `qwen2.5:1.5b` to another model without touching Python code.

## 2. Host Ollama Instead of Docker Ollama

### Problem

Performance logs showed that Qdrant and embedding were fast, but Ollama generation inside Docker was very slow.

Observed bottleneck:

```text
Embedding: under 1 second
Qdrant search: milliseconds
Ollama generation: dominant latency
```

Ollama logs showed CPU-only inference and slow prompt/token evaluation.

### What Changed

Files changed:

- `.env`
- `docker-compose.yml`
- `README.md`

The backend now uses host Ollama by default:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Docker Ollama was moved behind an optional Compose profile:

```bash
docker compose --profile docker-ollama up --build
```

### Why

Native Ollama on macOS performed significantly better than Ollama inside Docker on the same machine. This kept the backend/frontend/Qdrant containerized while moving the slow model runtime to the faster host environment.

## 3. Performance Logging

### Problem

Latency was being guessed instead of measured. It was unclear whether slow requests were caused by query rewriting, embedding, Qdrant, prompt size, Ollama, citation validation, or citation repair.

### What Changed

File changed:

- `backend/app/api/ask.py`

Added structured logs with prefix:

```text
[PERF]
```

The logs measure:

- request ID
- question
- query rewriting time
- embedding call count and time
- Qdrant search count and time
- chunks retrieved and deduplicated
- prompt size estimate
- Ollama generation time
- citation validation time
- citation repair time
- total request duration

### Why

This made performance work evidence-based. It proved that retrieval was not the bottleneck and that Ollama generation was the expensive stage.

## 4. Query Rewriting and Multi-Query Retrieval

### Problem

Short or vague questions like `when?`, `why?`, or `who founded it?` do not contain enough semantic signal for embedding search.

### What Changed

Files changed:

- `backend/app/api/ask.py`
- `backend/app/services/llm.py`

The backend can now:

- detect vague/follow-up-style questions
- ask Ollama to generate rewritten retrieval queries
- embed each retrieval query
- search Qdrant for each query
- merge and deduplicate chunks

There is also an in-memory rewrite cache.

Feature flags:

```env
ENABLE_QUERY_REWRITING=true
ENABLE_MULTI_QUERY_RETRIEVAL=true
```

### Why

Multi-query retrieval improves recall because different phrasings can retrieve different relevant chunks. It is more expensive than single-query search, so feature flags allow latency comparisons.

## 5. Inline Citations and Citation Validation

### Problem

The original answers were not clearly tied to retrieved chunks. The model could also invent citation numbers.

### What Changed

File changed:

- `backend/app/api/ask.py`

Key functions:

```python
_citation_sources()
_extract_citations()
_invalid_citations()
_missing_citations()
_has_citation_only_line()
```

Retrieved chunks are numbered as sources:

```text
[1], [2], [3], ...
```

The backend validates:

- whether citations exist
- whether citation IDs are valid retrieved sources
- whether citations are missing
- whether citations are incorrectly placed on their own final line

### Why

This makes the app more trustworthy. The system does not blindly trust the model's citations.

Important limitation:

The backend validates that a citation ID exists and is formatted inline. It does not yet prove full claim-level entailment.

## 6. Wikipedia Footnote Stripping

### Problem

Wikipedia article text contains references like `[55]`. The model copied these and they looked like app citations.

### What Changed

File changed:

- `backend/app/api/ask.py`

Function:

```python
_context_text()
```

This removes Wikipedia numeric footnotes from chunk text before sending context to the model.

### Why

Only app-generated citation IDs should be visible to the model.

## 7. Citation Repair Retry

### Problem

The model often produced correct answers without inline citations.

### What Changed

File changed:

- `backend/app/api/ask.py`

The non-streaming `/ask` endpoint can now perform one repair retry if citations are missing or invalid.

Function:

```python
_citation_retry_question()
```

The repair prompt asks the model to preserve the original answer meaning while inserting citations sentence by sentence.

Feature flag:

```env
ENABLE_CITATION_REPAIR=true
```

### Why

This improves citation compliance without hardcoding citations or automatically appending citation IDs.

Important distinction:

`/ask` can repair citations. `/ask/stream` validates citations but does not repair them.

## 8. Streaming Responses

### Problem

The UI originally waited for the full LLM response before showing anything.

### What Changed

Files changed:

- `backend/app/api/ask.py`
- `backend/app/services/llm.py`
- `frontend/src/App.jsx`

Added endpoint:

```text
GET /ask/stream
```

Streaming uses Server-Sent Events:

```text
event: token
event: final
event: error
```

Feature flag:

```env
ENABLE_STREAMING=true
```

The frontend reads `/config` and chooses:

```text
ENABLE_STREAMING=true  -> /ask/stream
ENABLE_STREAMING=false -> /ask
```

### Why

Streaming improves perceived latency. The user sees the answer as it is generated.

Tradeoff:

Streaming does not perform citation repair because repair requires the full generated answer first.

## 9. Background Ingestion Jobs

### Problem

Ingestion originally ran synchronously:

```text
scrape -> chunk -> embed -> store -> summarize -> return
```

Large articles could make the UI feel stuck.

### What Changed

Files changed:

- `backend/app/api/ingest.py`
- `frontend/src/App.jsx`

Added in-memory jobs:

```python
_jobs = {}
```

Added status endpoint:

```text
GET /ingest/status/{job_id}
```

Feature flag:

```env
ENABLE_BACKGROUND_INGESTION=true
```

When enabled, `/ingest` returns a job ID and the frontend polls status.

When disabled, `/ingest` runs synchronously and returns the final result directly.

### Why

This improves UX for long ingestion without introducing Celery, Redis, or new infrastructure.

Limitation:

Jobs are in memory and disappear on backend restart.

## 10. Summary Generation Control

### Problem

Summary generation is another Ollama call during ingestion. It can timeout or slow ingestion.

### What Changed

File changed:

- `backend/app/api/ingest.py`

Summary generation is non-fatal. If it fails after chunks are stored, ingestion still succeeds.

Feature flag:

```env
ENABLE_SUMMARY_GENERATION=true
```

When disabled, ingestion skips the summary call and returns:

```text
summary_status="disabled"
```

### Why

This isolates ingestion/storage from optional summary generation.

## 11. Embedding Cache

### Problem

Embedding every chunk repeatedly is expensive.

### What Changed

File changed:

- `backend/app/services/embedder.py`

Batch embedding uses a disk cache based on SHA-256 hash of chunk text.

Key functions:

```python
_hash_text()
_load_cache()
_write_cache()
generate_embeddings_async()
generate_embeddings()
```

### Why

Repeated ingestion of identical chunks can avoid duplicate embedding calls.

Limitation:

Single query embeddings are not cached.

## 12. Frontend Citation UI

### Problem

Sources were returned by the backend, but users needed an easy way to inspect them.

### What Changed

File changed:

- `frontend/src/App.jsx`

Component:

```js
AnswerText()
```

It turns citation markers like `[1]` into clickable buttons. Clicking opens the corresponding source chunk.

### Why

This makes the answer auditable and improves trust in the RAG response.

## 13. Public Config Endpoint

### Problem

The frontend cannot directly read backend `.env`.

### What Changed

File changed:

- `backend/app/main.py`

Added:

```text
GET /config
```

Returns:

```json
{
  "enable_streaming": true,
  "enable_background_ingestion": true
}
```

### Why

The frontend uses this to choose whether to call streaming `/ask/stream` or normal `/ask`, and whether to poll ingestion jobs.

## Planned But Not Yet Implemented

## Conversation Memory

Conversation memory has been planned but not implemented yet.

Planned goal:

```text
User: Who founded Linux?
User: When?
```

The backend should resolve:

```text
When?
```

into:

```text
When was Linux founded?
```

Planned design:

- deterministic in-memory conversation store
- no extra Ollama call
- no conversation history dumped into answer prompt
- use memory only to resolve retrieval question
- sliding window of last 4 turns
- approximate token budget

Planned flag:

```env
ENABLE_CONVERSATION_MEMORY=true
```

## Current Feature Flags

```env
ENABLE_STREAMING=false
ENABLE_CITATION_REPAIR=true
ENABLE_QUERY_REWRITING=true
ENABLE_MULTI_QUERY_RETRIEVAL=true
ENABLE_SUMMARY_GENERATION=true
ENABLE_BACKGROUND_INGESTION=true
ENABLE_PERF_LOGS=true
ENABLE_CITATION_DEBUG_LOGS=false
```

Notes:

- `ENABLE_STREAMING=false` means frontend uses `/ask`, which supports citation repair.
- If `ENABLE_STREAMING=true`, frontend uses `/ask/stream`, which streams quickly but only validates citations at the end.

## Testing

Backend tests were expanded significantly.

Test coverage includes:

- ingestion happy path
- background job creation
- ingestion failure handling
- summary failure non-fatal behavior
- summary disabled behavior
- citation validation
- missing citation detection
- citation repair retry
- citation repair disabled
- bad citation-only-line repair detection
- query rewriting
- query rewriting disabled
- multi-query disabled
- streaming SSE token/final/error events
- `/config` endpoint
- prompt rules
- Ollama options

Latest backend result:

```text
57 passed, 1 skipped
coverage around 95%
```

## Key Engineering Decisions

## Why Host Ollama

Performance logs showed the bottleneck was Ollama generation, not retrieval. Running Ollama on the host was faster than Docker Ollama on the MacBook Air.

## Why Feature Flags

Feature flags allow latency and behavior testing without deleting code.

Examples:

```text
streaming on/off
citation repair on/off
query rewriting on/off
background ingestion on/off
summary generation on/off
```

## Why Citation Validation Stays Always On

Citations and validation are trust/safety behavior. They were not made optional in the first flag pass to avoid weakening correctness.

## Why Streaming Does Not Repair Citations

Streaming shows tokens immediately, but repair requires the full answer. The system currently chooses:

```text
streaming -> fast UX + validation warning
non-streaming -> slower but can repair citations
```

## Remaining Production Improvements

Important future improvements:

- durable job queue with Redis/Celery/RQ
- persistent conversation memory
- document-level filtering in Qdrant
- answer caching
- stronger model or provider abstraction
- hybrid retrieval with BM25 + vectors
- reranking
- claim-level citation verification
- frontend automated tests
- monitoring/metrics
- production authentication/session isolation

## Manager-Friendly Summary

The project started as a basic Wikipedia RAG chatbot and evolved into a more robust, observable, configurable RAG system.

The biggest improvements were:

- measured performance instead of guessing
- identified Ollama as the bottleneck
- moved Ollama to host runtime for speed
- added streaming for perceived latency
- added citation validation and repair for trust
- added background ingestion for better UX
- added feature flags to isolate behavior
- kept retrieval and answer grounding based on Qdrant chunks

The system is still a demo/take-home implementation, but it now shows strong engineering practices: instrumentation, graceful fallback, scoped feature flags, honest limitations, and a clear path toward production.
