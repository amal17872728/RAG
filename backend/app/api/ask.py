from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import json
import re
import requests
import time
import uuid

from app.core.config import settings
from app.services import conversation
from app.services.embedder import generate_embedding
from app.services.vector_store import search_chunks
from app.services.llm import answer_question, repair_citations, rewrite_query, stream_answer_question
from app.services import llm as llm_service

router = APIRouter()
LLM_CONTEXT_CHARS = 1200


def _ms(seconds: float) -> int:
    return round(seconds * 1000)


def _perf_log(request_id: str, message: str):
    if settings.enable_perf_logs:
        print(f"[PERF] Request ID: {request_id} | {message}", flush=True)


def _citation_debug(request_id: str, message: str):
    if settings.enable_citation_debug_logs:
        print(f"[CITATION_DEBUG] Request ID: {request_id} | {message}", flush=True)


def _memory_debug(request_id: str, message: str):
    if settings.enable_memory_debug_logs:
        print(f"[MEMORY_DEBUG] Request ID: {request_id} | {message}", flush=True)


def _citation_sources(chunks: list[dict]) -> list[dict]:
    sources = []
    for citation, chunk in enumerate([c for c in chunks if c.get("text")], start=1):
        sources.append({
            "citation": citation,
            "text": chunk.get("text"),
            "title": chunk.get("title"),
            "chunk_number": chunk.get("chunk_number"),
            "url": chunk.get("url"),
            "score": chunk.get("score"),
        })
    return sources


def _extract_citations(answer: str) -> list[int]:
    return sorted({int(match) for match in re.findall(r"\[(\d+)\]", answer or "")})


def _invalid_citations(answer: str, sources: list[dict]) -> list[int]:
    valid = {source["citation"] for source in sources}
    return [citation for citation in _extract_citations(answer) if citation not in valid]


def _has_citation_only_line(answer: str) -> bool:
    return any(
        re.fullmatch(r"(?:\[\d+\]\s*)+[.。]?", line.strip())
        for line in (answer or "").splitlines()
        if line.strip()
    )


def _missing_citations(answer: str, sources: list[dict]) -> bool:
    return bool(sources) and (not _extract_citations(answer) or _has_citation_only_line(answer))


def _context_text(text: str) -> str:
    # Remove Wikipedia reference markers like [55] so the model only sees app citation IDs.
    return re.sub(r"\[\d+\]", "", text or "")


def _llm_context_text(text: str) -> str:
    cleaned = _context_text(text)
    if len(cleaned) <= LLM_CONTEXT_CHARS:
        return cleaned
    return f"{cleaned[:LLM_CONTEXT_CHARS].rstrip()}..."


def _answer_with_timeout(question: str, context: str) -> str:
    try:
        return answer_question(question, context)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Answer generation timed out or failed while calling Ollama: {str(exc)[:200]}",
        ) from exc


def _repair_with_timeout(question: str, draft_answer: str, context: str) -> str:
    try:
        return repair_citations(question, draft_answer, context)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Citation repair timed out or failed while calling Ollama: {str(exc)[:200]}",
        ) from exc


def _has_repair_prompt_leak(answer: str) -> bool:
    leak_phrases = (
        "You are repairing citation formatting",
        "Rewrite the draft answer",
        "Good format:",
        "Bad format:",
    )
    return any(phrase in (answer or "") for phrase in leak_phrases)


def _should_rewrite_query(question: str) -> bool:
    normalized = " ".join((question or "").lower().strip().split())
    if not normalized:
        return False

    short_followups = {"when", "when?", "why", "why?", "how", "how?", "who", "who?", "where", "where?"}
    if normalized in short_followups:
        return True

    followup_phrases = ("what about", "tell me more")
    if any(normalized.startswith(phrase) for phrase in followup_phrases):
        return True

    pronouns = {"it", "its", "they", "them", "their", "this", "that", "these", "those"}
    words = re.findall(r"\b\w+\b", normalized)
    return len(words) <= 4 and any(word in pronouns for word in words)


