import re
from copy import deepcopy

MAX_TURNS = 4
MAX_HISTORY_TOKENS = 300

_store: dict[str, list[dict[str, str]]] = {}


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(str(text)) / 4))


def _turn_tokens(turn: dict[str, str]) -> int:
    return estimate_tokens(turn.get("question", "")) + estimate_tokens(turn.get("answer", ""))


def estimate_history_tokens(turns: list[dict[str, str]]) -> int:
    return sum(_turn_tokens(turn) for turn in turns)


def trim_history(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    trimmed = list(turns)[-MAX_TURNS:]
    while trimmed and estimate_history_tokens(trimmed) > MAX_HISTORY_TOKENS:
        trimmed.pop(0)
    return trimmed


def add_turn(conversation_id: str, question: str, answer: str) -> None:
    if not conversation_id:
        return

    turns = _store.setdefault(conversation_id, [])
    turns.append({
        "question": str(question or "").strip(),
        "answer": str(answer or "").strip(),
    })
    _store[conversation_id] = trim_history(turns)


def get_recent_turns(conversation_id: str) -> list[dict[str, str]]:
    if not conversation_id:
        return []
    return deepcopy(_store.get(conversation_id, []))


def is_follow_up(question: str) -> bool:
    return detect_follow_up_type(question) is not None


def detect_follow_up_type(question: str) -> str | None:
    normalized = " ".join((question or "").lower().strip().split())
    if not normalized:
        return None

    short_followups = {
        "when", "when?", "why", "why?", "how", "how?", "who", "who?",
        "where", "where?", "what", "what?", "which", "which?",
    }
    if normalized in short_followups:
        return normalized.rstrip("?")

    followup_starts = (
        "what about",
        "tell me more",
        "and ",
        "also ",
        "how about",
        "what else",
    )
    if any(normalized.startswith(prefix) for prefix in followup_starts):
        return "followup_phrase"

    pronouns = {
        "it", "its", "they", "them", "their", "this", "that", "these",
        "those", "he", "him", "his", "she", "her",
    }
    words = re.findall(r"\b\w+\b", normalized)
    if len(words) <= 8 and any(word in pronouns for word in words):
        return "pronoun"
    return None


def extract_topic_from_question(question: str) -> str | None:
    cleaned = str(question or "").strip().rstrip("?!.")
    match = re.match(r"(?i)^who\s+(?:founded|created)\s+(.+)$", cleaned)
    if match:
        return match.group(1).strip()
    return None


def resolve_question(question: str, turns: list[dict[str, str]]) -> str:
    original = str(question or "").strip()
    if not original or not turns or not is_follow_up(original):
        return original

    previous_question = str(turns[-1].get("question", "")).strip()
    if not previous_question:
        return original

    return f"{original} (referring to the previous question: {previous_question})"
