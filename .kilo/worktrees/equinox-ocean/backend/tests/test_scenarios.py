"""Scenario CRUD + versioning tests (PRD §5.1, §6.3)."""

from __future__ import annotations


def test_create_list_get_update(client, org_admin):
    h = org_admin["headers"]
    r = client.post(
        "/api/v1/scenarios",
        headers=h,
        json={
            "title": "Rental Dispute",
            "jurisdiction": "Singapore",
            "domain": "landlord_tenant",
            "tags": ["rental"],
            "fact_pattern": "Tenant withheld rent for repairs.",
            "parameters": {"parties": ["landlord", "tenant"]},
        },
    )
    assert r.status_code == 201, r.text
    sc = r.json()
    assert sc["title"] == "Rental Dispute"

    listing = client.get("/api/v1/scenarios", headers=h).json()["scenarios"]
    assert any(s["id"] == sc["id"] for s in listing)

    got = client.get(f"/api/v1/scenarios/{sc['id']}", headers=h)
    assert got.status_code == 200
    assert got.json()["current_version"]["fact_pattern"].startswith("Tenant")

    upd = client.put(
        f"/api/v1/scenarios/{sc['id']}", headers=h, json={"fact_pattern": "NEW facts."}
    )
    assert upd.status_code == 200
    assert upd.json()["current_version"]["fact_pattern"] == "NEW facts."


def test_unknown_scenario_404(client, org_admin):
    assert (
        client.get("/api/v1/scenarios/nope", headers=org_admin["headers"]).status_code
        == 404
    )


def test_delete_scenario(client, org_admin):
    h = org_admin["headers"]
    sid = client.post(
        "/api/v1/scenarios", headers=h, json={"title": "Disposable"}
    ).json()["id"]
    assert client.delete(f"/api/v1/scenarios/{sid}", headers=h).status_code == 204
    assert client.get(f"/api/v1/scenarios/{sid}", headers=h).status_code == 404


def test_create_scenario_with_file_upload(client, org_admin):
    import io

    h = dict(org_admin["headers"])
    # multipart request shouldn't force application/json
    file_bytes = (
        b"FACTUAL DISPUTE DOSSIER:\n"
        b"On 12 January 2025, Acme Corp entered into an exclusivity contract with Beta Ltd.\n"
        b"Clause 4.1 required 30 days written notice before termination.\n"
        b"On 15 March 2025, Beta Ltd terminated immediately without notice."
    )
    files = {"file": ("dispute_case_brief.txt", io.BytesIO(file_bytes), "text/plain")}
    data = {
        "title": "Acme v Beta Breach Dossier",
        "jurisdiction": "England and Wales",
        "domain": "commercial_contracts",
        "incident_date": "2025-03-15",
        "proceedings_date": "2025-06-01",
    }
    r = client.post("/api/v1/scenarios/upload", headers=h, files=files, data=data)
    assert r.status_code == 201, r.text
    sc = r.json()
    assert sc["title"] == "Acme v Beta Breach Dossier"
    params = sc.get("parameters") or sc.get("current_version", {}).get("parameters", {})
    assert "dossier" in params
    assert params["dossier"]["filename"] == "dispute_case_brief.txt"
    assert params["dossier"]["indexed"] is True
    assert "FACTUAL DISPUTE DOSSIER" in sc["fact_pattern"]
    assert sc["incident_date"] == "2025-03-15"
    assert sc["proceedings_date"] == "2025-06-01"

    # Cleanup
    del_r = client.delete(f"/api/v1/scenarios/{sc['id']}", headers=h)
    assert del_r.status_code == 204
