"""Review templates + collaborative annotations (plan Phase 6 P2)."""

from __future__ import annotations

import uuid

from conftest import _promote, _register, wait_for_job


def test_review_template_crud(client, org_admin, document_id):
    h = org_admin["headers"]

    r = client.post(
        "/api/v1/reviews/templates",
        headers=h,
        json={
            "name": "Payment & Termination",
            "description": "Focus extraction on payment and termination clauses.",
            "document_types": ["contract"],
            "focus_clause_types": ["payment", "termination"],
            "is_default": False,
        },
    )
    assert r.status_code == 201, r.text
    template_id = r.json()["id"]

    listed = client.get("/api/v1/reviews/templates", headers=h).json()["templates"]
    assert any(
        t["id"] == template_id and t["name"] == "Payment & Termination" for t in listed
    )

    r = client.delete(f"/api/v1/reviews/templates/{template_id}", headers=h)
    assert r.status_code == 200, r.text
    listed = client.get("/api/v1/reviews/templates", headers=h).json()["templates"]
    assert not any(t["id"] == template_id for t in listed)


def test_review_with_template_filters_findings(client, org_admin, document_id):
    h = org_admin["headers"]

    r = client.post(
        "/api/v1/reviews/templates",
        headers=h,
        json={
            "name": "Termination only",
            "focus_clause_types": ["termination"],
            "document_types": ["contract"],
        },
    )
    template_id = r.json()["id"]

    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews",
            headers=h,
            json={"document_id": document_id, "template_id": template_id},
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]

    review = client.get(f"/api/v1/reviews/{review_id}", headers=h).json()
    assert review["template_id"] == template_id
    assert review["template_name"] == "Termination only"
    assert review["findings"]
    assert all(f["clause_type"] == "termination" for f in review["findings"])


def test_annotations_lifecycle(client, org_admin, member, document_id):
    h = org_admin["headers"]

    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]

    r = client.post(
        f"/api/v1/reviews/{review_id}/annotations",
        headers=h,
        json={"body": "Second opinion needed on the termination clause."},
    )
    assert r.status_code == 201, r.text
    annotation_id = r.json()["id"]
    assert r.json()["resolution"] == "open"

    listed = client.get(f"/api/v1/reviews/{review_id}/annotations", headers=h).json()[
        "annotations"
    ]
    assert any(a["id"] == annotation_id for a in listed)

    r = client.patch(
        f"/api/v1/reviews/annotations/{annotation_id}",
        headers=h,
        json={"resolution": "resolved"},
    )
    assert r.status_code == 200
    assert r.json()["resolution"] == "resolved"

    r = client.delete(f"/api/v1/reviews/annotations/{annotation_id}", headers=h)
    assert r.status_code == 200

    # plain member in the same org lacks the report.view permission
    h2 = member["headers"]
    assert (
        client.get(f"/api/v1/reviews/{review_id}/annotations", headers=h2).status_code
        == 403
    )


def test_annotation_tenant_isolation(client, org_admin, document_id):
    h = org_admin["headers"]
    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]

    other = _register(client, f"xten-{uuid.uuid4().hex[:10]}@test.dev", "Org B")
    _promote(
        client,
        other["user_id"],
        other["organization_id"],
        module_roles=["review.review_lead"],
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": other["email"], "password": "Password-123"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (
        client.post(
            f"/api/v1/reviews/{review_id}/annotations",
            headers=other_headers,
            json={"body": "cross-tenant"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/reviews/{review_id}/annotations", headers=other_headers
        ).status_code
        == 404
    )
