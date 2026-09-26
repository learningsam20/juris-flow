"""Shared test fixtures.

Environment is pinned to a scratch SQLite DB BEFORE `app.main` is first
imported (config is lru-cached), then every LLM/embedding/vector interaction is
replaced by hermetic fakes so the suite runs fully offline without Ollama.
"""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="jurisflow_tests_"))
_DB = _TMP / "jurisflow.db"

os.environ.setdefault("JAIL_DATABASE_URL", f"sqlite:///{_DB}")
os.environ.setdefault("JAIL_SECRET_KEY", "test-secret-key-that-is-32-bytes-long!!")
os.environ.setdefault("JAIL_LOG_LEVEL", "WARNING")
os.environ.setdefault("JAIL_VECTOR_PROVIDER", "qdrant")
os.environ.setdefault("JAIL_QDRANT_PATH", str(_TMP / "qdrant"))
os.environ["JAIL_DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.setdefault("JAIL_RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("JAIL_TTS_ENABLED", "false")
os.environ.setdefault("JAIL_TTS_PROVIDER", "none")
os.environ["JAIL_TTS_ENABLED"] = "false"
os.environ["JAIL_TTS_PROVIDER"] = "none"

import pytest

# --------------------------------------------------------------------------- #
# Hermetic AI fakes
# --------------------------------------------------------------------------- #
_EXTRACTION_JSON = (
    '{"findings": ['
    '{"clause_type": "termination", "risk_level": "high", '
    '"excerpt": "either party may terminate this Agreement upon 30 days written notice", '
    '"explanation": "Termination requires 30 days notice.", "obligation": true},'
    '{"clause_type": "payment", "risk_level": "medium", '
    '"excerpt": "Payment terms: the company shall remit payment within 30 days of invoice", '
    '"explanation": "Payment due 30 days after invoice.", "obligation": true},'
    '{"clause_type": "dispute_resolution", "risk_level": "medium", '
    '"excerpt": "any dispute shall be resolved by arbitration seated in Singapore", '
    '"explanation": "Arbitration seated in Singapore.", "obligation": false},'
    '{"clause_type": "confidentiality", "risk_level": "high", '
    '"excerpt": "Confidentiality: this Agreement is confidential and non-disclosure", '
    '"explanation": "Confidentiality obligations apply.", "obligation": true}'
    "]}"
)


class FakeLLM:
    name = "fake"

    def chat(
        self, system: str, messages: list[dict], *, max_tokens: int | None = None
    ) -> str:
        # Extraction prompt asks for ONLY a JSON findings object; everything else
        # (agent turns, summaries, Q&A) gets a short deterministic reply.
        if "Return ONLY a JSON object with the shape" in system:
            return _EXTRACTION_JSON
        if "presented the WINNING case" in system:
            return (
                "WINNER: plaintiff\n"
                "RATIONALE: The plaintiff's claim was coherent, grounded in the "
                "retrieved sources, and uncontested on the material facts."
            )
        return "Educational and informational. Not legal advice."


class FakeEmbeddings:
    name = "fake"
    dimensions = 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dimensions for _ in texts]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class FakeVectorstore:
    """Trivial in-memory vector store matching the VectorStore interface."""

    name = "fake"
    dimensions = 384

    def __init__(self) -> None:
        self._points: dict[str, dict[str, tuple[list[float], dict]]] = {}

    def ensure_collection(self, name: str, dimensions: int | None = None) -> None:
        self._points.setdefault(name, {})

    def upsert(
        self,
        name: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict] | None = None,
    ) -> None:
        self._points.setdefault(name, {})
        for i, pid in enumerate(ids):
            self._points[name][pid] = (vectors[i], (payloads or [{}])[i])

    def search(
        self,
        name: str,
        vector: list[float],
        *,
        filters: dict | None = None,
        top_k: int = 5,
    ):
        from app.vectorstore.base import SearchHit

        out = []
        for pid, (_, payload) in self._points.get(name, {}).items():
            if filters and not all(payload.get(k) == v for k, v in filters.items()):
                continue
            out.append(
                SearchHit(
                    id=pid, score=1.0, text=payload.get("text", ""), metadata=payload
                )
            )
            if len(out) >= top_k:
                break
        return out

    def delete(
        self, name: str, ids: list[str] | None = None, filters: dict | None = None
    ) -> None:
        for pid in ids or []:
            self._points.get(name, {}).pop(pid, None)

    def count(self, name: str, filters: dict | None = None) -> int:
        if filters:
            return sum(
                1
                for _, p in self._points.get(name, {}).values()
                if all(p.get(k) == v for k, v in filters.items())
            )
        return len(self._points.get(name, {}))


# --------------------------------------------------------------------------- #
# Provider patching
# --------------------------------------------------------------------------- #
def _fake_embeddings_factory() -> FakeEmbeddings:
    return FakeEmbeddings()


