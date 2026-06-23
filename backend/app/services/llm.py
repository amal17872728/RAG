import requests
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen2.5:3b")


def summarize_article(article_text: str) -> str:
    prompt = f"""
Summarize the following Wikipedia article in 5 concise bullet points.

Article:
{article_text[:6000]}
"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": CHAT_MODEL,
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
    # If no context is provided, return a clear message instead of calling the LLM.
    if not context or not str(context).strip():
        return "Context not provided. Please ingest the relevant article or provide context before asking."

    prompt = f"""
Use the context below to answer the question.

Context:
{context}

Question:
{question}

Answer:
"""

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": CHAT_MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["response"]
