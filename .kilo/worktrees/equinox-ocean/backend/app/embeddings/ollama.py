"""Ollama embedding provider (uses local embedding model, e.g. all-minilm)."""

from __future__ import annotations

import logging

import requests

from app.config import get_settings
from app.core.errors import EmbeddingError
from app.embeddings.base import EmbeddingProvider

logger = logging.getLogger("embeddings.ollama")


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ollama_base_url).rstrip("/")
        self.model = model or s.embedding_model
        self.dimensions = s.embedding_dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings")
            if not embeddings:
                raise EmbeddingError(
                    f"Ollama returned no embeddings for model {self.model}"
                )
            return embeddings
        except requests.RequestException as exc:
            raise EmbeddingError(
                f"Embedding endpoint `{self.base_url}` unavailable: {exc}"
            ) from exc
