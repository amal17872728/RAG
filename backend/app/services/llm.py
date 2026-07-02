import json
import re
import requests

from app.core.config import settings

_rewrite_cache = {}
ANSWER_OPTIONS = {
    "num_predict": 220,
    "temperature": 0,
}


def _citation_debug(message: str):
    if settings.enable_citation_debug_logs:
        print(f"[CITATION_DEBUG] {message}", flush=True)


def _context_source_ids(context: str) -> list[int]:
    return sorted({int(match) for match in re.findall(r"^\[(\d+)\]", context or "", flags=re.MULTILINE)})


def summarize_article(article_text: str) -> str:
    prompt = f"""
Summarize the following Wikipedia article in 5 concise bullet points.

Article:
{article_text[:6000]}
"""

    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.chat_model,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    return result["response"]


def _normalize_question(question: str) -> str:
    return " ".join((question or "").lower().split())


def _parse_rewritten_queries(text: str) -> list[str]:
    queries = []
    for line in (text or "").splitlines():
        query = line.strip()
        query = query.lstrip("-*0123456789. )").strip()
        if query:
            queries.append(query)
    return queries[:3]


def rewrite_query(question: str) -> list[str]:
    cache_key = _normalize_question(question)
    if cache_key in _rewrite_cache:
        return _rewrite_cache[cache_key]

    prompt = f"""
Rewrite the user question into exactly 3 concise search queries for retrieving relevant Wikipedia article chunks.
Do not answer the question.
Preserve the user's intent.
Return only one rewritten search query per line.

User question:
{question}

Rewritten search queries:
"""

    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.chat_model,
            "prompt": prompt,
            "stream": False
        },
        timeout=60,
    )

    response.raise_for_status()

    queries = _parse_rewritten_queries(response.json()["response"])
    _rewrite_cache[cache_key] = queries
    return queries


def _answer_prompt(question: str, context: str) -> str:
    return f"""
Answer the question directly using only the retrieved sources below.

Rules:
- Write naturally as if speaking to a user.
- Do not mention "the context", "the provided context", "the article", or similar phrases.
- Do not explain where the information came from.
- Answer directly.
- Keep the answer concise.
- Every factual sentence must end with valid inline citations like [1].
- Use only information supported by the retrieved sources.
- Use only source IDs that appear in the retrieved sources.
- Do not use Wikipedia footnote numbers or any ID not shown in the context.
- If a sentence cannot be supported by a source ID, omit it.
- If the answer is unsupported, say exactly:
I cannot answer this from the provided article context.

Retrieved sources:
{context}

Question:
{question}

Answer with citations:
"""


def answer_question(
    question: str,
    context: str
):
    # If no context is provided, return a clear message instead of calling the LLM.
    if not context or not str(context).strip():
        return "Context not provided. Please ingest the relevant article or provide context before asking."

    prompt = _answer_prompt(question, context)
    _citation_debug(
        "endpoint=answer_question | _answer_prompt_called=true | "
        f"source_ids={_context_source_ids(context)} | "
        f"prompt_first_1000={prompt[:1000]!r}"
    )

    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.chat_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": ANSWER_OPTIONS,
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["response"]


def repair_citations(question: str, draft_answer: str, context: str) -> str:
    prompt = f"""
You are repairing citation formatting.

Rules:
- Rewrite the draft answer sentence by sentence.
- Keep the same meaning.
- Do not add new facts.
- Every factual sentence must end with one or more valid source IDs like [1] or [1][2].
- Use only source IDs shown in the context.
- Do not put citations on their own line.
- Do not add a citation list at the end.
- Output only the repaired answer.

Good format:
Linux is an open-source operating system [1]. It was first released in 1991 [1].

Bad format:
Linux is an open-source operating system. It was first released in 1991.
[1]

Context:
{context}

Original question:
{question}

Draft answer:
{draft_answer}

Repaired answer:
"""
    _citation_debug(
        "endpoint=repair_citations | direct_repair_prompt=true | "
        f"source_ids={_context_source_ids(context)} | "
        f"prompt_first_1000={prompt[:1000]!r}"
    )

    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.chat_model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "10m",
            "options": ANSWER_OPTIONS,
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["response"]


def stream_answer_question(question: str, context: str):
    if not context or not str(context).strip():
        yield "Context not provided. Please ingest the relevant article or provide context before asking."
        return

    prompt = _answer_prompt(question, context)
    _citation_debug(
        "endpoint=stream_answer_question | _answer_prompt_called=true | "
        f"source_ids={_context_source_ids(context)} | "
        f"prompt_first_1000={prompt[:1000]!r}"
    )

    response = requests.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.chat_model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "10m",
            "options": ANSWER_OPTIONS,
        },
        timeout=120,
        stream=True,
    )

    try:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line.decode("utf-8"))
            token = data.get("response", "")
            if token:
                yield token
            if data.get("done"):
                break
    finally:
        close = getattr(response, "close", None)
        if close:
            close()
