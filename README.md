# Wikipedia RAG Demo

A containerised Retrieval-Augmented Generation app over English Wikipedia articles. The stack scrapes an article, summarizes it with a local Ollama model, embeds chunks locally, stores them in Qdrant, and answers questions using retrieved context.

## Prerequisites

- Docker and Docker Compose
- Ollama running locally on your machine
- Python 3.11+ if you want to run tests outside Docker
- Enough disk/network time for Ollama to pull the configured models on first run

## Configuration

`.env.example` intentionally uses placeholder values. Create a local `.env` file before running:

```bash
cp .env.example .env
```

For the default local setup, use:

```env
CHAT_MODEL=qwen2.5:3b
EMBED_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://host.docker.internal:11434
QDRANT_COLLECTION=wikipedia_articles
QDRANT_PORT=6333
OLLAMA_PORT=11434
BACKEND_PORT=8000
FRONTEND_PORT=3000
EMBED_CACHE_DIR=/tmp/emb_cache
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173
```

The `.env` file is ignored by git. Model names, ports, collection name, and cache path can be changed there without editing application code.

`OLLAMA_BASE_URL=http://host.docker.internal:11434` is used when the backend runs in Docker and Ollama runs directly on macOS. This is the default recommended local setup because native Ollama is faster than CPU inference inside the Docker container on some Macs.

## Run

Start Ollama on the host machine and pull the models:

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

If Ollama is not already running, start it:

```bash
ollama serve
```

Start the app stack:

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Qdrant: `http://localhost:6333`
- Ollama: `http://localhost:11434`

The default Compose stack starts Qdrant, the backend, and the frontend. It connects to the host Ollama service through `OLLAMA_BASE_URL`.

To run Ollama inside Docker instead, change `.env`:

```env
OLLAMA_BASE_URL=http://ollama:11434
```

Then start Compose with the optional Ollama profile:

```bash
docker compose --profile docker-ollama up --build
```

The Docker Ollama profile can take several minutes on first run because `ollama-pull` downloads `CHAT_MODEL` and `EMBED_MODEL`.

## Quick Smoke Test

After creating `.env`, this script starts the stack and runs the live integration test:

```bash
./run_local.sh
```

## Backend Tests

Create a Python environment and install dependencies:

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
```

Run unit tests with coverage:

```bash
cd backend
PYTHONPATH=. venv/bin/python -m pytest -q
```

The committed coverage report is `backend/coverage.xml`.

To run the live-stack integration test manually, keep Docker Compose running and execute:

```bash
RUN_INTEGRATION=1 PYTHONPATH=backend pytest -q backend/tests/test_integration_stack.py::test_real_stack_root_and_ollama
```

## Demo Evidence

Add the final app demo recording or screenshot link here before submission:

`TODO: paste Loom/GIF/screenshot URL showing ingest, summary, question, answer, and retrieved context.`

## Notes

- Runtime LLM calls and embeddings use local Ollama, not hosted inference APIs.
- Qdrant stores chunk vectors and metadata in the `qdrant_data` Docker volume.
- The frontend is built with Vite and served with `vite preview` in the container; it calls the FastAPI backend directly through `VITE_API_BASE`.
- Ingestion runs as a FastAPI background task with an in-memory job registry and frontend polling. For production, the next step would be a durable job queue such as Celery/RQ with Redis.
- See `REQUIREMENTS.md`, `DESIGN.md`, `TASKS.md`, and `NOTES.md` for planning details and trade-offs.
