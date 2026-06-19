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