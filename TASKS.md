# TASKS — Execution log and AI-assisted plan

This file documents the decomposition used while building the project, the order tasks were tackled in, and notes about what was delegated to the AI agent vs what was implemented by hand.

Plan (high level)

1. Project scaffolding
   - Create backend FastAPI app and services modules: `scraper`, `chunker`, `embedder`, `vector_store`, `llm`.
   - Scaffolding done with AI assistance for file templates and route stubs; author refined and implemented logic.

2. Ingestion pipeline
   - Implement `extract_wikipedia_article(url)` (scrape, validate URL).
   - Implement `chunk_text(text)` with overlap.
   - Implement embeddings and `create_collection` + `store_chunks` in Qdrant.
   - Add `/ingest` endpoint to orchestrate the flow and summarize the article.

3. Retrieval & QA
   - Implement question embedding, search, context assembly and `answer_question` using local LLM.
   - Add `/ask` endpoint returning answer and retrieved chunks.

4. Optimisations and robustness
   - Add duplicate detection (`article_exists`) in Qdrant.
   - Add async batched embeddings with disk cache and safe fallback.
   - Add per-step timing in `/ask` for diagnostics.

5. Frontend
   - Scaffold a minimal Vite + React UI with ingest form, summary display, question box, answer display, loading states and error handling.

6. Tests & coverage
   - Add unit tests for services and API endpoints (mocking external services). Add integration test that can be run behind `RUN_INTEGRATION=1`.
   - Ensure coverage >= 85% (adjust tests to meet the threshold).

Task list (detailed, chronological)

- [x] Initialize FastAPI app and basic routes (`app/main.py`, `app/api/*`). (Author + AI scaffolding)
- [x] Implement `scraper.extract_wikipedia_article`. (Author)
- [x] Implement `chunker.chunk_text`. (Author)
- [x] Implement `embedder.generate_embedding` and later async `generate_embeddings`. (AI generated + author edits)
- [x] Implement `vector_store` with Qdrant client, `create_collection`, `store_chunks`, `article_exists`, `search_chunks`. (Author)
- [x] Implement `llm.summarize_article` and `llm.answer_question` with local Ollama calls; guard `answer_question` to return message when context missing. (Author)
- [x] Implement `/ingest` orchestration endpoint (ingest, chunk, embed, store, summarise). (Author)
- [x] Implement `/ask` endpoint; later extended to include per-step timings. (Author)
- [x] Add React/Vite frontend scaffold and basic pages. (AI scaffold + author wiring)
- [x] Add async batched embeddings with disk cache and safe fallback; update `/ingest` to use it. (AI draft + author integration)
- [x] Add `.coveragerc` and unit tests; run tests locally and reach >=85% coverage. (Author tests + AI assistance for test ideas)
- [x] Add diagnostics: timing in `/ask`. (Author)

Notes on AI usage (evidence and prompts)
- The AI agent was used as a planning and scaffolding partner: to generate route templates, initial service implementations, and the async embedding code sketch. Example prompts used:

  - "Generate a FastAPI route template for POST /ingest that accepts a JSON body {url: str} and returns summary and chunk count."
  - "Provide a robust Wikipedia scraper that validates the URL, fetches the article and returns title, content, sections, and references." 
  - "Show an asyncio-based function to concurrently request embeddings for a list of texts and cache results to disk." 

- All AI-generated code was reviewed, adapted and tested by the author; no AI output was accepted verbatim without review.

Next steps (remaining or optional)
- Add streaming LLM responses to reduce perceived latency (optional).
- Improve chunking to be token-aware (use a tokeniser) for better context packing.
- Harden ingestion with retries and more detailed progress reporting (progress endpoint / background job).
- Containerise Ollama (if feasible) and ensure `docker compose up` brings up the full stack; document host fallback in `README.md`.
# Execution Plan and Log

Status legend: `[x]` complete, `[ ]` manual/future. This file records the actual sequence, including corrections rather than presenting a fictional perfect first pass.

## 1. Planning (AI pair + developer review)

- [x] Restate the brief into functional/non-functional requirements and explicit scope.
- [x] Choose FastAPI, React/Vite, Ollama, and Qdrant; document data flows and trade-offs.
- [x] Decompose implementation into scraper, local inference, storage, API, UI, test, and container tasks.

The initial planning artifacts were drafted with an AI coding agent and then revised after the original take-home brief was attached. The agent was used for decomposition, implementation, debugging, and verification; decisions and submitted code remain the developer's responsibility.

## 2. Core pipeline

- [x] Implement Wikipedia paragraph scraping.
- [x] Implement overlapping chunking.
- [x] Integrate Ollama summary, answer, and embedding calls.
- [x] Integrate Qdrant collection creation, storage, filtering, and retrieval.
- [x] Implement `/ingest` and `/ask` orchestration.
- [x] Build the single-page ingestion, summary, question, and evidence UI.

## 3. Live-stack debugging (AI agent executed, developer-visible)

- [x] Reproduce frontend `Failed to fetch`; identify missing CORS preflight handling.
- [x] Add Vite-origin CORS and verify `OPTIONS /ingest` returns 200.
- [x] Replace removed Qdrant `search()` call with `query_points()`.
- [x] Replace invalid `hash::chunk` point IDs with deterministic UUIDv5 IDs.
- [x] Correct Qdrant `scroll_filter` keyword and tuple response handling.
- [x] Ingest the Muhammad Ali Jinnah article (63 chunks) and verify a grounded answer.
- [x] Verify repeated ingestion returns `status: exists`.

## 4. Hardening

- [x] Restrict ingestion to English Wikipedia article URLs.
- [x] Extract headings/reference metadata and reject empty articles.
- [x] Make Ollama/Qdrant endpoints and model names environment-configurable.
- [x] Validate chunk settings and ask query/top-k inputs.
- [x] Return 404 instead of invoking the LLM when retrieval has no evidence.

## 5. Tests and coverage

- [x] Add meaningful chunker and validation edge-case tests.
- [x] Mock Wikipedia/Ollama HTTP boundaries in unit tests.
- [x] Mock Qdrant collection, duplicate, upsert, and query behavior.
- [x] Exercise FastAPI ingestion and grounded-answer orchestration.
- [x] Add an opt-in test for the live Compose stack.
- [x] Enforce ≥85% coverage and generate committed XML report (97.6%; 21 passed, 1 integration skipped).

## 6. Containerisation and developer experience

- [x] Add backend and multi-stage frontend Dockerfiles.
- [x] Add Nginx SPA/API proxy configuration.
- [x] Compose Qdrant, Ollama, model pull, API, and UI into one command.
- [x] Add `.env.example`, root README, prerequisites, commands, and caveats.
- [x] Add honest follow-up notes and AI-correction history.

## 7. Submission

- [ ] Developer: review the diff and commit in meaningful commits (do not rewrite history dishonestly).
- [ ] Developer: record a 2–4 minute demo or commit screenshots of the working flow.
- [ ] Developer: push the final reviewed repository publicly and submit its URL.
