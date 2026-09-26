"""Auth flow tests (PRD §6.1): register, login, me, refresh rotation, logout."""

from __future__ import annotations

PASSWORD = "Password-123"


def test_register_login_me(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "solo@test.dev",
            "password": PASSWORD,
            "full_name": "Solo User",
            "organization_name": "Solo Org",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["user_id"] and data["organization_id"]

    r = client.post(
        "/api/v1/auth/login", json={"email": "solo@test.dev", "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert (
        tokens["access_token"]
        and tokens["refresh_token"]
        and tokens["token_type"] == "bearer"
    )
    assert tokens["user"]["email"] == "solo@test.dev"

    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "solo@test.dev"


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "pw@test.dev", "password": PASSWORD, "organization_name": "Org"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "pw@test.dev", "password": "wrong-password"},
    )
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotation_invalidates_old_token(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "rot@test.dev",
            "password": PASSWORD,
            "organization_name": "Org",
        },
    )
    first = client.post(
        "/api/v1/auth/login", json={"email": "rot@test.dev", "password": PASSWORD}
    ).json()
    old_refresh = first["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    second = r.json()
    assert second["refresh_token"] != old_refresh

    # old token must now be rejected (rotation)
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        ).status_code
        == 401
    )
    # new token works
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
        ).status_code
        == 200
    )


def test_logout_revokes_refresh(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "out@test.dev",
            "password": PASSWORD,
            "organization_name": "Org",
        },
    )
    tokens = client.post(
        "/api/v1/auth/login", json={"email": "out@test.dev", "password": PASSWORD}
    ).json()
    assert (
        client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_duplicate_registration_rejected(client):
    for _ in range(2):
        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.dev",
                "password": PASSWORD,
                "organization_name": "Org",
            },
        )
        assert r.status_code == 201 or r.status_code == 422
