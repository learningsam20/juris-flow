"""Vertex AI Vector Search adapter (production path, PRD §7.1).

Requires ``JAIL_VECTOR_PROVIDER=vertex`` and cloud packages from
``backend/requirements-cloud.txt``. Because index deployment is an async GCP
operation, this adapter targets an already-deployed index endpoint and performs
point-level upserts via IndexEndpoint.vector_search.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.core.errors import VectorStoreError
from app.vectorstore.base import SearchHit, VectorStore


class VertexVectorSearchStore(VectorStore):
    name = "vertex"

    def __init__(self) -> None:
        s = get_settings()
        self.project = s.vertex_project
        self.location = s.vertex_location
        self.index = s.vertex_vector_index
        self.endpoint = s.vertex_vector_endpoint
        self.dimensions = s.embedding_dimensions
        self.distance = s.vertex_vector_distance
        self._ready = False

    def _aiplatform(self):
        try:
            from google.cloud import (
                aiplatform,  # type: ignore[import-not-found,import-untyped]
            )
        except ImportError as exc:
            raise VectorStoreError(
                "Vertex Vector Search selected but `google-cloud-aiplatform` is not installed. "
                "Install backend/requirements-cloud.txt."
            ) from exc
        return aiplatform

    def _require_deployed(self) -> Any:
        s = get_settings()
        if not (s.vertex_vector_index and s.vertex_vector_endpoint):
            raise VectorStoreError(
                "JAIL_VERTEX_VECTOR_INDEX and JAIL_VERTEX_VECTOR_ENDPOINT must be set for Vertex Vector Search."
            )
        aiplatform = self._aiplatform()
        return aiplatform.MatchingEngineIndex(
            s.vertex_vector_index
        ), aiplatform.MatchingEngineIndexEndpoint(s.vertex_vector_endpoint)

    def ensure_collection(self, name: str, dimensions: int | None = None) -> None:
        # Vertex index creation/deployment is an asynchronous GCP operation and
        # is intentionally out of band. No-op: index must exist before runtime.
        return None

    def upsert(
        self,
        name: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict] | None = None,
    ) -> None:
        _, endpoint = self._require_deployed()
        try:
            endpoint.upsert_datapoints(
                datapoints=[
                    {
                        "datapoint_id": oid,
                        "feature_vector": vector,
                        "restricts": self._restricts(payloads[i] if payloads else {}),
                    }
                    for i, (oid, vector) in enumerate(zip(ids, vectors))
                ]
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Vertex Vector Search upsert failed: {exc}"
            ) from exc

    def search(
        self,
        name: str,
        vector: list[float],
        *,
        filters: dict | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        _, endpoint = self._require_deployed()
        try:
            resp = endpoint.find_neighbors(
                queries=[vector], num_neighbors=top_k, restrict=filters or {}
            )
        except Exception as exc:
            raise VectorStoreError(f"Vertex Vector Search query failed: {exc}") from exc
        hits: list[SearchHit] = []
        for neighbor in (resp or [])[0:1]:
            for n in neighbor or []:
                hits.append(
                    SearchHit(
                        id=n.datapoint_id,
                        score=float(n.distance),
                        text="",
                        metadata=self._metadata(n),
                    )
                )
        return hits

    def delete(
        self, name: str, ids: list[str] | None = None, filters: dict | None = None
    ) -> None:
        _, endpoint = self._require_deployed()
        try:
            endpoint.remove_datapoints(ids=ids or [], index_name=self.index)
        except Exception as exc:
            raise VectorStoreError(
                f"Vertex Vector Search delete failed: {exc}"
            ) from exc

    def count(self, name: str, filters: dict | None = None) -> int:
        raise VectorStoreError(
            "Vertex Vector Search count requires GCP point listing; use document meta instead."
        )

    @staticmethod
    def _restricts(payload: dict) -> list[dict]:
        out = []
        for key in ("organization_id", "jurisdiction", "domain", "source_status"):
            if payload.get(key):
                out.append({"namespace": key, "allow": [str(payload[key])]})
        return out

    @staticmethod
    def _metadata(n: Any) -> dict:
        data = getattr(n, "datapoint_metadata", None) or {}
        if hasattr(n, "crowding_tag"):
            data["crowding_tag"] = n.crowding_tag
        return dict(data)
