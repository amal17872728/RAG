from fastapi.testclient import TestClient
import json
import pytest
import requests

from app.main import app
from app.api import ask as ask_api, ingest as ingest_api
from app.services import conversation
from app.services import llm

client = TestClient(app)


def setup_function():
    conversation._store.clear()


def set_setting(name, value):
    old_value = getattr(ask_api.settings, name)
    object.__setattr__(ask_api.settings, name, value)
    return old_value


def test_root_and_validation():
    assert client.get("/").status_code == 200
    assert client.get("/ask", params={"question": "", "top_k": 20}).status_code == 422


def test_public_config_endpoint_uses_safe_flags():
    old_streaming = set_setting("enable_streaming", False)
    old_background = set_setting("enable_background_ingestion", False)
    try:
        response = client.get("/config")
    finally:
        object.__setattr__(ask_api.settings, "enable_streaming", old_streaming)
        object.__setattr__(ask_api.settings, "enable_background_ingestion", old_background)

    assert response.status_code == 200
    assert response.json() == {
        "enable_streaming": False,
        "enable_background_ingestion": False,
    }


def test_ingest_happy_path(monkeypatch):
    ingest_api._jobs.clear()
    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"title": "Test", "content": "abcdef"})
    monkeypatch.setattr(ingest_api, "article_exists", lambda _: False)
    monkeypatch.setattr(ingest_api, "chunk_text", lambda _: ["abc", "def"])
    monkeypatch.setattr(ingest_api, "generate_embedding", lambda text: [float(len(text))])
    monkeypatch.setattr(ingest_api, "create_collection", lambda _: None)
    stored = []
    monkeypatch.setattr(ingest_api, "store_chunks", stored.extend)
    monkeypatch.setattr(ingest_api, "summarize_article", lambda _: "summary")

    result = ingest_api._run_ingestion("https://en.wikipedia.org/wiki/Test")
    assert result["chunks_stored"] == 2
    assert result["summary_status"] == "ok"
    assert result["summary_error"] is None
    assert stored[0]["title"] == "Test"


def test_ingest_returns_job_id_immediately(monkeypatch):
    ingest_api._jobs.clear()
    added = []

    class FakeBackgroundTasks:
        def add_task(self, fn, *args):
            added.append((fn, args))

    response = ingest_api.ingest(
        ingest_api.IngestRequest(url="https://en.wikipedia.org/wiki/Test"),
        FakeBackgroundTasks(),
    )

    assert response["job_id"]
    assert response["status"] == "pending"
    assert response["message"] == "Ingestion queued"
    assert response["job_id"] in ingest_api._jobs
    assert added[0][0] == ingest_api._run_ingestion_job


def test_ingest_status_unknown_job_returns_404():
    ingest_api._jobs.clear()
    response = client.get("/ingest/status/missing-job")
    assert response.status_code == 404


def test_ingestion_job_completed_stores_result(monkeypatch):
    ingest_api._jobs.clear()
    ingest_api._jobs["job-1"] = {
        "job_id": "job-1",
        "url": "url",
        "status": "pending",
        "message": "queued",
        "result": None,
        "error": None,
    }
    monkeypatch.setattr(ingest_api, "_run_ingestion", lambda url: {"status": "ok", "chunks_stored": 2})

    ingest_api._run_ingestion_job("job-1", "url")

    assert ingest_api._jobs["job-1"]["status"] == "completed"
    assert ingest_api._jobs["job-1"]["message"] == "Ingestion completed"
    assert ingest_api._jobs["job-1"]["result"]["chunks_stored"] == 2
    assert ingest_api._jobs["job-1"]["error"] is None


def test_ingestion_job_failed_stores_error(monkeypatch):
    ingest_api._jobs.clear()
    ingest_api._jobs["job-1"] = {
        "job_id": "job-1",
        "url": "url",
        "status": "pending",
        "message": "queued",
        "result": None,
        "error": None,
    }

    def fail(url):
        raise RuntimeError("boom")

    monkeypatch.setattr(ingest_api, "_run_ingestion", fail)

    ingest_api._run_ingestion_job("job-1", "url")

    assert ingest_api._jobs["job-1"]["status"] == "failed"
    assert ingest_api._jobs["job-1"]["message"] == "Ingestion failed"
    assert ingest_api._jobs["job-1"]["result"] is None
    assert ingest_api._jobs["job-1"]["error"] == "boom"


