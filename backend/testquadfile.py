from app.services.embedder import generate_embedding
from app.services.vector_store import (
    create_collection,
    store_chunk
)

text = "Artificial intelligence is a branch of computer science."

embedding = generate_embedding(text)

create_collection(
    vector_size=len(embedding)
)

store_chunk(
    chunk_id=1,
    chunk_text=text,
    embedding=embedding
)

print("Stored successfully")