import os

import pytest
import requests


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1 with the Compose stack running")
def test_real_stack_root_and_ollama():
    assert requests.get("http://localhost:8000/", timeout=5).status_code == 200
    tags = requests.get("http://localhost:11434/api/tags", timeout=5)
    tags.raise_for_status()
    chat_model = os.getenv("CHAT_MODEL", "qwen2.5:3b")
    assert any(model["name"].startswith(chat_model) for model in tags.json()["models"])

    article_url = "https://en.wikipedia.org/wiki/Muhammad_Ali_Jinnah"
    ingestion = requests.post(
        "http://localhost:8000/ingest",
        json={"url": article_url},
        timeout=900,
    )
    ingestion.raise_for_status()
    assert ingestion.json()["status"] in {"ok", "exists"}

    answer = requests.get(
        "http://localhost:8000/ask",
        params={"question": "Who founded Pakistan?"},
        timeout=180,
    )
    answer.raise_for_status()
    assert answer.json()["context"]
