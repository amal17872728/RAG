# DESIGN

## Architecture

+-------------+
| React UI    |
+-------------+
       |
       v
+-------------+
| FastAPI API |
+-------------+
       |
       +------------------+
       |                  |
       v                  v
+-------------+    +-------------+
| Ollama      |    | Qdrant      |
| Qwen2.5 3B  |    | Vector DB   |
+-------------+    +-------------+

---

## Processing Flow

User URL
    |
    v
Wikipedia Scraper
    |
    v
Article Text
    |
    +---------------------+
    |                     |
    v                     v
Summary Generation    Chunking
                           |
                           v
                    Embeddings
                           |
                           v
                         Qdrant

---

## RAG Flow

Question
    |
Embedding
    |
Vector Search
    |
Top K Chunks
    |
Prompt Assembly
    |
Qwen2.5
    |
Answer

---

## Chunking Strategy

Chunk Size: 500 characters

Overlap: 100 characters

Reason:
Balances retrieval quality and context preservation.

---

## Embedding Strategy

Model:
nomic-embed-text

Reason:
Runs locally through Ollama and performs well for semantic search.

---

## Vector Store

Qdrant

Reason:
Docker-friendly.
Easy setup.
Production-grade.

---

## LLM Runtime

Ollama

Model:
qwen2.5:3b

Reason:
Small memory footprint.
Good reasoning quality.
Runs comfortably on M4 Mac 16GB.

---

## Backend Modules

services/

- scraper.py
- summarizer.py
- embedder.py
- vector_store.py
- chat.py

---

## API Endpoints

POST /process-url

Request:
{
  "url": "..."
}

Response:
{
  "summary": "...",
  "article_id": "..."
}

POST /chat

Request:
{
  "question": "...",
  "article_id": "..."
}

Response:
{
  "answer": "..."
}
