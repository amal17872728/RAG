from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.core.config import settings

client = QdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
)

COLLECTION_NAME = settings.qdrant_collection


def create_collection(vector_size: int):

    collections = client.get_collections()

    existing = [
        c.name
        for c in collections.collections
    ]

    if COLLECTION_NAME not in existing:

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )


def article_exists(url: str) -> bool:
    """Return True if an article with the given URL is already ingested."""

    try:
        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="url",
                        match=MatchValue(value=url)
                    )
                ]
            ),
            limit=1
        )

        return bool(points)

    except Exception as exc:
        if "not found" not in str(exc).lower():
            raise
        return False


def store_chunks(points: list[dict]):
    """Upsert multiple chunks into Qdrant.

    Each point dict must contain: id (str|int), vector, text, title, chunk_number, url
    """

    qdrant_points = []

    for p in points:
        qdrant_points.append(
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload={
                    "text": p.get("text"),
                    "title": p.get("title"),
                    "chunk_number": p.get("chunk_number"),
                    "url": p.get("url")
                }
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=qdrant_points
    )


def search_chunks(
    query_embedding: list,
    limit: int = 3
):
    """Search Qdrant and return list of payload dicts ordered by relevance."""

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=limit,
        with_payload=True,
        with_vectors=False
    )

    out = []
    for r in response.points:
        payload = r.payload or {}
        out.append({
            "text": payload.get("text"),
            "title": payload.get("title"),
            "chunk_number": payload.get("chunk_number"),
            "url": payload.get("url"),
            "score": getattr(r, "score", None)
        })

    return out