def test_ingest_summary_failure_is_non_fatal(monkeypatch):
    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"title": "Test", "content": "abcdef"})
    monkeypatch.setattr(ingest_api, "article_exists", lambda _: False)
    monkeypatch.setattr(ingest_api, "chunk_text", lambda _: ["abc"])
    monkeypatch.setattr(ingest_api, "generate_embeddings", lambda chunks, concurrency=8: [[1.0]])
    monkeypatch.setattr(ingest_api, "create_collection", lambda _: None)
    stored = []
    monkeypatch.setattr(ingest_api, "store_chunks", stored.extend)

    def fail_summary(_):
        raise TimeoutError("ollama timed out")

    monkeypatch.setattr(ingest_api, "summarize_article", fail_summary)

    result = ingest_api._run_ingestion("https://en.wikipedia.org/wiki/Test")

    assert result["status"] == "ok"
    assert result["chunks_stored"] == 1
    assert result["summary_status"] == "failed"
    assert "ollama timed out" in result["summary_error"]
    assert stored


def test_ingest_summary_generation_disabled_skips_summary(monkeypatch):
    old_summary = set_setting("enable_summary_generation", False)
    try:
        monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"title": "Test", "content": "abcdef"})
        monkeypatch.setattr(ingest_api, "article_exists", lambda _: False)
        monkeypatch.setattr(ingest_api, "chunk_text", lambda _: ["abc"])
        monkeypatch.setattr(ingest_api, "generate_embeddings", lambda chunks, concurrency=8: [[1.0]])
        monkeypatch.setattr(ingest_api, "create_collection", lambda _: None)
        monkeypatch.setattr(ingest_api, "store_chunks", lambda points: None)

        def fail_if_called(_):
            raise AssertionError("summarize_article should not be called")

        monkeypatch.setattr(ingest_api, "summarize_article", fail_if_called)

        result = ingest_api._run_ingestion("https://en.wikipedia.org/wiki/Test")
    finally:
        object.__setattr__(ask_api.settings, "enable_summary_generation", old_summary)

    assert result["status"] == "ok"
    assert result["summary_status"] == "disabled"
    assert result["summary"] == "Summary generation disabled."
    assert result["summary_error"] is None


def test_ingest_background_disabled_returns_direct_result(monkeypatch):
    old_background = set_setting("enable_background_ingestion", False)
    try:
        monkeypatch.setattr(
            ingest_api,
            "_run_ingestion",
            lambda url: {"status": "ok", "title": "Test", "chunks_stored": 1},
        )
        response = client.post("/ingest", json={"url": "https://en.wikipedia.org/wiki/Test"})
    finally:
        object.__setattr__(ask_api.settings, "enable_background_ingestion", old_background)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "job_id" not in response.json()


def test_ingest_error_duplicate_and_empty(monkeypatch):
    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"error": "bad URL"})
    with pytest.raises(ingest_api.HTTPException):
        ingest_api._run_ingestion("bad")

    monkeypatch.setattr(ingest_api, "extract_wikipedia_article", lambda _: {"title": "Test", "content": "text"})
    monkeypatch.setattr(ingest_api, "article_exists", lambda _: True)
    assert ingest_api._run_ingestion("url")["status"] == "exists"

    monkeypatch.setattr(ingest_api, "article_exists", lambda _: False)
    monkeypatch.setattr(ingest_api, "chunk_text", lambda _: [])
    with pytest.raises(ingest_api.HTTPException):
        ingest_api._run_ingestion("url")


