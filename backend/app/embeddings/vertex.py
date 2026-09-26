"""Vertex AI text-embedding provider (production path)."""

from __future__ import annotations

from app.core.errors import EmbeddingError
from app.embeddings.base import EmbeddingProvider


class VertexEmbeddingProvider(EmbeddingProvider):
    name = "vertex"

    def __init__(self, model: str | None = None, dimensions: int = 768) -> None:
        from app.config import get_settings

        s = get_settings()
        self.model = model or s.vertex_embedding_model
        self.dimensions = dimensions

    def _client(self):
        try:
            import importlib

            genai = importlib.import_module("google.genai")
        except (ImportError, ModuleNotFoundError) as exc:
            raise EmbeddingError(
                "Vertex embedding provider selected but `google-genai` is not installed."
            ) from exc
        from app.config import get_settings

        s = get_settings()
        return genai.Client(
            vertexai=True, project=s.vertex_project, location=s.vertex_location
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._client()
        embeddings: list[list[float]] = []

        # Vertex AI limits: max 250 items and max 20,000 tokens per request.
        # Batching by 10 items keeps each batch comfortably within quota.
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            clean_batch = [t[:8000] if len(t) > 8000 else (t or " ") for t in batch]
            try:
                result = client.models.embed_content(
                    model=self.model, contents=clean_batch
                )
                batch_embeddings = [e.values for e in result.embeddings]
                if not batch_embeddings:
                    raise EmbeddingError("Vertex embedding returned no vectors")
                embeddings.extend(batch_embeddings)
            except Exception as exc:
                raise EmbeddingError(f"Vertex embedding unavailable: {exc}") from exc

        return embeddings
