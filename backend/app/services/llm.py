import requests


OLLAMA_URL = "http://localhost:11434/api/generate"


def summarize_article(article_text: str) -> str:
    prompt = f"""
Summarize the following Wikipedia article in 5 concise bullet points.

Article:
{article_text[:6000]}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    return result["response"]


def answer_question(
    question: str,
    context: str
):

    prompt = f"""
Use the context below to answer the question.

Context:
{context}

Question:
{question}

Answer:
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False
        }
    )

    response.raise_for_status()

    return response.json()["response"]