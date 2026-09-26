"""Ollama embedding provider (uses local embedding model, e.g. all-minilm)."""

from __future__ import annotations

import logging

import requests

from app.config import get_settings
from app.core.errors import EmbeddingError
from app.embeddings.base import EmbeddingProvider

logger = logging.getLogger("embeddings.ollama")

# Ollama's /api/embed can 400 / reset the runner when a single request
# ships hundreds of long chunks. Keep batches small and sequential.
_DEFAULT_BATCH_SIZE = 32


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ollama_base_url).rstrip("/")
        self.model = model or s.embedding_model
        self.dimensions = s.embedding_dimensions
        self.batch_size = max(1, int(getattr(s, "embedding_batch_size", _DEFAULT_BATCH_SIZE)))

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [t if isinstance(t, str) and t.strip() else " " for t in texts]
        out: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            out.extend(self._embed_batch(batch))
        if len(out) != len(texts):
            raise EmbeddingError(
                f"Ollama returned {len(out)} embeddings for {len(texts)} inputs"
            )
        return out

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.base_url}/api/embed"
        try:
            resp = requests.post(
                url,
                json={"model": self.model, "input": texts},
                timeout=120,
            )
        except requests.RequestException as exc:
            raise EmbeddingError(
                f"Embedding endpoint `{self.base_url}` unavailable: {exc}"
            ) from exc

        if resp.status_code >= 400:
            detail = (resp.text or "").strip()[:400]
            # One retry with half-size batches when the runner rejects a large payload.
            if resp.status_code == 400 and len(texts) > 1:
                logger.warning(
                    "Ollama embed 400 for batch of %s; retrying in halves (%s)",
                    len(texts),
                    detail,
                )
                mid = len(texts) // 2
                return self._embed_batch(texts[:mid]) + self._embed_batch(texts[mid:])
            raise EmbeddingError(
                f"Embedding endpoint `{self.base_url}` unavailable: "
                f"{resp.status_code} {resp.reason} for url: {url}"
                + (f" — {detail}" if detail else "")
            )

        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            raise EmbeddingError(f"Ollama returned no embeddings for model {self.model}")
        return embeddings
