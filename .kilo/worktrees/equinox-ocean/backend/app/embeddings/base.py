"""Embedding provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    name: str = "base"
    dimensions: int = 384

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a list of vectors of equal length."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
