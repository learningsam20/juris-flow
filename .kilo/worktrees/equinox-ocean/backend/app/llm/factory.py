"""LLM provider factory, selected via JAIL_LLM_PROVIDER (.env driven)."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.core.errors import LLMUnavailableError
from app.llm.base import LLMProvider

PROVIDERS = {
    "ollama": "app.llm.ollama:OllamaProvider",
    "vertex": "app.llm.vertex:VertexAIProvider",
}


@lru_cache(maxsize=8)
def get_llm(
    provider: str | None = None,
    model: str | None = None,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMProvider:
    settings = get_settings()
    provider_name = provider or settings.llm_provider
    entry = PROVIDERS.get(provider_name)
    if not entry:
        raise LLMUnavailableError(f"Unknown LLM provider `{provider_name}`")
    module_path, class_name = entry.split(":")
    from importlib import import_module

    mod = import_module(module_path)
    cls = getattr(mod, class_name)
    if model is None and temperature is None and max_tokens is None:
        return cls()
    kwargs: dict[str, object] = {}
    if model:
        kwargs["model"] = model
    # Temperature / max_tokens are supported by local Ollama; Vertex ignores them.
    if provider_name == "ollama":
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
    return cls(**kwargs)