def test_ask_uses_retrieved_context(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    chunks = [{"title": "Test", "chunk_number": 2, "text": "grounded fact", "url": "url", "score": .9}]
    monkeypatch.setattr(ask_api, "search_chunks", lambda embedding, limit: chunks)
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: f"{question}: grounded fact [1]")
    response = client.get("/ask", params={"question": "Why?"})
    assert response.status_code == 200
    assert "grounded fact" in response.json()["answer"]
    assert response.json()["sources"][0]["citation"] == 1
    assert response.json()["sources"][0]["chunk_number"] == 2
    assert response.json()["citations_used"] == [1]
    assert response.json()["invalid_citations"] == []
    assert response.json()["missing_citations"] is False
    assert response.json()["citation_retry_used"] is False

    monkeypatch.setattr(ask_api, "search_chunks", lambda embedding, limit: [])
    assert client.get("/ask", params={"question": "Why?"}).status_code == 404


def test_ask_reports_hallucinated_citations(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "unsupported citation [9]")
    monkeypatch.setattr(ask_api, "repair_citations", lambda question, draft, context: draft)

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 200
    assert response.json()["citations_used"] == [9]
    assert response.json()["invalid_citations"] == [9]
    assert response.json()["missing_citations"] is False
    assert response.json()["citation_retry_used"] is True
    assert response.json()["citation_repaired"] is True
    assert response.json()["sources"][0]["citation"] == 1


def test_ask_citation_repair_disabled_keeps_validation_metadata(monkeypatch):
    old_repair = set_setting("enable_citation_repair", False)
    try:
        monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
        monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
        )
        calls = []

        def answer_once(question, context):
            calls.append(question)
            return "grounded answer without marker"

        monkeypatch.setattr(ask_api, "answer_question", answer_once)

        response = client.get("/ask", params={"question": "Why?"})
    finally:
        object.__setattr__(ask_api.settings, "enable_citation_repair", old_repair)

    assert response.status_code == 200
    assert len(calls) == 1
    assert response.json()["missing_citations"] is True
    assert response.json()["invalid_citations"] == []
    assert response.json()["citation_retry_used"] is False


def test_ask_multi_query_keeps_invalid_citation_detection(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: ["query one", "query two", "query three"])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda query: query)
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda query, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "unsupported citation [8]")
    monkeypatch.setattr(ask_api, "repair_citations", lambda question, draft, context: draft)

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 200
    assert response.json()["retrieval_queries"] == ["Why?", "query one", "query two", "query three"]
    assert response.json()["citations_used"] == [8]
    assert response.json()["invalid_citations"] == [8]
    assert response.json()["citation_retry_used"] is True
    assert response.json()["citation_repaired"] is True


