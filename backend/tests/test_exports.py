"""Export endpoint tests (PRD §8.6, §15): export policy + audit path."""

from __future__ import annotations

from conftest import wait_for_job


def test_export_review_report(client, org_admin, document_id):
    h = org_admin["headers"]
    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]

    r = client.get(f"/api/v1/exports/reviews/{review_id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "review_report"
    assert body["filename"].endswith(".md")
    assert "not legal advice" in body["disclaimer"]


def test_export_case_study(client, org_admin, scenario_id):
    h = org_admin["headers"]
    r = client.post("/api/v1/simulations", headers=h, json={"scenario_id": scenario_id})
    assert r.status_code == 201, r.text
    sim = r.json()
    cs = client.get(f"/api/v1/simulations/{sim['id']}/case_study", headers=h).json()

    r = client.get(f"/api/v1/exports/case_studies/{cs['id']}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "case_study"
    assert body["case_study_id"] == cs["id"]


def test_export_requires_tenant(client, org_admin, other_org, document_id):
    h = org_admin["headers"]
    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]
    assert (
        client.get(
            f"/api/v1/exports/reviews/{review_id}", headers=other_org["headers"]
        ).status_code
        == 404
    )
