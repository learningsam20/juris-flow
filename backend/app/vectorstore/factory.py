"""Vector store factory (JAIL_VECTOR_PROVIDER)."""

from __future__ import annotations

import threading
from importlib import import_module

from app.config import get_settings
from app.core.errors import VectorStoreError
from app.vectorstore.base import VectorStore

PROVIDERS = {
    "qdrant": "app.vectorstore.qdrant_store:QdrantStore",
    "vertex": "app.vectorstore.vertex_search:VertexVectorSearchStore",
}

_lock = threading.Lock()
_instances: dict[str, VectorStore] = {}


def get_vectorstore(provider: str | None = None) -> VectorStore:
    raw_name = provider or get_settings().vector_provider
    name = (raw_name or "").lower().strip()
    if name in _instances:
        return _instances[name]
    with _lock:
        if name in _instances:
            return _instances[name]
        entry = PROVIDERS.get(name)
        if not entry:
            raise VectorStoreError(f"Unknown vector store provider `{name}`")
        module_path, class_name = entry.split(":")
        mod = import_module(module_path)
        instance = getattr(mod, class_name)()
        _instances[name] = instance
        return instance


get_vectorstore.cache_clear = _instances.clear  # type: ignore[attr-defined]
