"""Embedding provider factory (JAIL_EMBEDDING_PROVIDER)."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.core.errors import EmbeddingError
from app.embeddings.base import EmbeddingProvider

PROVIDERS = {
    "ollama": "app.embeddings.ollama:OllamaEmbeddingProvider",
    "vertex": "app.embeddings.vertex:VertexEmbeddingProvider",
}


@lru_cache(maxsize=4)
def get_embeddings(provider: str | None = None) -> EmbeddingProvider:
    name = provider or get_settings().embedding_provider
    entry = PROVIDERS.get(name)
    if not entry:
        raise EmbeddingError(f"Unknown embedding provider `{name}`")
    module_path, class_name = entry.split(":")
    from importlib import import_module

    mod = import_module(module_path)
    return getattr(mod, class_name)()
