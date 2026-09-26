"""Qdrant vector store adapter.

Runs in embedded local mode when ``JAIL_QDRANT_URL`` is empty (no server
required), or against a Qdrant server when configured. Payload filters enforce
tenant isolation + jurisdiction/domain/date/source-status guardrails.
"""

from __future__ import annotations

import contextlib
import os
import threading
import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from app.config import get_settings
from app.core.errors import VectorStoreError
from app.vectorstore.base import SearchHit, VectorStore

_ID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
_local_clients: dict[str, QdrantClient] = {}
_client_lock = threading.Lock()


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


def _point_id(oid: str) -> Any:
    """Qdrant requires UUID point ids; deterministically map opaque ids."""
    if _valid_uuid(oid):
        return oid
    return str(uuid.uuid5(_ID_NS, oid))


class QdrantStore(VectorStore):
    name = "qdrant"

    def __init__(self, url: str = "", path: str = "", api_key: str = "") -> None:
        s = get_settings()
        self.dimensions = s.embedding_dimensions
        q_url = url or s.qdrant_url
        q_key = api_key or s.qdrant_api_key
        if q_url:
            self.client = QdrantClient(url=q_url, api_key=q_key or None, timeout=30)
            self.local = False
            self._lock = None
        else:
            q_path = os.path.abspath(path or s.qdrant_path)
            with _client_lock:
                if q_path not in _local_clients:
                    _local_clients[q_path] = QdrantClient(
                        path=q_path,
                        force_disable_check_same_thread=True,
                    )
                self.client = _local_clients[q_path]
            self.local = True
            self._lock = threading.RLock()

    @contextlib.contextmanager
    def _guard(self):
        if self._lock is not None:
            with self._lock:
                yield
        else:
            yield

    def ensure_collection(self, name: str, dimensions: int | None = None) -> None:
        dim = dimensions or self.dimensions
        with self._guard():
            existing = self.client.get_collections().collections
            if not any(c.name == name for c in existing):
                try:
                    self.client.create_collection(
                        collection_name=name,
                        vectors_config=models.VectorParams(
                            size=dim, distance=models.Distance.COSINE
                        ),
                    )
                except Exception as exc:
                    raise VectorStoreError(
                        f"Qdrant collection `{name}` creation failed: {exc}"
                    ) from exc
            for field in [
                "organization_id",
                "jurisdiction",
                "domain",
                "document_id",
                "source_status",
                "doc_type",
                "document_category",
            ]:
                # Payload indexes are best-effort: they speed up keyword filters
                # but the store works (slower) without them.
                with contextlib.suppress(Exception):
                    self.client.create_payload_index(
                        collection_name=name,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

    def upsert(
        self,
        name: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict] | None = None,
    ) -> None:
        points = [
            models.PointStruct(
                id=_point_id(oid), vector=vector, payload=(payloads or [{}])[i]
            )
            for i, (oid, vector) in enumerate(zip(ids, vectors))
        ]
        with self._guard():
            try:
                self.client.upsert(collection_name=name, points=points)
            except Exception as exc:
                raise VectorStoreError(f"Qdrant upsert failed: {exc}") from exc

    def search(
        self,
        name: str,
        vector: list[float],
        *,
        filters: dict | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        query_filter = self._build_filter(filters) if filters else None
        with self._guard():
            try:
                hits = self.client.query_points(
                    collection_name=name,
                    query=vector,
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                ).points
            except Exception as exc:
                raise VectorStoreError(f"Qdrant search failed: {exc}") from exc
        return [
            SearchHit(
                id=str(h.id),
                score=float(h.score),
                text=str((h.payload or {}).get("text", "")),
                metadata={k: v for k, v in (h.payload or {}).items() if k != "text"},
            )
            for h in hits
        ]

    def delete(
        self, name: str, ids: list[str] | None = None, filters: dict | None = None
    ) -> None:
        with self._guard():
            try:
                if ids:
                    self.client.delete(
                        collection_name=name,
                        points_selector=models.PointIdsList(
                            points=[_point_id(i) for i in ids]
                        ),
                    )
                elif filters:
                    self.client.delete(
                        collection_name=name,
                        points_selector=models.FilterSelector(
                            filter=self._build_filter(filters)
                        ),
                    )
            except Exception as exc:
                raise VectorStoreError(f"Qdrant delete failed: {exc}") from exc

    def count(self, name: str, filters: dict | None = None) -> int:
        with self._guard():
            try:
                return self.client.count(
                    collection_name=name,
                    count_filter=self._build_filter(filters) if filters else None,
                ).count
            except Exception as exc:
                raise VectorStoreError(f"Qdrant count failed: {exc}") from exc

    @staticmethod
    def _build_filter(filters: dict[str, Any]) -> models.Filter:
        must: list[Any] = []
        for key, value in filters.items():
            if isinstance(value, list):
                must.append(
                    models.FieldCondition(key=key, match=models.MatchAny(any=value))
                )
            else:
                must.append(
                    models.FieldCondition(key=key, match=models.MatchValue(value=value))
                )
        return models.Filter(must=must)
