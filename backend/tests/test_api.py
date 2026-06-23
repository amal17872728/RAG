from fastapi.testclient import TestClient

from app.main import app
from app.api import ask as ask_api, ingest as ingest_api

client = TestClient(app)


def test_root_and_validation():
    assert client.get("/").status_code == 200
    assert client.get("/ask", params={"question": "", "top_k": 20}).status_code == 422


def test_ingest_happy_path(monkeypatch):
    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"title": "Test", "content": "abcdef"})
    monkeypatch.setattr(ingest_api, "article_exists", lambda _: False)
    monkeypatch.setattr(ingest_api, "chunk_text", lambda _: ["abc", "def"])
    monkeypatch.setattr(ingest_api, "generate_embedding", lambda text: [float(len(text))])
    monkeypatch.setattr(ingest_api, "create_collection", lambda _: None)
    stored = []
    monkeypatch.setattr(ingest_api, "store_chunks", stored.extend)
    monkeypatch.setattr(ingest_api, "summarize_article", lambda _: "summary")

    response = client.post("/ingest", json={"url": "https://en.wikipedia.org/wiki/Test"})
    assert response.status_code == 200
    assert response.json()["chunks_stored"] == 2
    assert stored[0]["title"] == "Test"


def test_ingest_error_duplicate_and_empty(monkeypatch):
    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"error": "bad URL"})
    assert client.post("/ingest", json={"url": "bad"}).status_code == 400

    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"title": "Test", "content": "text"})
    monkeypatch.setattr(ingest_api, "article_exists", lambda _: True)
    assert client.post("/ingest", json={"url": "url"}).json()["status"] == "exists"

    monkeypatch.setattr(ingest_api, "article_exists", lambda _: False)
    monkeypatch.setattr(ingest_api, "chunk_text", lambda _: [])
    assert client.post("/ingest", json={"url": "url"}).status_code == 400


def test_ask_uses_retrieved_context(monkeypatch):
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    chunks = [{"title": "Test", "chunk_number": 2, "text": "grounded fact"}]
    monkeypatch.setattr(ask_api, "search_chunks", lambda embedding, limit: chunks)
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: f"{question}: {context}")
    response = client.get("/ask", params={"question": "Why?"})
    assert response.status_code == 200
    assert "grounded fact" in response.json()["answer"]

    monkeypatch.setattr(ask_api, "search_chunks", lambda embedding, limit: [])
    assert client.get("/ask", params={"question": "Why?"}).status_code == 404
