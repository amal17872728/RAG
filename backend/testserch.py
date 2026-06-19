from app.services.embedder import generate_embedding
from app.services.vector_store import search_chunks

query = "What is artificial intelligence?"

query_embedding = generate_embedding(query)

results = search_chunks(query_embedding)

print(results)