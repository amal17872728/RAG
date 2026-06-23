
import requests
import os
import json
import hashlib
import asyncio
import httpx

from app.core.config import settings

os.makedirs(settings.embed_cache_dir, exist_ok=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(settings.embed_cache_dir, f"{key}.json")


def _load_cache(key: str):
    p = _cache_path(key)
    if os.path.exists(p):
        try:
            return json.load(open(p, "r"))
        except Exception:
            return None
    return None


def _write_cache(key: str, embedding):
    try:
        json.dump(embedding, open(_cache_path(key), "w"))
    except Exception:
        pass


def generate_embedding(text: str):
    """Synchronous single embedding (kept for backwards compatibility)."""
    response = requests.post(
        f"{settings.ollama_base_url}/api/embeddings",
        json={
            "model": settings.embed_model,
            "prompt": text
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["embedding"]


async def _embed_single(client: httpx.AsyncClient, text: str):
    resp = await client.post(
        f"{settings.ollama_base_url}/api/embeddings",
        json={"model": settings.embed_model, "prompt": text},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


async def generate_embeddings_async(texts: list[str], concurrency: int = 8) -> list:
    """Return embeddings in same order as texts. Uses disk cache and concurrent HTTP calls."""
    results = [None] * len(texts)

    to_request = []
    for i, t in enumerate(texts):
        key = _hash_text(t)
        cached = _load_cache(key)
        if cached is not None:
            results[i] = cached
        else:
            to_request.append((i, t, key))

    if not to_request:
        return results

    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        async def worker(idx, text, key):
            async with semaphore:
                emb = await _embed_single(client, text)
                _write_cache(key, emb)
                results[idx] = emb

        tasks = [asyncio.create_task(worker(i, text, key)) for (i, text, key) in to_request]
        await asyncio.gather(*tasks)

    return results


def generate_embeddings(texts: list[str], concurrency: int = 8) -> list:
    """Sync wrapper for convenience (calls async implementation)."""
    return asyncio.run(generate_embeddings_async(texts, concurrency=concurrency))
