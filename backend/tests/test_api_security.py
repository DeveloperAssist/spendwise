"""Accounts, tokens, brute force, and one user never seeing another's data."""

import datetime as dt

import jwt
from conftest import register, upload

from spendwise.config import get_settings


def test_register_login_me(client):
    h = register(client, "Asha@Example.com")
    assert client.get("/api/auth/me", headers=h).json()["email"] == "asha@example.com"  # stored lower-case
    r = client.post("/api/auth/login", data={"username": "ASHA@example.com", "password": "correct-horse-1"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


def test_duplicate_email_any_case(client):
    register(client, "asha@example.com")
    r = client.post("/api/auth/register", json={"email": "ASHA@example.com", "name": "A", "password": "x" * 8})
    assert r.status_code == 409


def test_registration_validation(client):
    for body in (
        {"email": "not-an-email", "name": "A", "password": "longenough"},
        {"email": "a@example.com", "name": "A", "password": "short"},
        {"email": "a@example.com", "name": "   ", "password": "longenough"},
    ):
        assert client.post("/api/auth/register", json=body).status_code == 422


def test_wrong_password_and_unknown_email_look_the_same(client):
    register(client)
    a = client.post("/api/auth/login", data={"username": "asha@example.com", "password": "wrong-password"})
    b = client.post("/api/auth/login", data={"username": "nobody@example.com", "password": "wrong-password"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_brute_force_is_limited(client):
    register(client)
    codes = [
        client.post("/api/auth/login", data={"username": "asha@example.com", "password": f"guess-{i}"}).status_code
        for i in range(11)
    ]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_tampered_expired_and_missing_tokens(client):
    h = register(client)
    token = h["Authorization"].split()[1]
    forged = jwt.encode(
        {"sub": "1", "exp": dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)},
        "a-guessed-secret-that-is-long-enough-to-not-warn",
        algorithm="HS256",
    )
    expired = jwt.encode(
        {"sub": "1", "exp": dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    none_alg = jwt.encode({"sub": "1"}, key=None, algorithm="none")
    for bad in (forged, expired, none_alg, token[:-3] + "abc", "garbage"):
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert client.get("/api/transactions").status_code == 401


def test_users_never_see_each_other(client):
    asha = register(client, "asha@example.com")
    ravi = register(client, "ravi@example.com", "Ravi")
    imp = upload(client, asha).json()
    tx = client.get("/api/transactions", headers=asha).json()["items"][0]

    assert client.get("/api/transactions", headers=ravi).json()["total"] == 0
    assert client.get("/api/analytics/months", headers=ravi).json() == []
    assert client.get("/api/analytics/dashboard?month=2026-09", headers=ravi).json()["summary"]["spent"] == 0
    assert client.get("/api/imports", headers=ravi).json() == []
    # someone else's ids behave exactly like ids that don't exist
    assert client.patch(f"/api/transactions/{tx['id']}", headers=ravi, json={"category": "fun"}).status_code in (
        404,
        422,
    )
    assert client.patch(f"/api/transactions/{tx['id']}", headers=ravi, json={"category": "other"}).status_code == 404
    assert client.delete(f"/api/transactions/{tx['id']}", headers=ravi).status_code == 404
    assert client.delete(f"/api/imports/{imp['id']}", headers=ravi).status_code == 404
    # and Ravi importing the same file doesn't collide with Asha's rows
    assert upload(client, ravi).json()["added"] == 227
    assert client.get("/api/transactions", headers=asha).json()["total"] == 227


def test_delete_account_removes_everything(client):
    h = register(client)
    upload(client, h)
    client.put("/api/budgets/food", headers=h, json={"limit": 3000})
    assert client.request("DELETE", "/api/auth/me", headers=h, json={"password": "wrong"}).status_code == 403
    assert client.request("DELETE", "/api/auth/me", headers=h, json={"password": "correct-horse-1"}).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
    h2 = register(client)  # the email is free again, and empty
    assert client.get("/api/transactions", headers=h2).json()["total"] == 0


def test_security_headers_and_health(client):
    r = client.get("/api/health")
    assert r.json()["status"] == "ok"
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert client.get("/api/no-such-thing").status_code == 404