def _retrieval_queries(question: str, request_id: str | None = None, perf: dict | None = None) -> list[str]:
    rewrite_start = time.perf_counter()
    should_rewrite = _should_rewrite_query(question)
    cache_key = llm_service._normalize_question(question)
    cache_hit = cache_key in llm_service._rewrite_cache

    if not settings.enable_query_rewriting or not should_rewrite:
        if perf is not None:
            perf["rewrite_enabled"] = False
            perf["rewrite_skipped"] = not should_rewrite
            perf["rewrite_cache_hit"] = False
            perf["rewrite_calls"] = 0
            perf["rewrite_ms"] = _ms(time.perf_counter() - rewrite_start)
        if request_id:
            _perf_log(
                request_id,
                (
                    "Query rewriting: skipped | "
                    f"enabled={settings.enable_query_rewriting} | "
                    f"skipped_by_heuristic={not should_rewrite} | "
                    f"cache_hit=false | rewritten_queries=0 | "
                    f"duration={_ms(time.perf_counter() - rewrite_start)} ms"
                ),
            )
        return [question]

    try:
        rewritten = rewrite_query(question)
        rewrite_failed = False
    except Exception:
        rewritten = []
        rewrite_failed = True

    queries = [question]
    for query in rewritten:
        query = str(query).strip()
        if query and query not in queries:
            queries.append(query)

    if not settings.enable_multi_query_retrieval:
        queries = [queries[1] if len(queries) > 1 else question]

    if perf is not None:
        perf["rewrite_enabled"] = True
        perf["rewrite_skipped"] = False
        perf["rewrite_cache_hit"] = cache_hit
        perf["rewrite_calls"] = 0 if cache_hit else 1
        perf["rewrite_failed"] = rewrite_failed
        perf["rewrite_ms"] = _ms(time.perf_counter() - rewrite_start)
    if request_id:
        _perf_log(
            request_id,
            (
                "Query rewriting: "
                f"enabled=true | skipped=false | cache_hit={cache_hit} | "
                f"failed={rewrite_failed} | rewritten_queries={len(queries) - 1} | "
                f"multi_query={settings.enable_multi_query_retrieval} | "
                f"duration={_ms(time.perf_counter() - rewrite_start)} ms"
            ),
        )
    return queries


def _chunk_key(chunk: dict):
    url = chunk.get("url")
    chunk_number = chunk.get("chunk_number")
    if url is not None and chunk_number is not None:
        return ("chunk", url, chunk_number)
    return ("text", " ".join((chunk.get("text") or "").split()))


def _merge_chunks(results: list[list[dict]], limit: int) -> list[dict]:
    merged = []
    seen = set()
    for chunks in results:
        for chunk in chunks:
            key = _chunk_key(chunk)
            if key in seen:
                continue
            seen.add(key)
            merged.append(chunk)
            if len(merged) >= limit:
                return merged
    return merged


