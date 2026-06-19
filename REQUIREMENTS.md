# REQUIREMENTS

## Overview

Build a containerized Retrieval-Augmented Generation (RAG) web application that allows users to interact with the contents of a Wikipedia article.

The application should:

1. Accept a Wikipedia article URL from the user.
2. Scrape and extract article content.
3. Generate a concise summary using a locally deployed LLM.
4. Chunk the article and generate embeddings.
5. Store embeddings in a vector database.
6. Allow users to ask questions about the article through a chat interface.
7. Answer questions using retrieved article chunks (RAG), not model memory.

---

# Functional Requirements

## Article Processing

- User can submit a Wikipedia article URL.
- System validates URL.
- System fetches article content.
- System extracts title, headings, paragraphs, and relevant references.

## Summarization

- Generate a concise article summary.
- Summary generated using local LLM through Ollama.

## Vectorization

- Split article into chunks.
- Generate embeddings for each chunk.
- Store embeddings in vector database.

## Chat

- User can ask questions about the article.
- Relevant chunks are retrieved from vector database.
- Retrieved chunks are provided as context to LLM.
- Responses should be grounded in retrieved content.

## Error Handling

System should handle:

- Invalid URLs
- Network failures
- Empty articles
- Missing embeddings
- LLM failures

---

# Non-Functional Requirements

## Performance

- Summary generation should complete within reasonable time.
- Chat responses should be returned within a few seconds.

## Maintainability

- Modular architecture.
- Clear separation of concerns.
- Replaceable LLM and vector database implementations.

## Testability

- Minimum 85% line coverage.
- Unit and integration tests.

## Containerization

- Entire stack should start with docker compose up.

---

# In Scope

- Single article processing
- Single page UI
- Local LLM summarization
- RAG chat

---

# Out of Scope

- Authentication
- User accounts
- Multi-user support
- Article history
- Analytics
- Conversation persistence

---

# Assumptions

- User provides valid Wikipedia URLs.
- Ollama is available locally.
- Small local models are acceptable.
- Embeddings are generated locally.

---

# Technology Decisions

- Backend: FastAPI
- Frontend: React + Vite
- LLM Runtime: Ollama
- Chat Model: Qwen2.5 3B
- Embedding Model: nomic-embed-text
- Vector Database: Qdrant
- Containerization: Docker Compose
