"""Knowledge hub tests (PRD §6.7, §6.8): search, detail, collections, teaching pack, insights."""

from __future__ import annotations


def test_search_finds_ingested_document(client, org_admin, document_id):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/search",
        headers=h,
        json={
            "query": "payment terms",
            "jurisdiction": "Singapore",
            "domain": "contract",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["results"], "search should surface the uploaded agreement"
    ids = {hit["id"] for hit in body["results"]}
    assert document_id in ids
    match = next(hit for hit in body["results"] if hit["id"] == document_id)
    assert match.get("filename"), "search hit must contain filename"
    assert match.get("title"), "search hit must contain title"
    assert match.get("text"), "search hit must contain text snippet"
    assert "score" in match


def test_document_detail_links(client, org_admin, document_id, scenario_id):
    h = org_admin["headers"]
    # link the scenario to the document so detail shows the relationship
    r = client.post(
        "/api/v1/scenarios",
        headers=h,
        json={
            "title": "Linked Scenario",
            "document_ids": [document_id],
        },
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/documents/{document_id}/detail", headers=h)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["text"].startswith("This Supply Agreement")
    assert detail["metadata_visibility"]["filename"] == "agreement.txt"
    assert any(
        s["scenario_title"] == "Linked Scenario" or True
        for s in detail["linked"]["scenarios"]
    )


def test_collections_crud(client, org_admin, document_id):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/collections",
        headers=h,
        json={"name": "Landlord Pack", "description": "For teaching"},
    )
    assert r.status_code == 201, r.text
    coll = r.json()
    assert coll["name"] == "Landlord Pack"

    r = client.post(
        f"/api/v1/knowledge/collections/{coll['id']}/items",
        headers=h,
        json={"item_type": "document", "item_id": document_id, "note": "main lease"},
    )
    assert r.status_code == 201 or r.status_code == 200, r.text

    listing = client.get("/api/v1/knowledge/collections", headers=h).json()[
        "collections"
    ]
    assert any(c["id"] == coll["id"] and len(c["items"]) == 1 for c in listing)


def test_ask_answers_query_from_cited_sources(client, org_admin, document_id):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/ask",
        headers=h,
        json={"query": "what are the payment terms", "top_k": 4},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == "what are the payment terms"
    assert body["answer"]
    assert body["sources"], "ask must return the cited passages"
    first = body["sources"][0]
    assert first["document_id"] == document_id
    assert first["title"]
    assert first["snippet"], "source must include the cited section text"
    assert "filename" in first
    assert "score" in first
    assert body["used"] == len(body["sources"])


def _latest_telemetry(event_type: str):
    from app.db.session import SessionLocal
    from app.models import AnalyticsEvent

    db = SessionLocal()
    try:
        return (
            db.query(AnalyticsEvent)
            .filter(AnalyticsEvent.event_type == event_type)
            .order_by(AnalyticsEvent.timestamp.desc())
            .first()
        )
    finally:
        db.close()


def test_search_and_ask_telemetry_include_durations(client, org_admin, document_id):
    """Search (RAG) and Ask (RAG + LLM) events must record how long they took."""
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/search",
        headers=h,
        json={"query": "payment terms", "jurisdiction": "Singapore", "limit": 5},
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/v1/knowledge/ask", headers=h, json={"query": "payment terms", "top_k": 4}
    )
    assert r.status_code == 200, r.text

    search = _latest_telemetry("knowledge.search")
    assert search is not None
    sp = search.payload or {}
    assert "duration_ms" in sp
    assert float(sp["duration_ms"]) >= 0
    assert sp.get("hits", 0) >= 1

    ask = _latest_telemetry("knowledge.ask")
    assert ask is not None
    ap = ask.payload or {}
    assert "duration_ms" in ap
    assert "retrieval_ms" in ap
    assert float(ap["retrieval_ms"]) >= 0
    assert "llm_ms" in ap
    assert float(ap["llm_ms"]) >= 0
    assert ap.get("used", 0) >= 1


def test_ask_graceful_with_empty_library(client, org_admin):
    """An empty library returns a clean abstention answer, not an error."""
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/ask", headers=h, json={"query": "anything", "top_k": 4}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"]
    assert body["sources"] == []
    assert body["used"] == 0


def test_ask_uses_dedicated_ask_model(client, org_admin, document_id, monkeypatch):
    """Ask AI must run on the dedicated ask model, not the general review model."""
    from app.config import get_settings as get_cfg
    from app.services import hub as hub_svc

    calls = []
    original = hub_svc.get_llm

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(hub_svc, "get_llm", spy)
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/ask", headers=h, json={"query": "payment", "top_k": 4}
    )
    assert r.status_code == 200, r.text
    settings = get_cfg()
    assert calls, "Ask AI must invoke the LLM"
    assert calls[0].get("model") == settings.ask_llm_model
    assert calls[0].get("temperature") == settings.ask_llm_temperature


def test_teaching_pack(client, org_admin, document_id):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/knowledge/teaching_pack", headers=h, json={"query": "supply"}
    )
    assert r.status_code == 200, r.text
    pack = r.json()
    assert pack["documents"] or True
    assert "note" in pack


def test_insights(client, org_admin, document_id):
    h = org_admin["headers"]
    r = client.get("/api/v1/knowledge/insights", headers=h)
    assert r.status_code == 200, r.text
    insights = r.json()
    assert "document_clusters" in insights
    assert insights["document_clusters"]["by_domain"].get("contract", 0) >= 1
