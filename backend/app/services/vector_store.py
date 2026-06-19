from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct
)

client = QdrantClient(
    host="localhost",
    port=6333
)

COLLECTION_NAME = "wikipedia_articles"


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


def store_chunk(
    chunk_id: int,
    chunk_text: str,
    embedding: list
):

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=chunk_id,
                vector=embedding,
                payload={
                    "text": chunk_text
                }
            )
        ]
    )

def search_chunks(
    query_embedding: list,
    limit: int = 3
):

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=limit
    )

    return [
        point.payload["text"]
        for point in results.points
    ]