def _retrieval_context(question: str, top_k: int, request_id: str | None = None, perf: dict | None = None):
    retrieval_queries = _retrieval_queries(question, request_id=request_id, perf=perf)

    embedding_start = time.perf_counter()
    query_embeddings = []
    for index, query in enumerate(retrieval_queries, start=1):
        one_start = time.perf_counter()
        query_embeddings.append(generate_embedding(query))
        if request_id:
            _perf_log(request_id, f"Embedding #{index}: {_ms(time.perf_counter() - one_start)} ms")
    t_embedding = time.perf_counter() - embedding_start
    if perf is not None:
        perf["embedding_calls"] = len(retrieval_queries)
        perf["embedding_ms"] = _ms(t_embedding)
    if request_id:
        _perf_log(
            request_id,
            f"Embeddings: requests={len(retrieval_queries)} | total={_ms(t_embedding)} ms",
        )

    search_start = time.perf_counter()
    search_results = []
    raw_chunk_count = 0
    for index, query_embedding in enumerate(query_embeddings, start=1):
        one_start = time.perf_counter()
        result = search_chunks(query_embedding, limit=top_k)
        search_results.append(result)
        raw_chunk_count += len(result)
        if request_id:
            _perf_log(
                request_id,
                f"Qdrant search #{index}: {_ms(time.perf_counter() - one_start)} ms | chunks={len(result)}",
            )

    chunks = _merge_chunks(search_results, limit=top_k)
    t_search = time.perf_counter() - search_start
    if perf is not None:
        perf["qdrant_searches"] = len(query_embeddings)
        perf["search_ms"] = _ms(t_search)
        perf["chunks_retrieved"] = raw_chunk_count
        perf["chunks_after_dedupe"] = len(chunks)
    if request_id:
        _perf_log(
            request_id,
            (
                "Vector search: "
                f"searches={len(query_embeddings)} | total={_ms(t_search)} ms | "
                f"chunks_retrieved={raw_chunk_count} | chunks_after_dedupe={len(chunks)}"
            ),
        )

    if not chunks:
        raise HTTPException(status_code=404, detail="No ingested article content was found")

    sources = _citation_sources(chunks)
    if not sources:
        raise HTTPException(status_code=404, detail="No retrieved chunks contained usable text")

    prompt_start = time.perf_counter()
    context_pieces = [
        (
            f"[{source['citation']}]\n"
            f"Title: {source.get('title') or 'Unknown'}\n"
            f"Original chunk: {source.get('chunk_number')}\n"
            f"Text:\n{_llm_context_text(source.get('text'))}"
        )
        for source in sources
    ]
    context = "\n\n---\n\n".join(context_pieces)
    prompt = llm_service._answer_prompt(question, context)
    prompt_build_ms = _ms(time.perf_counter() - prompt_start)
    prompt_chars = len(prompt)
    prompt_tokens_estimate = round(prompt_chars / 4)
    if perf is not None:
        perf["prompt_build_ms"] = prompt_build_ms
        perf["prompt_chars"] = prompt_chars
        perf["prompt_tokens_estimate"] = prompt_tokens_estimate
    if request_id:
        _perf_log(request_id, f"Prompt build: {prompt_build_ms} ms")
        _perf_log(
            request_id,
            f"Prompt size: {prompt_chars:,} chars (~{prompt_tokens_estimate:,} tokens)",
        )

    return {
        "retrieval_queries": retrieval_queries,
        "chunks": chunks,
        "sources": sources,
        "context": context,
        "t_embedding": t_embedding,
        "t_search": t_search,
    }


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _resolved_question(question: str, conversation_id: str | None, request_id: str | None = None) -> str:
    memory_start = time.perf_counter()
    enabled = settings.enable_conversation_memory
    if request_id:
        _perf_log(
            request_id,
            f"Conversation memory: start | enabled={enabled} | conversation_id={conversation_id or ''}",
        )

    if not enabled or not conversation_id:
        overhead_ms = _ms(time.perf_counter() - memory_start)
        if request_id:
            _perf_log(
                request_id,
                (
                    "Conversation memory: skipped | "
                    f"enabled={enabled} | conversation_id={conversation_id or ''} | "
                    f"history_lookup_ms=0 | history_turns=0 | history_tokens_estimate=0 | "
                    "is_follow_up=false | question_changed=false | "
                    f"resolution_ms=0 | overhead_ms={overhead_ms}"
                ),
            )
        return question

    history_start = time.perf_counter()
    turns = conversation.get_recent_turns(conversation_id)
    history_lookup_ms = _ms(time.perf_counter() - history_start)
    history_tokens = conversation.estimate_history_tokens(turns)

    followup_start = time.perf_counter()
    followup_type = conversation.detect_follow_up_type(question)
    is_follow_up = followup_type is not None
    previous_turn = turns[-1] if turns else {}
    previous_question = str(previous_turn.get("question", ""))
    previous_answer = str(previous_turn.get("answer", ""))
    extracted_topic = conversation.extract_topic_from_question(previous_question)
    resolved = conversation.resolve_question(question, turns)
    resolution_ms = _ms(time.perf_counter() - followup_start)
    overhead_ms = _ms(time.perf_counter() - memory_start)
    question_changed = resolved != question

    if request_id:
        _perf_log(
            request_id,
            (
                "Conversation memory: resolved | "
                f"enabled=true | conversation_id={conversation_id} | "
                f"history_lookup_ms={history_lookup_ms} | "
                f"history_turns={len(turns)} | "
                f"history_tokens_estimate={history_tokens} | "
                f"is_follow_up={is_follow_up} | "
                f"resolved_question={resolved!r} | "
                f"question_changed={question_changed} | "
                f"resolution_ms={resolution_ms} | "
                f"overhead_ms={overhead_ms}"
            ),
        )
        _memory_debug(
            request_id,
            (
                f"previous_user_question={previous_question!r} | "
                f"previous_assistant_answer_first_200={previous_answer[:200]!r} | "
                f"extracted_topic={extracted_topic!r} | "
                f"detected_follow_up_type={followup_type!r} | "
                f"resolved_question={resolved!r}"
            ),
        )
    return resolved


def _store_turn(conversation_id: str | None, question: str, answer: str) -> None:
    if settings.enable_conversation_memory and conversation_id and not _has_repair_prompt_leak(answer):
        conversation.add_turn(conversation_id, question, answer)


