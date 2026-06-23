# DESIGN.md

## Overview

This application implements a Retrieval-Augmented Generation (RAG) workflow over Wikipedia articles.

Users submit a Wikipedia article URL, which is scraped, chunked, embedded, and stored in Qdrant. When a question is asked, the system retrieves the most relevant chunks and uses a local Ollama-hosted language model to generate an answer grounded in the retrieved content.

The design prioritizes simplicity, modularity, testability, and local-first AI inference while remaining fully containerized through Docker Compose.

---

## Architecture

<img width="1536" height="1024" alt="ChatGPT Image Jun 23, 2026, 06_21_06 AM" src="https://github.com/user-attachments/assets/fcd93206-e202-4926-bf7f-2e9383c0033a" />


### Components

**Frontend (React + Vite)**

Provides a simple interface for article ingestion, summary display, and question answering.

**FastAPI Backend**

Coordinates article scraping, chunk generation, embedding creation, retrieval, and LLM interactions.

**Ollama**

Provides local inference for article summarization, question answering, and embedding generation.

**Qdrant**

Stores article chunk embeddings and metadata and performs similarity search during retrieval.

---

## Data Flow

### Ingestion

1. User submits a Wikipedia URL.
2. The scraper extracts and cleans article content.
3. The article is split into overlapping chunks.
4. Embeddings are generated asynchronously.
5. Chunks and metadata are stored in Qdrant.
6. A concise summary is generated and returned to the frontend.

### Question Answering

1. User submits a question.
2. The question is converted into an embedding.
3. Qdrant retrieves the most relevant chunks.
4. Retrieved chunks are assembled into a context window.
5. The context and question are sent to the local LLM.
6. A grounded answer is generated and returned together with supporting evidence.

---

## Key Design Decisions

### Deterministic Chunk IDs

Chunk identifiers are generated using UUIDv5 derived from the article URL and chunk position. This ensures idempotent ingestion and prevents duplicate vectors from being stored.

### Character-Based Chunking

The application uses fixed-size character chunks (1000 characters with 200-character overlap). This approach is deterministic, simple to implement, and sufficient for the scope of the assignment. Token-aware chunking would likely improve retrieval quality but was considered outside the current scope.

### Embedding Cache

Embeddings are generated asynchronously and cached on disk. Repeated ingestion of identical content can reuse existing embeddings, reducing latency and unnecessary model inference.

### Duplicate Prevention

Before ingestion, the system checks whether the submitted article URL already exists in Qdrant. Existing articles are not reprocessed, reducing storage overhead and ensuring consistent results.

### Modular Service Design

Scraping, chunking, embedding generation, vector storage, and LLM interactions are implemented as separate services. This separation simplifies testing and allows individual components to be replaced without affecting the rest of the system.

---

## Technology Choices

### FastAPI

Selected for its lightweight architecture, strong async support, and straightforward API development experience.

### React + Vite

Provides a minimal frontend with fast development iteration and simple deployment.

### Qdrant

Chosen because it offers persistent vector storage, metadata filtering, efficient similarity search, and seamless Docker integration.

### Ollama

Provides local inference while satisfying the requirement that the running application must not depend on hosted LLM providers.

---

## Testing

External dependencies such as Ollama and Qdrant are mocked during unit testing to ensure fast and deterministic execution.

An optional integration test exercises the complete stack using Docker Compose and can be enabled through:

```bash
RUN_INTEGRATION=1
```

The project exceeds the required coverage threshold and includes a generated coverage report in the repository.

<img width="1470" height="507" alt="Screenshot 2026-06-23 at 11 53 01 AM" src="https://github.com/user-attachments/assets/9b6520da-d151-4343-b65f-5dea5d9ee45e" />

---
