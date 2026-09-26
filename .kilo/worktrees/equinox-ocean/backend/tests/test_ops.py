"""Ops endpoints (PRD §15.3): health + readiness self-check."""

from __future__ import annotations


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] is True


def test_readiness(client):
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["opa_self_check"] is True
    assert body["opa_mode"] == "embedded"


def test_ops_are_unauthenticated(client):
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 200
