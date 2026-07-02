# TASKS - Execution Log and AI-Assisted Plan

This file records the decomposition used while building the project, the order work was tackled in, and what was delegated to the AI agent versus reviewed or implemented by the developer.

Status legend: `[x]` complete, `[ ]` manual/future.

## 1. Planning

- [x] Restate the brief into functional and non-functional requirements.
- [x] Choose FastAPI, React/Vite, Ollama, and Qdrant.
- [x] Document data flow, model choices, vector store choice, and trade-offs.
- [x] Decompose work into scraper, chunking, embedding, storage, API, UI, tests, and containerisation tasks.

The initial planning artifacts were drafted with an AI coding agent and then revised by the developer. The agent was used for decomposition, implementation support, debugging, and verification; final decisions and submitted code remain the developer's responsibility.

## 2. Core Pipeline

- [x] Create backend FastAPI app and API routers.
- [x] Implement Wikipedia URL validation and article scraping.
- [x] Extract readable paragraphs plus section and reference metadata.
- [x] Implement overlapping character-based chunking.
- [x] Integrate local Ollama calls for summaries, answers, and embeddings.
- [x] Integrate Qdrant collection creation, vector upserts, duplicate checks, and similarity retrieval.
- [x] Implement `/ingest` orchestration: scrape, chunk, embed, store, summarize.
- [x] Implement `/ask` orchestration: embed question, retrieve chunks, build context, answer.
- [x] Build the single-page ingestion, summary, question, answer, and evidence UI.

## 3. Live-Stack Debugging

- [x] Reproduce frontend `Failed to fetch`; identify missing CORS preflight handling.
- [x] Add Vite-origin CORS and verify `OPTIONS /ingest` returns successfully.
- [x] Replace removed Qdrant `search()` call with `query_points()`.
- [x] Replace invalid `hash::chunk` point IDs with deterministic UUIDv5 IDs.
- [x] Correct Qdrant `scroll_filter` keyword and tuple response handling.
- [x] Ingest a real Wikipedia article and verify a grounded answer.
- [x] Verify repeated ingestion returns `status: exists`.

## 4. Hardening

- [x] Restrict ingestion to English Wikipedia article URLs.
- [x] Reject invalid URLs, empty articles, and missing retrieval evidence.
- [x] Make Ollama/Qdrant endpoints, model names, collection name, and cache path environment-configurable.
- [x] Add async batched embeddings with disk cache and safe fallback.
- [x] Validate chunk settings and ask query/top-k inputs.
- [x] Return `404` instead of invoking the LLM when retrieval has no evidence.
- [x] Make summary generation non-fatal after successful chunk storage, so Ollama summary timeouts do not fail ingestion.
- [x] Move ingestion behind a FastAPI `BackgroundTasks` job with in-memory status tracking.
- [x] Add `/ingest/status/{job_id}` so the frontend can poll ingestion progress.
- [x] Add inline citation IDs to retrieved chunks in `/ask`.
- [x] Update the answer prompt so the model cites only retrieved chunk IDs.
- [x] Parse model citation markers and report hallucinated/unsupported citation numbers.
- [x] Detect answers that omit inline citations and surface a warning.
- [x] Show cited source chunks and unsupported citation warnings in the frontend.
- [x] Add clickable inline citation buttons that expand the matching source chunk.
- [x] Retry answer generation once when the model omits or invents citations.
- [x] Strip Wikipedia footnote markers from LLM context so they are not mistaken for app citations.
- [x] Add multi-query rewriting before retrieval with original-query fallback.
- [x] Cache rewritten queries in memory to avoid repeated Ollama rewrite calls.
- [x] Fan out retrieval across rewritten queries and deduplicate retrieved chunks.
- [x] Skip rewriting for clear standalone questions to reduce local Ollama latency.
- [x] Add `/ask/stream` SSE endpoint for token-level answer streaming.
- [x] Stream partial answers in the frontend while preserving final citation metadata.
- [x] Return a clean `/ask` timeout error when Ollama answer generation is too slow.
- [x] Disable asking while ingestion is running to avoid competing Ollama requests.

## 5. Tests and Coverage

- [x] Add chunker and validation edge-case tests.
- [x] Mock Wikipedia/Ollama HTTP boundaries in unit tests.
- [x] Mock Qdrant collection, duplicate, upsert, and query behavior.
- [x] Exercise FastAPI ingestion and grounded-answer orchestration.
- [x] Test that summary timeout/failure still returns successful ingestion with `summary_status="failed"`.
- [x] Test ingestion job creation, status lookup, completion, failure, and summary-failure completion.
- [x] Test valid citation handling and hallucinated citation detection.
- [x] Test missing inline citation detection.
- [x] Test citation retry when the first model answer has no citation markers.
- [x] Test that Wikipedia reference markers are removed before answer generation.
- [x] Test query-rewrite fan-out, deduplication, fallback, and cache behavior.
- [x] Test that clear standalone questions skip rewriting while vague follow-ups still rewrite.
- [x] Test streaming token events, final citation metadata, and stream error events.
- [x] Add an opt-in integration test for the live Compose stack.
- [x] Enforce at least 85% coverage with pytest.
- [x] Regenerate and commit `backend/coverage.xml` showing 93.84% line coverage.

## 6. Containerisation and Developer Experience

- [x] Add backend Dockerfile.
- [x] Add multi-stage frontend Dockerfile.
- [x] Serve the built Vite frontend with `vite preview` in the frontend container.
- [x] Compose Qdrant, Ollama, model pull, API, and UI.
- [x] Add `.env.example`, `.gitignore` rules, and central backend settings.
- [x] Add README setup, run, test, caveat, and demo-evidence instructions.

## 7. AI Usage Evidence

The AI agent was used as a planning and scaffolding partner. Example prompts used:

- "Generate a FastAPI route template for POST /ingest that accepts a JSON body `{url: str}` and returns summary and chunk count."
- "Provide a robust Wikipedia scraper that validates the URL, fetches the article and returns title, content, sections, and references."
- "Show an asyncio-based function to concurrently request embeddings for a list of texts and cache results to disk."

All AI-generated code was reviewed, adapted, and tested by the developer. Notable corrections included CORS handling, updated Qdrant APIs, valid Qdrant point IDs, and correct Qdrant scroll behavior.

## 8. Submission

- [ ] Developer: add a 2-4 minute demo recording or screenshots showing ingest, summary, chat answer, and retrieved context.
- [ ] Developer: review final repository state and submit the public GitHub URL.

## Optional Next Steps

- [ ] Move ingestion to a background job and expose progress/status.
- [ ] Improve chunking with token-aware splitting.
- [ ] Add streaming LLM responses.
- [ ] Add browser-level UI tests and accessibility checks.
