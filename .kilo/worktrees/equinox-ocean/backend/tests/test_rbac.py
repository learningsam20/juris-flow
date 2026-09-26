"""OPA-backed RBAC + tenant isolation tests (PRD §15.4)."""

from __future__ import annotations


def test_member_denied_module_permission(client, member):
    r = client.get("/api/v1/scenarios", headers=member["headers"])
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert "sim.scenario.view" in detail


def test_org_admin_allowed(client, org_admin):
    assert (
        client.get("/api/v1/scenarios", headers=org_admin["headers"]).status_code == 200
    )


def test_member_cannot_run_simulation(client, member, scenario_id):
    r = client.post(
        "/api/v1/simulations",
        headers=member["headers"],
        json={"scenario_id": scenario_id},
    )
    assert r.status_code == 403


def test_member_cannot_upload(client, member):
    r = client.post(
        "/api/v1/documents/upload",
        headers=member["headers"],
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 403


def test_unauthenticated_denied(client):
    assert client.get("/api/v1/scenarios").status_code == 401


def test_tenant_isolation_scenario(client, org_admin, other_org, scenario_id):
    # other org cannot read or mutate this org's scenario
    assert (
        client.get(
            f"/api/v1/scenarios/{scenario_id}", headers=other_org["headers"]
        ).status_code
        == 404
    )
    r = client.put(
        f"/api/v1/scenarios/{scenario_id}",
        headers=other_org["headers"],
        json={"title": "intruder edit"},
    )
    assert r.status_code == 404


def test_tenant_isolation_document(client, org_admin, other_org, document_id):
    assert (
        client.get(
            f"/api/v1/documents/{document_id}", headers=other_org["headers"]
        ).status_code
        == 404
    )