@pytest.fixture(autouse=True)
def mock_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap AI providers with per-test singletons.

    The real vector store is persistent, so the fake store must be shared by
    every `get_vectorstore()` call within a test (not recreated per call).
    """
    import app.embeddings.factory
    import app.llm.factory
    import app.vectorstore.factory

    llm = FakeLLM()
    embeddings = FakeEmbeddings()
    store = FakeVectorstore()

    def _llm() -> FakeLLM:
        return llm

    def _embeddings() -> FakeEmbeddings:
        return embeddings

    def _store() -> FakeVectorstore:
        return store

    monkeypatch.setattr(app.llm.factory, "get_llm", _llm)
    monkeypatch.setattr(app.embeddings.factory, "get_embeddings", _embeddings)
    monkeypatch.setattr(app.vectorstore.factory, "get_vectorstore", _store)
    monkeypatch.setattr("app.services.simulation.get_llm", _llm)
    monkeypatch.setattr("app.review.service.get_llm", _llm)
    monkeypatch.setattr("app.services.hub.get_llm", _llm)

    monkeypatch.setattr("app.services.document.get_embeddings", _embeddings)
    monkeypatch.setattr("app.services.document.get_vectorstore", _store)
    monkeypatch.setattr("app.services.hub.get_embeddings", _embeddings)
    monkeypatch.setattr("app.services.hub.get_vectorstore", _store)
    monkeypatch.setattr("app.agents.tools.get_embeddings", _embeddings)
    monkeypatch.setattr("app.agents.tools.get_vectorstore", _store)
    monkeypatch.setattr("app.services.scenario.get_embeddings", _embeddings)
    monkeypatch.setattr("app.services.scenario.get_vectorstore", _store)
    monkeypatch.setattr("app.review.service.get_embeddings", _embeddings)
    monkeypatch.setattr("app.review.service.get_vectorstore", _store)
    monkeypatch.setattr("app.services.tts.is_enabled", lambda: False)
    monkeypatch.setattr("app.services.simulation._enqueue_audio", lambda sim: None)


@pytest.fixture(autouse=True, scope="session")
def _cleanup_queue():
    yield
    from app.queue import shutdown

    shutdown(wait=False, cancel_futures=True)


# --------------------------------------------------------------------------- #
# App + client
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def client_factory():
    from fastapi.testclient import TestClient

    from app.main import app

    def build():
        return TestClient(app)

    return build


@pytest.fixture
def client(client_factory):
    with client_factory() as c:
        yield c


def _register(client, email: str, org: str, password: str = "Password-123"):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "organization_name": org,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _promote(
    client,
    user_id: str,
    org_id: str,
    platform_role: str = "org_admin",
    module_roles: list[str] | None = None,
):
    """Bump a registered user's default membership directly in the DB."""
    from app.db.session import SessionLocal
    from app.models import UserRole

    db = SessionLocal()
    try:
        role = (
            db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.organization_id == org_id)
            .first()
        )
        assert role is not None
        role.platform_role = platform_role
        role.module_roles = module_roles or []
        db.commit()
    finally:
        db.close()


@pytest.fixture
def org_admin(client):
    """org_admin with lead/educator module roles; returns auth headers + org id."""
    data = _register(client, f"admin-{uuid.uuid4().hex[:10]}@test.dev", "Org A")
    _promote(
        client,
        data["user_id"],
        data["organization_id"],
        module_roles=["review.review_lead", "sim.sim_professional"],
    )
    r = client.post(
        "/api/v1/auth/login", json={"email": data["email"], "password": "Password-123"}
    )
    assert r.status_code == 200, r.text
    return {
        "headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
        "organization_id": data["organization_id"],
        "user_id": data["user_id"],
    }


@pytest.fixture
def member(client, org_admin):
    """A plain member inside the same org (denied most module permissions)."""
    data = _register(client, f"member-{uuid.uuid4().hex[:10]}@test.dev", "Org A")
    r = client.post(
        "/api/v1/auth/login", json={"email": data["email"], "password": "Password-123"}
    )
    assert r.status_code == 200
    return {
        "headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
        "organization_id": data["organization_id"],
    }


@pytest.fixture
def other_org(client):
    """org_admin in a different organization (tenant isolation checks)."""
    data = _register(client, f"other-{uuid.uuid4().hex[:10]}@test.dev", "Org B")
    _promote(client, data["user_id"], data["organization_id"])
    r = client.post(
        "/api/v1/auth/login", json={"email": data["email"], "password": "Password-123"}
    )
    assert r.status_code == 200
    return {
        "headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
        "organization_id": data["organization_id"],
    }


CONTRACT_TEXT = (
    'This Supply Agreement (the "Agreement") is made effective as of the effective date set forth on '
    "the signature page between the vendor and the company (each a party). Payment terms: the company "
    "shall remit payment within 30 days of invoice. Termination: either party may terminate this "
    "Agreement upon 30 days written notice. Indemnity: the vendor shall indemnify and hold harmless "
    "the company from claims. Confidentiality: this Agreement is confidential and non-disclosure "
    "obligations apply. Dispute resolution: any dispute shall be resolved by arbitration seated in "
    "Singapore, governed by the laws of Singapore. Penalties: late payment bears interest at 1.5% ship."
)


@pytest.fixture
def scenario_id(client, org_admin) -> str:
    r = client.post(
        "/api/v1/scenarios",
        headers=org_admin["headers"],
        json={
            "title": f"GreenLeaf vs Alta {uuid.uuid4().hex[:8]}",
            "jurisdiction": "Singapore",
            "domain": "contract",
            "fact_pattern": "A supplier delivered bad goods and the buyer withheld payment.",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def document_id(client, org_admin) -> str:
    r = client.post(
        "/api/v1/documents/upload",
        headers=org_admin["headers"],
        files={"file": ("agreement.txt", CONTRACT_TEXT.encode(), "text/plain")},
        data={
            "title": "Supply Agreement",
            "jurisdiction": "Singapore",
            "domain": "contract",
            "doc_type": "contract",
            "overwrite": "true",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def wait_for_job(client, headers, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/reviews/jobs/{job_id}", headers=headers)
        assert r.status_code == 200, r.text
        job = r.json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")
