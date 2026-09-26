"""Simulation lifecycle tests (PRD §4.2, §6.4, §8.1): run to completion, case study,
HITL clarification + resume, cancel, life-cycle guards."""

from __future__ import annotations


def _start(client, h, scenario_id, active_agents=None):
    body = {"scenario_id": scenario_id}
    if active_agents:
        body["active_agents"] = active_agents
    r = client.post("/api/v1/simulations", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_simulation_runs_to_completion(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)
    assert sim["status"] == "completed", sim
    assert sim["turn_limit"] == 8
    assert sim["current_turn"] >= 1
    assert sim["case_study"]["status"] in ("draft", "approved")

    # turns are persisted and ordered
    turns = sim["turns"]
    assert len(turns) == sim["current_turn"]
    assert turns[0]["agent_role"] in ("plaintiff", "defendant")
    roles = {t["agent_role"] for t in turns}
    assert {"plaintiff", "defendant", "judge"} <= roles

    # listing + fetch round-trip
    listing = client.get("/api/v1/simulations", headers=h).json()["simulations"]
    assert any(s["id"] == sim["id"] for s in listing)
    got = client.get(f"/api/v1/simulations/{sim['id']}", headers=h)
    assert got.status_code == 200
    assert got.json()["status"] == "completed"


def test_case_study_export(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)

    r = client.get(f"/api/v1/simulations/{sim['id']}/case_study", headers=h)
    assert r.status_code == 200, r.text
    cs = r.json()
    assert cs["markdown"]
    assert "educational" in cs["disclaimer"].lower() if "disclaimer" in cs else True

    r = client.post(f"/api/v1/simulations/{sim['id']}/export", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "case_study"
    assert body["markdown"]


def test_hitl_clarification_then_resume(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)

    r = client.post(
        f"/api/v1/simulations/{sim['id']}/clarify",
        headers=h,
        json={"content": "Was late delivery an admitted fact?"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "human_input"

    # resume drives the simulation again to completion
    r = client.post(f"/api/v1/simulations/{sim['id']}/resume", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    resumed = client.get(f"/api/v1/simulations/{sim['id']}", headers=h).json()
    assert resumed["status"] == "completed"


def test_inject_fact_and_steer(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)

    r = client.post(
        f"/api/v1/simulations/{sim['id']}/steer",
        headers=h,
        json={"focus": "liquidated damages"},
    )
    assert r.status_code == 200, r.text
    assert "liquidated damages" in r.json()["focus_areas"]

    # injecting into a completed sim is rejected
    r = client.post(
        f"/api/v1/simulations/{sim['id']}/inject_fact",
        headers=h,
        json={"fact": "New evidence"},
    )
    assert r.status_code == 400, r.text


def test_cancel(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)
    r = client.post(f"/api/v1/simulations/{sim['id']}/cancel", headers=h)
    assert r.status_code == 200
    assert (
        client.get(f"/api/v1/simulations/{sim['id']}", headers=h).json()["status"]
        == "cancelled"
    )


def test_finished_sim_rejects_lifecycle_ops(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)
    for action in ("pause", "advance", "resume", "inject_fact"):
        r = client.post(
            f"/api/v1/simulations/{sim['id']}/{action}",
            headers=h,
            json={"content": "x"}
            if action in ("advance",)
            else {"fact": "x"}
            if action == "inject_fact"
            else {},
        )
        assert r.status_code == 400, (action, r.text)


def test_judge_delivers_winner_verdict(client, org_admin, scenario_id):
    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)
    assert sim["status"] == "completed", sim
    verdict = sim.get("verdict")
    assert verdict is not None, sim
    assert verdict["winner"] in ("plaintiff", "defendant", "draw", "undecided")
    # the final recorded turn is the judge's winner ruling
    assert sim["turns"], sim
    assert sim["turns"][-1]["agent_role"] == "judge"
    assert sim["turns"][-1]["payload"].get("winner") == verdict["winner"]


def test_per_run_judge_overrides(client, org_admin, scenario_id):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/simulations",
        headers=h,
        json={
            "scenario_id": scenario_id,
            "judge_effort": "medium",
            "judge_max_rounds": 2,
        },
    )
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["status"] == "completed", sim
    # per-run config is persisted and returned
    assert sim["judge_config"].get("judge_effort") == "medium"
    assert sim["judge_config"].get("judge_max_rounds") == 2
    # 2 exchanges x (plaintiff + defendant + judge) = 6 turns then the verdict
    assert sim["current_turn"] == 6, sim["current_turn"]
    assert sim["turns"][-1]["agent_role"] == "judge"
    assert sim["verdict"] is not None


def test_agent_telemetry_records_call_durations(client, org_admin, scenario_id):
    """Agent telemetry events must carry the duration of LLM, tool (RAG), and turn."""
    from app.db.session import SessionLocal
    from app.models import AnalyticsEvent

    h = org_admin["headers"]
    sim = _start(client, h, scenario_id)
    assert sim["status"] == "completed", sim

    db = SessionLocal()
    try:
        events = (
            db.query(AnalyticsEvent)
            .filter(
                AnalyticsEvent.organization_id == org_admin["organization_id"],
                AnalyticsEvent.module == "sim",
                AnalyticsEvent.simulation_id == sim["id"],
            )
            .all()
        )
    finally:
        db.close()

    by_type: dict[str, list[dict]] = {}
    for ev in events:
        by_type.setdefault(ev.event_type, []).append(ev.payload or {})

    turns = by_type.get("agent.turn", [])
    assert turns, "agent.turn events must be recorded"
    for t in turns:
        assert "duration_ms" in t
        assert "llm_ms" in t
        assert "retrieval_ms" in t
        assert float(t["duration_ms"]) >= 0

    llm_calls = by_type.get("agent.llm_call", [])
    assert llm_calls, "agent.llm_call events must be recorded"
    for c in llm_calls:
        assert "duration_ms" in c
        assert float(c["duration_ms"]) >= 0
        assert "attempts" in c

    tool_calls = by_type.get("agent.tool_call", [])
    assert tool_calls, "agent.tool_call events must be recorded"
    assert all("duration_ms" in c for c in tool_calls)
    assert {c.get("tool") for c in tool_calls} == {"knowledge.retriever"}

    retrievals = by_type.get("agent.retrieval", [])
    assert retrievals, "agent.retrieval events must be recorded"
    assert all("duration_ms" in r for r in retrievals)
    assert all("hits" in r for r in retrievals)


def test_missing_scenario_rejected(client, org_admin):
    r = client.post(
        "/api/v1/simulations",
        headers=org_admin["headers"],
        json={"scenario_id": "nope"},
    )
    assert r.status_code == 400


def test_simulation_with_scenario_dossier_dual_rag(client, org_admin):
    import io

    h = dict(org_admin["headers"])
    # 1. Create scenario with uploaded dispute dossier
    dossier_text = (
        "CONFIDENTIAL ARBITRATION BRIEF:\n"
        "Claimant Delta claims 500,000 SGD liquidated damages.\n"
        "Respondent claims force majeure under clause 19 due to shipping embargo."
    )
    files = {
        "file": (
            "arbitration_brief.txt",
            io.BytesIO(dossier_text.encode("utf-8")),
            "text/plain",
        )
    }
    data = {
        "title": "Delta v Echo Arbitration",
        "jurisdiction": "Singapore",
        "domain": "commercial_disputes",
    }
    sc_r = client.post("/api/v1/scenarios/upload", headers=h, files=files, data=data)
    assert sc_r.status_code == 201, sc_r.text
    sc = sc_r.json()

    # 2. Run simulation on this scenario
    sim_r = client.post(
        "/api/v1/simulations",
        headers=h,
        json={"scenario_id": sc["id"], "max_turns": 3},
    )
    assert sim_r.status_code == 201, sim_r.text
    sim = sim_r.json()
    assert len(sim["turns"]) > 0

    first_turn = sim["turns"][0]
    payload = first_turn.get("payload", {})
    # Check that dual RAG captured scenario citations from the isolated SIM_COLLECTION index
    assert "scenario_citations" in payload
    assert "knowledge_citations" in payload
    assert "is_grounded" in payload

    # Clean up
    client.delete(f"/api/v1/scenarios/{sc['id']}", headers=h)