def test_ask_reports_missing_citations(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded answer without marker")
    monkeypatch.setattr(ask_api, "repair_citations", lambda question, draft, context: draft)

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 200
    assert response.json()["citations_used"] == []
    assert response.json()["invalid_citations"] == []
    assert response.json()["missing_citations"] is True
    assert response.json()["citation_retry_used"] is True
    assert response.json()["citation_repaired"] is True
    assert response.json()["sources"][0]["citation"] == 1


def test_ask_retries_when_answer_has_no_citations(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
    )

    answer_calls = []

    def answer_once(question, context):
        answer_calls.append(question)
        return "grounded answer without marker"

    monkeypatch.setattr(ask_api, "answer_question", answer_once)
    monkeypatch.setattr(ask_api, "repair_citations", lambda question, draft, context: "grounded answer with marker [1]")

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 200
    assert len(answer_calls) == 1
    assert response.json()["answer"] == "grounded answer with marker [1]"
    assert response.json()["citations_used"] == [1]
    assert response.json()["invalid_citations"] == []
    assert response.json()["missing_citations"] is False
    assert response.json()["citation_retry_used"] is True
    assert response.json()["citation_repaired"] is True


def test_ask_flags_repair_that_appends_citation_on_own_line(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
    )

    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded answer without marker")
    monkeypatch.setattr(ask_api, "repair_citations", lambda question, draft, context: "grounded answer still not inline.\n\n[1]")

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "grounded answer still not inline.\n\n[1]"
    assert response.json()["citations_used"] == [1]
    assert response.json()["invalid_citations"] == []
    assert response.json()["missing_citations"] is True
    assert response.json()["citation_retry_used"] is True
    assert response.json()["citation_repaired"] is True


def test_ask_rejects_prompt_leaking_citation_repair(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded answer without marker")
    monkeypatch.setattr(
        ask_api,
        "repair_citations",
        lambda question, draft, context: "You are repairing citation formatting.\n\nRewrite the draft answer sentence by sentence.",
    )

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "grounded answer without marker"
    assert response.json()["citations_used"] == []
    assert response.json()["invalid_citations"] == []
    assert response.json()["missing_citations"] is True
    assert response.json()["citation_retry_used"] is True
    assert response.json()["citation_repaired"] is False


def test_ask_does_not_store_prompt_leak_answer(monkeypatch):
    old_repair = set_setting("enable_citation_repair", False)
    try:
        monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
        monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
        )
        monkeypatch.setattr(
            ask_api,
            "answer_question",
            lambda question, context: "Bad format:\nYou are repairing citation formatting.",
        )

        response = client.get("/ask", params={"question": "Why?", "conversation_id": "conv-leak"})
    finally:
        object.__setattr__(ask_api.settings, "enable_citation_repair", old_repair)

    assert response.status_code == 200
    assert response.json()["answer"] == "Bad format:\nYou are repairing citation formatting."
    assert conversation.get_recent_turns("conv-leak") == []


def test_ask_removes_wikipedia_reference_markers_from_llm_context(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{
            "title": "Fish",
            "chunk_number": 15,
            "text": "Some 400 species of fish can breathe air.[55]",
        }],
    )

    captured = {}

    def answer_with_context(question, context):
        captured["context"] = context
        return "Some fish can breathe air [1]"

    monkeypatch.setattr(ask_api, "answer_question", answer_with_context)

    response = client.get("/ask", params={"question": "Can fish breathe air?"})

    assert response.status_code == 200
    assert "[55]" not in captured["context"]
    assert "[1]" in captured["context"]
    assert response.json()["invalid_citations"] == []


def test_ask_answer_generation_timeout_returns_gateway_timeout(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 5, "text": "grounded fact"}],
    )

    def fail_answer(question, context):
        raise requests.Timeout("ollama timed out")

    monkeypatch.setattr(ask_api, "answer_question", fail_answer)

    response = client.get("/ask", params={"question": "Why?"})

    assert response.status_code == 504
    assert "Answer generation timed out" in response.json()["detail"]