@router.get("/ask")
def ask(
    question: str = Query(min_length=1),
    top_k: int = Query(4, ge=1, le=10),
    conversation_id: str | None = Query(None),
):
    request_id = str(uuid.uuid4())
    perf = {}
    start_total = time.perf_counter()
    _perf_log(request_id, f"REQUEST start | endpoint=/ask | question={question!r}")

    resolved_question = _resolved_question(question, conversation_id, request_id=request_id)
    retrieval = _retrieval_context(resolved_question, top_k, request_id=request_id, perf=perf)
    retrieval_queries = retrieval["retrieval_queries"]
    chunks = retrieval["chunks"]
    sources = retrieval["sources"]
    context = retrieval["context"]
    _citation_debug(
        request_id,
        f"endpoint=/ask | source_ids={[source['citation'] for source in sources]} | context_first_1000={context[:1000]!r}",
    )
    t_embedding = retrieval["t_embedding"]
    t_search = retrieval["t_search"]

    t0 = time.perf_counter()
    _perf_log(request_id, f"Ollama generation: start | model={settings.chat_model} | streaming=false")
    answer = _answer_with_timeout(resolved_question, context)
    _citation_debug(request_id, f"endpoint=/ask | raw_final_answer_before_validation={answer!r}")
    first_generation_ms = _ms(time.perf_counter() - t0)
    _perf_log(
        request_id,
        f"Ollama generation: {first_generation_ms} ms | model={settings.chat_model} | streaming=false | response_chars={len(answer)}",
    )

    validation_start = time.perf_counter()
    citations_used = _extract_citations(answer)
    invalid_citations = _invalid_citations(answer, sources)
    missing_citations = _missing_citations(answer, sources)
    _citation_debug(
        request_id,
        (
            "endpoint=/ask | validation_result | "
            f"citations_extracted={citations_used} | "
            f"missing_citations={missing_citations} | "
            f"invalid_citations={invalid_citations}"
        ),
    )
    _perf_log(
        request_id,
        (
            "Citation validation: "
            f"{_ms(time.perf_counter() - validation_start)} ms | "
            f"citations_found={len(citations_used)} | "
            f"invalid_citations={len(invalid_citations)} | "
            f"missing_citations={missing_citations}"
        ),
    )
    citation_retry_used = False
    citation_repaired = False
    repair_ms = 0

    if settings.enable_citation_repair and (missing_citations or invalid_citations):
        citation_retry_used = True
        repair_start = time.perf_counter()
        _perf_log(request_id, "Citation repair: triggered")
        original_answer = answer
        repaired_answer = _repair_with_timeout(resolved_question, original_answer, context)
        _citation_debug(request_id, f"endpoint=/ask | raw_repaired_answer_before_validation={repaired_answer!r}")
        repair_ms = _ms(time.perf_counter() - repair_start)
        repair_rejected = _has_repair_prompt_leak(repaired_answer)
        if repair_rejected:
            _perf_log(request_id, "Citation repair: rejected | reason=prompt_leak")
        else:
            answer = repaired_answer
            citation_repaired = True
        _perf_log(
            request_id,
            (
                f"Citation repair: {repair_ms} ms | response_chars={len(repaired_answer)} | "
                f"accepted={citation_repaired} | additional_ollama_calls=1"
            ),
        )
        if citation_repaired:
            validation_start = time.perf_counter()
            citations_used = _extract_citations(answer)
            invalid_citations = _invalid_citations(answer, sources)
            missing_citations = _missing_citations(answer, sources)
            _citation_debug(
                request_id,
                (
                    "endpoint=/ask | validation_result_after_repair | "
                    f"citations_extracted={citations_used} | "
                    f"missing_citations={missing_citations} | "
                    f"invalid_citations={invalid_citations}"
                ),
            )
            _perf_log(
                request_id,
                (
                    "Citation validation after repair: "
                    f"{_ms(time.perf_counter() - validation_start)} ms | "
                    f"citations_found={len(citations_used)} | "
                    f"invalid_citations={len(invalid_citations)} | "
                    f"missing_citations={missing_citations}"
                ),
            )
    else:
        _perf_log(
            request_id,
            f"Citation repair: skipped | enabled={settings.enable_citation_repair}",
        )

    t_generation = first_generation_ms / 1000 + repair_ms / 1000

    t_total = time.perf_counter() - start_total
    total_ollama_calls = (
        perf.get("rewrite_calls", 0)
        + perf.get("embedding_calls", 0)
        + 1
        + (1 if citation_retry_used else 0)
    )
    _perf_log(
        request_id,
        (
            "FINAL RESPONSE: "
            f"total={_ms(t_total)} ms | "
            f"total_ollama_calls={total_ollama_calls} | "
            f"embedding_calls={perf.get('embedding_calls', 0)} | "
            f"qdrant_searches={perf.get('qdrant_searches', 0)}"
        ),
    )
    _store_turn(conversation_id, question, answer)

    return {
        "question": question,
        "resolved_question": resolved_question,
        "retrieval_query": retrieval_queries[0],
        "retrieval_queries": retrieval_queries,
        "answer": answer,
        "context": chunks,
        "sources": sources,
        "citations_used": citations_used,
        "invalid_citations": invalid_citations,
        "missing_citations": missing_citations,
        "citation_retry_used": citation_retry_used,
        "citation_repaired": citation_repaired,
        "timings": {
            "embedding": round(t_embedding, 3),
            "search": round(t_search, 3),
            "generation": round(t_generation, 3),
            "total": round(t_total, 3)
        }
    }


