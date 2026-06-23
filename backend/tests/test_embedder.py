import asyncio
import types

import pytest

from app.services import embedder


def test_generate_embedding_sync(monkeypatch):
    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embedding": [0.1, 0.2, 0.3]}

    def fake_post(url, json=None, timeout=None):
        return DummyResp()

    monkeypatch.setattr(embedder, "requests", types.SimpleNamespace(post=fake_post))

    emb = embedder.generate_embedding("hello world")
    assert isinstance(emb, list)
    assert emb == [0.1, 0.2, 0.3]


def test_generate_embeddings_async_cache_and_call(monkeypatch, tmp_path):
    texts = ["one", "two"]

    # make cache return a value for the first text
    keys = [embedder._hash_text(t) for t in texts]
    cached = {keys[0]: [9.9, 9.9]}

    def fake_load_cache(key):
        return cached.get(key)

    monkeypatch.setattr(embedder, "_load_cache", fake_load_cache)

    async def fake_embed_single(client, text):
        # return different embedding depending on text
        return [len(text), 0.0]

    monkeypatch.setattr(embedder, "_embed_single", fake_embed_single)

    res = asyncio.run(embedder.generate_embeddings_async(texts, concurrency=2))
    assert res[0] == [9.9, 9.9]
    assert res[1] == [3, 0.0]


def test_generate_embeddings_wrapper(monkeypatch):
    texts = ["a", "bb"]

    async def fake_async(texts, concurrency=8):
        return [[1], [2]]

    monkeypatch.setattr(embedder, "generate_embeddings_async", fake_async)

    res = embedder.generate_embeddings(texts)
    assert res == [[1], [2]]
