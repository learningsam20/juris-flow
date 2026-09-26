"""Document review pipeline tests (PRD §5.2, §6.5): job, findings, publish, report, Q&A."""

from __future__ import annotations

from conftest import CONTRACT_TEXT, wait_for_job


def test_review_pipeline(client, org_admin, document_id):
    h = org_admin["headers"]

    r = client.post("/api/v1/reviews", headers=h, json={"document_id": document_id})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    job = wait_for_job(client, h, job_id)
    assert job["status"] == "completed", job
    assert job["error"] is None
    assert job["result"]["findings"]

    review_id = job["result"]["review_id"]
    r = client.get(f"/api/v1/reviews/{review_id}", headers=h)
    assert r.status_code == 200
    review = r.json()
    assert review["status"] == "draft"
    assert review["document_id"] == document_id
    assert review["findings"], "expected substantive (deterministic) findings"
    first = review["findings"][0]
    assert first["clause_type"] and first["risk_level"] in ("high", "medium", "low")
    assert first["text"]  # verbatim excerpt
    assert any(f["span_end"] > f["span_start"] for f in review["findings"])

    listing = client.get("/api/v1/reviews", headers=h).json()["reviews"]
    assert any(rv["id"] == review_id for rv in listing)


def test_publish_and_report(client, org_admin, document_id):
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
        f"/api/v1/reviews/{review_id}/publish",
        headers=h,
        json={"risk_level": "high", "obligation_load": 4, "balance_score": 3.0},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "published"

    # re-publish must conflict
    assert (
        client.post(
            f"/api/v1/reviews/{review_id}/publish", headers=h, json={}
        ).status_code
        == 409
    )

    r = client.get(f"/api/v1/reviews/{review_id}/report", headers=h)
    assert r.status_code == 200
    assert "markdown_report" in r.json()


def test_qna_grounded(client, org_admin, document_id):
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
        f"/api/v1/reviews/{review_id}/qna",
        headers=h,
        json={"question": "What is the payment term?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "answer" in body and "citations" in body


def test_review_unknown_document(client, org_admin):
    r = client.post(
        "/api/v1/reviews", headers=org_admin["headers"], json={"document_id": "missing"}
    )
    assert r.status_code == 404


def test_review_not_found(client, org_admin):
    assert (
        client.get("/api/v1/reviews/nope", headers=org_admin["headers"]).status_code
        == 404
    )


def test_extraction_grounds_excerpts_in_source(client, org_admin, document_id):
    """Every review finding excerpt must be a verbatim substring of the source text."""
    h = org_admin["headers"]
    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]
    findings = client.get(f"/api/v1/reviews/{review_id}", headers=h).json()["findings"]
    assert findings
    for f in findings:
        assert f["text"] in CONTRACT_TEXT, (
            f"excerpt not grounded in source: {f['text']!r}"
        )


def test_reviews_intelligence(client, org_admin, document_id):
    h = org_admin["headers"]
    resp = client.get("/api/v1/reviews/intelligence", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_documents" in data
    assert "risk_distribution" in data
    assert "top_vulnerabilities" in data
    assert "watchlist" in data
    assert "coverage_percentage" in data


def test_proposed_contract_changes_and_remediation(client, org_admin, document_id):
    """Verify that review findings include contextual proposed changes and amendments."""
    h = org_admin["headers"]
    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]
    r = client.get(f"/api/v1/reviews/{review_id}", headers=h)
    assert r.status_code == 200
    review = r.json()
    findings = review["findings"]
    assert findings, "findings expected"

    # Verify proposed changes and rationale are populated on findings
    remediated = [f for f in findings if f.get("proposed_change")]
    assert len(remediated) > 0, "at least one finding should have a proposed change"
    first_rem = remediated[0]
    assert len(first_rem["proposed_change"]) > 10
    assert len(first_rem["change_rationale"]) > 5

    # Verify report contains proposed contract modifications section
    report_res = client.get(f"/api/v1/reviews/{review_id}/report", headers=h)
    assert report_res.status_code == 200
    report_md = report_res.json()["markdown_report"]
    assert "Proposed Contract Modifications & Remediation" in report_md
    assert "Proposed Contract Amendment" in report_md

    # Verify on-demand propose-change endpoint
    prop_res = client.post(
        f"/api/v1/reviews/{review_id}/findings/{first_rem['id']}/propose-change",
        headers=h,
        json={"stance": "protective"},
    )
    assert prop_res.status_code == 200
    prop_data = prop_res.json()
    assert prop_data["finding_id"] == first_rem["id"]
    assert prop_data["proposed_change"]
    assert prop_data["change_rationale"]
    assert prop_data["stance"] == "protective"


def test_risk_guidelines_endpoint(client, org_admin):
    """The high/medium/low flagging ruleset is exposed to the UI and report."""
    r = client.get("/api/v1/reviews/risk-guidelines", headers=org_admin["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    levels = {lvl["level"]: lvl for lvl in data["levels"]}
    assert set(levels) == {"high", "medium", "low"}
    assert "termination" in levels["high"]["clause_types"]
    assert "payment" in levels["medium"]["clause_types"]
    assert levels["high"]["recommended_action"]
    assert len(data["assignment_rules"]) >= 4
    assert data["disclaimer"]


def test_implementation_status_and_apply(client, org_admin, document_id):
    """Findings track implementation status and merge into the source contract."""
    h = org_admin["headers"]
    job = wait_for_job(
        client,
        h,
        client.post(
            "/api/v1/reviews", headers=h, json={"document_id": document_id}
        ).json()["job_id"],
    )
    review_id = job["result"]["review_id"]

    review = client.get(f"/api/v1/reviews/{review_id}", headers=h).json()
    findings = review["findings"]
    assert findings
    assert all("implementation_status" in f for f in findings)
    assert all("grounded" in f for f in findings)
    assert all(f["implementation_status"] == "not_started" for f in findings), (
        "findings start untracked"
    )

    target = next(f for f in findings if f.get("proposed_change"))

    # invalid status is rejected
    bad = client.patch(
        f"/api/v1/reviews/{review_id}/findings/{target['id']}/implementation-status",
        headers=h,
        json={"status": "not-a-status"},
    )
    assert bad.status_code == 422

    ok = client.patch(
        f"/api/v1/reviews/{review_id}/findings/{target['id']}/implementation-status",
        headers=h,
        json={"status": "in_progress"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["implementation_status"] == "in_progress"

    # applying merges the proposed amendments and marks them remediated
    applied = client.post(f"/api/v1/reviews/{review_id}/apply", headers=h)
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["markdown"].startswith("# Remediated Contract")
    assert "✅ REMEDIATED" in body["markdown"]
    assert "## Remediation Appendix" in body["markdown"]
    assert body["applied"] >= 1
    assert body["filename"].endswith("-remediated.md")

    after = {
        f["id"]: f
        for f in client.get(f"/api/v1/reviews/{review_id}", headers=h).json()[
            "findings"
        ]
    }
    assert after[target["id"]]["implementation_status"] == "applied"

    # dashboard contract-management metrics reflect the update
    dash = client.get("/api/v1/analytics/dashboard", headers=h)
    assert dash.status_code == 200, dash.text
    rem = dash.json()["kpis"]["contract_remediation"]
    assert rem["findings"] == len(after)
    assert rem["implementation"]["applied"] >= 1
    assert "non_grounded" in rem and "open_high_risk" in rem
    assert (
        rem["risk_distribution"]["high"]
        + rem["risk_distribution"]["medium"]
        + rem["risk_distribution"]["low"]
        == rem["findings"]
    )
