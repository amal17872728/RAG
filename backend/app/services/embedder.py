import requests


OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"


def generate_embedding(text: str):

    response = requests.post(
        OLLAMA_EMBED_URL,
        json={
            "model": "nomic-embed-text",
            "prompt": text
        }
    )

    response.raise_for_status()

    return response.json()["embedding"]