@router.get("/ask/stream")
def ask_stream(
    question: str = Query(min_length=1),
    top_k: int = Query(4, ge=1, le=10),
    conversation_id: str | None = Query(None),
):
    request_id = str(uuid.uuid4())
    perf = {}
    start_total = time.perf_counter()
    _perf_log(request_id, f"REQUEST start | endpoint=/ask/stream | question={question!r}")

    resolved_question = _resolved_question(question, conversation_id, request_id=request_id)
    retrieval = _retrieval_context(resolved_question, top_k, request_id=request_id, perf=perf)
    retrieval_queries = retrieval["retrieval_queries"]
    sources = retrieval["sources"]
    context = retrieval["context"]
    _citation_debug(
        request_id,
        f"endpoint=/ask/stream | source_ids={[source['citation'] for source in sources]} | context_first_1000={context[:1000]!r}",
    )

    def events():
        answer_parts = []
        generation_start = time.perf_counter()
        _perf_log(request_id, f"Ollama generation: start | model={settings.chat_model} | streaming=true")
        try:
            for token in stream_answer_question(resolved_question, context):
                answer_parts.append(token)
                yield _sse_event("token", {"text": token})

            answer = "".join(answer_parts)
            _citation_debug(request_id, f"endpoint=/ask/stream | raw_final_answer_before_validation={answer!r}")
            _perf_log(
                request_id,
                (
                    "Ollama generation: "
                    f"{_ms(time.perf_counter() - generation_start)} ms | "
                    f"model={settings.chat_model} | streaming=true | response_chars={len(answer)}"
                ),
            )
            validation_start = time.perf_counter()
            citations_used = _extract_citations(answer)
            invalid_citations = _invalid_citations(answer, sources)
            missing_citations = _missing_citations(answer, sources)
            _citation_debug(
                request_id,
                (
                    "endpoint=/ask/stream | validation_result | "
                    f"citations_extracted={citations_used} | "
                    f"missing_citations={missing_citations} | "
                    f"invalid_citations={invalid_citations}"
                ),
            )
            _perf_log(
                request_id,
                (
                    "Citation validation: "
                    f"{_ms(time.perf_counter() - validation_start)} ms | "
                    f"citations_found={len(citations_used)} | "
                    f"invalid_citations={len(invalid_citations)} | "
                    f"missing_citations={missing_citations}"
                ),
            )
            _perf_log(request_id, "Citation repair: skipped | streaming=true")
            total_ollama_calls = perf.get("rewrite_calls", 0) + perf.get("embedding_calls", 0) + 1
            _perf_log(
                request_id,
                (
                    "FINAL RESPONSE: "
                    f"total={_ms(time.perf_counter() - start_total)} ms | "
                    f"total_ollama_calls={total_ollama_calls} | "
                    f"embedding_calls={perf.get('embedding_calls', 0)} | "
                    f"qdrant_searches={perf.get('qdrant_searches', 0)}"
                ),
            )
            _store_turn(conversation_id, question, answer)
            yield _sse_event("final", {
                "question": question,
                "resolved_question": resolved_question,
                "answer": answer,
                "sources": sources,
                "citations_used": citations_used,
                "invalid_citations": invalid_citations,
                "missing_citations": missing_citations,
                "citation_retry_used": False,
                "citation_repaired": False,
                "retrieval_queries": retrieval_queries,
            })
        except Exception as exc:
            _perf_log(
                request_id,
                f"Ollama generation: failed after {_ms(time.perf_counter() - generation_start)} ms | streaming=true | error={str(exc)[:200]}",
            )
            yield _sse_event("error", {
                "detail": f"Answer streaming failed while calling Ollama: {str(exc)[:200]}"
            })

    return StreamingResponse(events(), media_type="text/event-stream")
