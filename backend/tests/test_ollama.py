from unittest.mock import Mock

from app.services import embedder, llm


def response_with(payload):
    response = Mock()
    response.json.return_value = payload
    return response


def test_generate_embedding(monkeypatch):
    post = Mock(return_value=response_with({"embedding": [0.1, 0.2]}))
    monkeypatch.setattr(embedder.requests, "post", post)
    assert embedder.generate_embedding("hello") == [0.1, 0.2]
    post.return_value.raise_for_status.assert_called_once()
    assert post.call_args.kwargs["json"]["prompt"] == "hello"


def test_summarize_article_truncates_input(monkeypatch):
    post = Mock(return_value=response_with({"response": "summary"}))
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.summarize_article("a" * 7000) == "summary"
    assert "a" * 6001 not in post.call_args.kwargs["json"]["prompt"]


def test_answer_question_includes_context(monkeypatch):
    post = Mock(return_value=response_with({"response": "answer"}))
    monkeypatch.setattr(llm.requests, "post", post)
    assert llm.answer_question("question?", "ground truth") == "answer"
    prompt = post.call_args.kwargs["json"]["prompt"]
    assert "question?" in prompt and "ground truth" in prompt
