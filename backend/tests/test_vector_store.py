from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import vector_store


def test_create_collection_only_when_missing(monkeypatch):
    fake = Mock()
    fake.get_collections.return_value = SimpleNamespace(collections=[])
    monkeypatch.setattr(vector_store, "client", fake)
    vector_store.create_collection(3)
    fake.create_collection.assert_called_once()

    fake.reset_mock()
    fake.get_collections.return_value = SimpleNamespace(collections=[SimpleNamespace(name=vector_store.COLLECTION_NAME)])
    vector_store.create_collection(3)
    fake.create_collection.assert_not_called()


def test_article_exists_and_missing_collection(monkeypatch):
    fake = Mock()
    fake.scroll.return_value = ([SimpleNamespace()], None)
    monkeypatch.setattr(vector_store, "client", fake)
    assert vector_store.article_exists("url") is True

    fake.scroll.return_value = ([], None)
    assert vector_store.article_exists("url") is False

    fake.scroll.side_effect = RuntimeError("collection not found")
    assert vector_store.article_exists("url") is False

    fake.scroll.side_effect = RuntimeError("connection refused")
    with pytest.raises(RuntimeError):
        vector_store.article_exists("url")


def test_store_and_search_chunks(monkeypatch):
    fake = Mock()
    fake.query_points.return_value = SimpleNamespace(points=[
        SimpleNamespace(payload={"text": "chunk", "title": "Title", "chunk_number": 1, "url": "url"}, score=.9),
        SimpleNamespace(payload=None, score=.1),
    ])
    monkeypatch.setattr(vector_store, "client", fake)

    vector_store.store_chunks([{"id": 1, "vector": [1.0], "text": "chunk", "title": "Title", "chunk_number": 1, "url": "url"}])
    assert fake.upsert.call_args.kwargs["points"][0].payload["text"] == "chunk"

    results = vector_store.search_chunks([1.0], limit=2)
    assert results[0]["score"] == .9
    assert results[1]["text"] is None
