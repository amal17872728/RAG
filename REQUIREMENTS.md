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
