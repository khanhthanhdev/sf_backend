import pytest


def auth_header(token: str = "testtoken"):
    return {"Authorization": f"Bearer {token}"}


def test_auth_status_without_auth(api_client):
    r = api_client.get("/api/v1/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("authenticated") is False


def test_auth_status_with_auth(api_client):
    r = api_client.get("/api/v1/auth/status", headers=auth_header())
    assert r.status_code == 200
    data = r.json()
    assert data.get("authenticated") is True
    assert data.get("user_id")


def test_protected_requires_auth(api_client):
    # Without auth -> 401
    r1 = api_client.get("/api/v1/auth/test-protected")
    assert r1.status_code == 401

    # With auth -> 200
    r2 = api_client.get("/api/v1/auth/test-protected", headers=auth_header())
    assert r2.status_code == 200
    assert r2.json().get("user_id")


def test_verify_endpoint_requires_auth_and_returns_verified(api_client):
    r = api_client.post("/api/v1/auth/verify", headers=auth_header())
    assert r.status_code == 200
    body = r.json()
    assert body.get("verified") is True
    assert body.get("user_id")