def test_ask_stream_returns_token_and_final_events(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "stream_answer_question", lambda question, context: iter(["grounded ", "fact [1]"]))

    response = client.get("/ask/stream", params={"question": "Why?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: token\ndata: {"text": "grounded "}' in response.text
    assert 'event: token\ndata: {"text": "fact [1]"}' in response.text
    assert "event: final" in response.text
    assert '"answer": "grounded fact [1]"' in response.text
    assert '"invalid_citations": []' in response.text
    assert '"missing_citations": false' in response.text


def test_ask_stream_final_event_contains_invalid_citation_metadata(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "stream_answer_question", lambda question, context: iter(["bad citation [9]"]))

    response = client.get("/ask/stream", params={"question": "Why?"})

    assert response.status_code == 200
    assert "event: final" in response.text
    assert '"invalid_citations": [9]' in response.text
    assert '"citation_repaired": false' in response.text


def test_ask_stream_returns_error_event_on_stream_failure(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
    )

    def fail_stream(question, context):
        yield "partial"
        raise requests.Timeout("ollama timed out")

    monkeypatch.setattr(ask_api, "stream_answer_question", fail_stream)

    response = client.get("/ask/stream", params={"question": "Why?"})

    assert response.status_code == 200
    assert 'event: token\ndata: {"text": "partial"}' in response.text
    assert "event: error" in response.text
    assert "Answer streaming failed" in response.text


def test_stream_answer_question_yields_ollama_tokens(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter([
                json.dumps({"response": "hello ", "done": False}).encode("utf-8"),
                json.dumps({"response": "world", "done": False}).encode("utf-8"),
                json.dumps({"done": True}).encode("utf-8"),
            ])

        def close(self):
            return None

    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(llm.requests, "post", fake_post)

    tokens = list(llm.stream_answer_question("question?", "context"))

    assert tokens == ["hello ", "world"]
    assert calls[0][1]["json"]["stream"] is True
    assert calls[0][1]["json"]["keep_alive"] == "10m"
    assert calls[0][1]["json"]["options"] == llm.ANSWER_OPTIONS
    assert calls[0][1]["stream"] is True


def test_answer_question_uses_generation_latency_options(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "answer [1]"}

    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(llm.requests, "post", fake_post)

    assert llm.answer_question("question?", "[1] context") == "answer [1]"
    payload = calls[0][1]["json"]
    assert payload["stream"] is False
    assert payload["keep_alive"] == "10m"
    assert payload["options"] == llm.ANSWER_OPTIONS
    assert payload["options"]["num_predict"] == 220


def test_answer_prompt_contains_strict_citation_rules():
    prompt = llm._answer_prompt("What is this?", "[1] source text")

    assert "Write naturally as if speaking to a user" in prompt
    assert 'Do not mention "the context", "the provided context", "the article"' in prompt
    assert "Answer directly" in prompt
    assert "Every factual sentence must end with valid inline citations" in prompt
    assert "Answer with citations" in prompt
    assert "Do not use Wikipedia footnote numbers" in prompt


def test_ask_skips_rewrite_for_clear_standalone_question(monkeypatch):
    def fail_if_called(question):
        raise AssertionError("rewrite_query should not be called")

    monkeypatch.setattr(ask_api, "rewrite_query", fail_if_called)
    embedded = []
    searches = []
    limits = []

    def capture_embedding(text):
        embedded.append(text)
        return [1.0]

    def capture_search(embedding, limit):
        searches.append(embedding)
        limits.append(limit)
        return [{"title": "Fish", "chunk_number": 1, "text": "fish can breathe air"}]

    monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
    monkeypatch.setattr(ask_api, "search_chunks", capture_search)
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "Some fish can breathe air [1]")

    response = client.get("/ask", params={"question": "Do fish breathe air?"})

    assert response.status_code == 200
    assert embedded == ["Do fish breathe air?"]
    assert searches == [[1.0]]
    assert limits == [4]
    assert response.json()["retrieval_queries"] == ["Do fish breathe air?"]


def test_ask_truncates_llm_context_but_returns_full_source(monkeypatch):
    monkeypatch.setattr(ask_api, "generate_embedding", lambda _: [1.0])
    long_text = "A" * 1600
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": long_text}],
    )
    captured = {}

    def answer_with_context(question, context):
        captured["context"] = context
        return "grounded answer [1]"

    monkeypatch.setattr(ask_api, "answer_question", answer_with_context)

    response = client.get("/ask", params={"question": "What is this?"})

    assert response.status_code == 200
    assert long_text not in captured["context"]
    assert "A" * ask_api.LLM_CONTEXT_CHARS in captured["context"]
    assert response.json()["sources"][0]["text"] == long_text
    assert response.json()["context"][0]["text"] == long_text


def test_ask_fans_out_rewritten_queries(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: ["query one", "query two", "query three"])
    embedded = []

    def capture_embedding(text):
        embedded.append(text)
        return [float(len(embedded))]

    monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
    searches = []

    def capture_search(embedding, limit):
        searches.append(embedding)
        return [{"title": "Test", "chunk_number": len(searches), "text": f"fact {len(searches)}"}]

    monkeypatch.setattr(
        ask_api,
        "search_chunks", capture_search
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

    response = client.get("/ask", params={"question": "when?"})

    assert response.status_code == 200
    assert embedded == ["when?", "query one", "query two", "query three"]
    assert searches == [[1.0], [2.0], [3.0], [4.0]]
    assert response.json()["question"] == "when?"
    assert response.json()["retrieval_query"] == "when?"
    assert response.json()["retrieval_queries"] == ["when?", "query one", "query two", "query three"]


def test_ask_query_rewriting_disabled_uses_original_question(monkeypatch):
    old_rewrite = set_setting("enable_query_rewriting", False)
    try:
        def fail_if_called(question):
            raise AssertionError("rewrite_query should not be called")

        monkeypatch.setattr(ask_api, "rewrite_query", fail_if_called)
        embedded = []

        def capture_embedding(text):
            embedded.append(text)
            return [1.0]

        monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
        )
        monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

        response = client.get("/ask", params={"question": "when?"})
    finally:
        object.__setattr__(ask_api.settings, "enable_query_rewriting", old_rewrite)

    assert response.status_code == 200
    assert embedded == ["when?"]
    assert response.json()["retrieval_queries"] == ["when?"]


def test_ask_multi_query_disabled_uses_one_retrieval_query(monkeypatch):
    old_multi = set_setting("enable_multi_query_retrieval", False)
    try:
        monkeypatch.setattr(ask_api, "rewrite_query", lambda question: ["query one", "query two", "query three"])
        embedded = []

        def capture_embedding(text):
            embedded.append(text)
            return [1.0]

        monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
        )
        monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

        response = client.get("/ask", params={"question": "when?"})
    finally:
        object.__setattr__(ask_api.settings, "enable_multi_query_retrieval", old_multi)

    assert response.status_code == 200
    assert embedded == ["query one"]
    assert response.json()["retrieval_queries"] == ["query one"]


