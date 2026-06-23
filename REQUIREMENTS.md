# Requirements — Wikipedia RAG take‑home

This file is our interpretation of the assignment and the decisions we made while implementing the system.

1) Objective
- Build a small web app that ingests a Wikipedia article, summarizes it, stores chunks in a vector DB, and answers user questions using RAG (answers grounded in retrieved chunks).

2) Functional requirements (in-scope)
- POST /ingest: accept a Wikipedia URL, scrape the article, generate a concise summary, chunk the article, create embeddings for chunks, store vectors and metadata in Qdrant.
- GET /ask: accept a question, embed the question, search Qdrant for top‑k relevant chunks, combine the chunks into a context window, and call the local LLM to answer using that context. Return answer and retrieved chunks.
- GET /summary and GET /article: convenience endpoints for previewing article contents and summaries.

3) Non-functional requirements
- The app must run locally with a single `docker compose up` (Qdrant + app + optionally local LLM). If the LLM cannot be containerised on the runner hardware, document the fallback (host Ollama) in `README.md`.
- Tests: unit tests mocking external services and one optional integration test exercising the real Compose stack. Coverage >= 85% for backend app code.
- No secrets committed; configuration via environment variables and `.env.example`.

4) In-scope vs out-of-scope
- In-scope: single-article ingestion, per-article deterministic chunk ids, chunk metadata (title, chunk_number, url), duplicate prevention by URL, local LLM calls via Ollama, vector storage with Qdrant, small React UI for demo.
- Out-of-scope: authentication, multi-article per-user history, analytics, production hardening (auto-scaling, observability beyond simple logs), enterprise features.

5) Assumptions made
- Running environment has Docker available for Qdrant and optionally for Ollama. If not, the app supports a host-run Ollama via `OLLAMA_BASE_URL`.
- Embeddings produced by `nomic-embed-text` (via local Ollama embedding endpoint) and are of fixed dimension; collection creation uses the first embedding's size.
- Chunking uses fixed character windows (1,000 chars with 200 overlap) for simplicity and deterministic behaviour.
- Deterministic chunk IDs use UUIDv5 over `url#index` to avoid collisions and enable idempotent ingestion.

6) Open questions we resolved
- Q: Containerise the LLM? A: Prefer containerising Ollama in compose when possible; otherwise document connecting to local host Ollama (this repo allows `OLLAMA_BASE_URL` override).
- Q: Embedding batching? A: Implemented async concurrent embedding + disk cache to reduce latency and avoid re-requesting unchanged text.
- Q: Duplicate detection criteria? A: Use `url` field in Qdrant payloads and `article_exists(url)` query to avoid re-ingestion.

7) Minimal acceptance criteria (for reviewers)
- The app ingests an English Wikipedia article and returns a concise summary.
- The app stores article chunks and embeddings in Qdrant with metadata.
- Asking questions returns answers grounded in retrieved chunks; UI shows the summary and answer.
- Tests run locally and coverage >= 85%.

8) How AI agents were used (short)
- The development used AI agents as a pair programmer for planning, scaffolding files, and generating code snippets; all final code was reviewed and adjusted by the author. The `TASKS.md` contains the planning artefacts and examples of prompts used.
# Requirements

## Interpretation

Build a small, containerised RAG application over English Wikipedia. A user submits one article URL, receives a locally generated summary, and asks grounded questions whose supporting chunks are visible. The repository must also demonstrate an AI-agent-assisted engineering process through planning artifacts, tests, and an execution log.

## Functional requirements

1. Accept and validate an English Wikipedia article URL.
2. Fetch readable paragraphs plus section and reference metadata where available.
3. Reject invalid URLs, fetch failures, and empty articles with useful errors.
4. Split content into overlapping chunks and embed every chunk locally.
5. Persist chunks and metadata in Qdrant; repeated ingestion must be idempotent.
6. Generate a concise summary with a local Ollama chat model.
7. Embed each question, retrieve top-k chunks, pass only that context to the chat model, and return the answer with its evidence.
8. Provide a functional one-page URL, summary, and chat UI.

## Non-functional requirements

- `docker compose up --build` starts the UI, API, Qdrant, and Ollama and downloads required models on first run.
- Runtime inference and embeddings make no hosted AI calls.
- Application line coverage is at least 85%, enforced by pytest; unit tests mock network/model/database boundaries and an opt-in integration test checks the live stack.
- Components remain replaceable through small scraper, chunker, embedding, LLM, and vector-store modules.
- No secrets are committed; model names are configurable through environment variables.

## Scope

In scope: one shared article-ingestion flow, summary, grounded Q&A, local persistence, Docker Compose, tests, planning documentation, and demo evidence instructions.

Out of scope: authentication, users, analytics, conversation persistence, article-history UI, distributed jobs, and production cloud deployment.

## Assumptions and unilateral decisions

- Only `en.wikipedia.org/wiki/...` URLs are accepted. This narrows parsing behavior and blocks arbitrary server-side URL fetching (SSRF).
- Content is capped at 50,000 characters and chunked at 1,000 characters with 200-character overlap. This bounds local inference time while preserving adjacent context.
- `qwen2.5:3b` is the default chat model and `nomic-embed-text` the embedding model; both fit a typical 16 GB development laptop.
- Duplicate identity is the canonical submitted URL. Deterministic UUIDs make retries idempotent.
- Ingestion remains synchronous because background jobs are outside this exercise's intended surface; the UI exposes a busy state.
- Ollama runs in Compose for single-command review. On macOS this may be slower than host-native Ollama due to container acceleration limits.

## Resolved questions

- References are captured as metadata but not embedded separately; paragraph text is the retrieval corpus.
- The application supports a shared collection rather than an article selector because article history is explicitly out of scope.
- The coverage report is committed as `backend/coverage.xml`; generated HTML is ignored.
