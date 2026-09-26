"""Vector store interface (PRD §7.1).

Adapters: Qdrant (embedded local mode for dev; server mode for prod) and
Vertex AI Vector Search. The store enforces metadata filters (organization,
jurisdiction, domain, source status, effective date) at retrieval time so
retrieval guardrails (PRD §15.3) are applied.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchHit:
    id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def document_id(self) -> str | None:
        return self.metadata.get("document_id")

    @property
    def jurisdiction(self) -> str | None:
        return self.metadata.get("jurisdiction")

    @property
    def source_status(self) -> str | None:
        return self.metadata.get("source_status")


class VectorStore(ABC):
    name: str = "base"
    dimensions: int = 384

    @abstractmethod
    def ensure_collection(self, name: str, dimensions: int | None = None) -> None: ...

    @abstractmethod
    def upsert(
        self,
        name: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict] | None = None,
    ) -> None: ...

    @abstractmethod
    def search(
        self,
        name: str,
        vector: list[float],
        *,
        filters: dict | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]: ...

    @abstractmethod
    def delete(
        self, name: str, ids: list[str] | None = None, filters: dict | None = None
    ) -> None: ...

    @abstractmethod
    def count(self, name: str, filters: dict | None = None) -> int: ...