def test_ask_rewrites_pronoun_followup(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: ["founding query"])
    embedded = []

    def capture_embedding(text):
        embedded.append(text)
        return [float(len(embedded))]

    monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

    response = client.get("/ask", params={"question": "who founded it?"})

    assert response.status_code == 200
    assert embedded == ["who founded it?", "founding query"]
    assert response.json()["retrieval_queries"] == ["who founded it?", "founding query"]


def test_ask_deduplicates_chunks_from_multiple_queries(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: ["query one"])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda query: query)

    def search_by_query(query, limit):
        if query == "when?":
            return [
                {"title": "Test", "chunk_number": 1, "url": "url", "text": "fact one"},
                {"title": "Test", "chunk_number": 2, "url": "url", "text": "fact two"},
            ]
        return [
            {"title": "Test", "chunk_number": 1, "url": "url", "text": "fact one duplicate"},
            {"title": "Test", "chunk_number": 3, "url": "url", "text": "fact three"},
        ]

    monkeypatch.setattr(ask_api, "search_chunks", search_by_query)
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

    response = client.get("/ask", params={"question": "when?", "top_k": 5})

    assert response.status_code == 200
    assert [chunk["chunk_number"] for chunk in response.json()["context"]] == [1, 2, 3]
    assert [source["citation"] for source in response.json()["sources"]] == [1, 2, 3]


def test_ask_deduplicates_chunks_by_text_when_stable_id_missing(monkeypatch):
    monkeypatch.setattr(ask_api, "rewrite_query", lambda question: ["query one"])
    monkeypatch.setattr(ask_api, "generate_embedding", lambda query: query)
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda query, limit: [
            {"title": "Test", "text": "same fact"},
            {"title": "Test", "text": "same fact"},
            {"title": "Test", "text": "other fact"},
        ],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

    response = client.get("/ask", params={"question": "when?", "top_k": 5})

    assert response.status_code == 200
    assert [chunk["text"] for chunk in response.json()["context"]] == ["same fact", "other fact"]


def test_ask_falls_back_to_original_query_when_rewrite_fails(monkeypatch):
    def fail_rewrite(question):
        raise requests.Timeout("rewrite timed out")

    monkeypatch.setattr(ask_api, "rewrite_query", fail_rewrite)
    embedded = []

    def capture_embedding(text):
        embedded.append(text)
        return [1.0]

    monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
    monkeypatch.setattr(
        ask_api,
        "search_chunks",
        lambda embedding, limit: [{"title": "Test", "chunk_number": 1, "text": "grounded fact"}],
    )
    monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "grounded fact [1]")

    response = client.get("/ask", params={"question": "when?"})

    assert response.status_code == 200
    assert embedded == ["when?"]
    assert response.json()["retrieval_query"] == "when?"
    assert response.json()["retrieval_queries"] == ["when?"]


