import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _get_csv(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = _get_int("QDRANT_PORT", 6333)
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "wikipedia_articles")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    chat_model: str = os.getenv("CHAT_MODEL", "qwen2.5:3b")
    embed_model: str = os.getenv("EMBED_MODEL", "nomic-embed-text")
    embed_cache_dir: str = os.getenv("EMBED_CACHE_DIR", "/tmp/emb_cache")
    enable_streaming: bool = _get_bool("ENABLE_STREAMING", True)
    enable_citation_repair: bool = _get_bool("ENABLE_CITATION_REPAIR", True)
    enable_query_rewriting: bool = _get_bool("ENABLE_QUERY_REWRITING", True)
    enable_multi_query_retrieval: bool = _get_bool("ENABLE_MULTI_QUERY_RETRIEVAL", True)
    enable_conversation_memory: bool = _get_bool("ENABLE_CONVERSATION_MEMORY", True)
    enable_summary_generation: bool = _get_bool("ENABLE_SUMMARY_GENERATION", True)
    enable_background_ingestion: bool = _get_bool("ENABLE_BACKGROUND_INGESTION", True)
    enable_perf_logs: bool = _get_bool("ENABLE_PERF_LOGS", True)
    enable_citation_debug_logs: bool = _get_bool("ENABLE_CITATION_DEBUG_LOGS", False)
    enable_memory_debug_logs: bool = _get_bool("ENABLE_MEMORY_DEBUG_LOGS", False)
    cors_origins: list[str] = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "cors_origins",
            _get_csv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
            ),
        )


settings = Settings()