def test_ask_stores_turn_and_uses_resolved_question(monkeypatch):
    old_memory = set_setting("enable_conversation_memory", True)
    try:
        conversation.add_turn("conv-ask", "Who founded Python?", "Guido van Rossum founded Python [1].")
        monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
        embedded = []
        answered = []

        def capture_embedding(text):
            embedded.append(text)
            return [1.0]

        def capture_answer(question, context):
            answered.append(question)
            return "Python was first released in 1991 [1]"

        monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Python", "chunk_number": 1, "text": "Python was first released in 1991."}],
        )
        monkeypatch.setattr(ask_api, "answer_question", capture_answer)

        response = client.get("/ask", params={"question": "When?", "conversation_id": "conv-ask"})
    finally:
        object.__setattr__(ask_api.settings, "enable_conversation_memory", old_memory)

    assert response.status_code == 200
    assert response.json()["question"] == "When?"
    assert response.json()["resolved_question"] == (
        "When? (referring to the previous question: Who founded Python?)"
    )
    assert embedded == [response.json()["resolved_question"]]
    assert answered == [response.json()["resolved_question"]]
    assert conversation.get_recent_turns("conv-ask")[-1] == {
        "question": "When?",
        "answer": "Python was first released in 1991 [1]",
    }


def test_ask_memory_disabled_does_not_resolve_or_store(monkeypatch):
    old_memory = set_setting("enable_conversation_memory", False)
    try:
        conversation.add_turn("conv-disabled", "Who founded Python?", "Guido van Rossum founded Python [1].")
        monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
        embedded = []

        def capture_embedding(text):
            embedded.append(text)
            return [1.0]

        monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Python", "chunk_number": 1, "text": "Python was first released in 1991."}],
        )
        monkeypatch.setattr(ask_api, "answer_question", lambda question, context: "Python was first released in 1991 [1]")

        response = client.get("/ask", params={"question": "When?", "conversation_id": "conv-disabled"})
    finally:
        object.__setattr__(ask_api.settings, "enable_conversation_memory", old_memory)

    assert response.status_code == 200
    assert response.json()["question"] == "When?"
    assert response.json()["resolved_question"] == "When?"
    assert embedded == ["When?"]
    assert len(conversation.get_recent_turns("conv-disabled")) == 1


def test_ask_stream_stores_turn_and_final_event_has_resolved_question(monkeypatch):
    old_memory = set_setting("enable_conversation_memory", True)
    try:
        conversation.add_turn("conv-stream", "Who created Linux?", "Linus Torvalds created Linux [1].")
        monkeypatch.setattr(ask_api, "rewrite_query", lambda question: [])
        streamed = []

        def capture_embedding(text):
            return [1.0]

        def capture_stream(question, context):
            streamed.append(question)
            return iter(["It was created in 1991 [1]"])

        monkeypatch.setattr(ask_api, "generate_embedding", capture_embedding)
        monkeypatch.setattr(
            ask_api,
            "search_chunks",
            lambda embedding, limit: [{"title": "Linux", "chunk_number": 1, "text": "Linux was created in 1991."}],
        )
        monkeypatch.setattr(ask_api, "stream_answer_question", capture_stream)

        response = client.get("/ask/stream", params={"question": "When?", "conversation_id": "conv-stream"})
    finally:
        object.__setattr__(ask_api.settings, "enable_conversation_memory", old_memory)

    assert response.status_code == 200
    assert streamed == ["When? (referring to the previous question: Who created Linux?)"]
    assert '"question": "When?"' in response.text
    assert '"resolved_question": "When? (referring to the previous question: Who created Linux?)"' in response.text
    assert conversation.get_recent_turns("conv-stream")[-1] == {
        "question": "When?",
        "answer": "It was created in 1991 [1]",
    }


def test_rewrite_query_cache_prevents_second_ollama_call(monkeypatch):
    llm._rewrite_cache.clear()
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "query one\nquery two\nquery three"}

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(llm.requests, "post", fake_post)

    first = llm.rewrite_query("When?")
    second = llm.rewrite_query("  when?  ")

    assert first == ["query one", "query two", "query three"]
    assert second == ["query one", "query two", "query three"]
    assert len(calls) == 1
