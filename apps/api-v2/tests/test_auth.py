import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_register_creates_account_and_persistent_session(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Ray Test User",
            "age": 25,
            "email": "ray@example.com",
            "password": "A-Strong-Password-2026",
            "password_confirmation": "A-Strong-Password-2026",
            "country_of_origin": "cu",
            "accept_terms": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["country_of_origin"] == "CU"
    assert response.json()["terms_status"] == "provisional"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "kubanfy_session=" in cookie
    assert "max-age=" in cookie
    assert "password_hash" not in response.json()["user"]


@pytest.mark.asyncio
async def test_registration_requires_terms_and_matching_passwords(client):
    base = {
        "full_name": "Ray Test User",
        "age": 25,
        "email": "validation@example.com",
        "password": "A-Strong-Password-2026",
        "password_confirmation": "A-Different-Password-2026",
        "country_of_origin": "US",
        "accept_terms": True,
    }
    assert (await client.post("/api/v1/auth/register", json=base)).status_code == 422
    base["password_confirmation"] = base["password"]
    base["accept_terms"] = False
    assert (await client.post("/api/v1/auth/register", json=base)).status_code == 422


@pytest.mark.asyncio
async def test_login_me_and_logout_revoke_session(client):
    payload = {
        "full_name": "Ray Test User",
        "age": 25,
        "email": "login@example.com",
        "password": "A-Strong-Password-2026",
        "password_confirmation": "A-Strong-Password-2026",
        "country_of_origin": "CU",
        "accept_terms": True,
    }
    await client.post("/api/v1/auth/register", json=payload)
    client.cookies.clear()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN@example.com", "password": "A-Strong-Password-2026", "remember_me": True},
    )
    assert login.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_invalid_credentials_are_rejected(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "not-the-password", "remember_me": False},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_country_is_refreshed_from_trusted_cloudflare_context(client):
    previous = settings.trust_cloudflare_headers
    settings.trust_cloudflare_headers = True
    try:
        response = await client.post(
            "/api/v1/auth/register",
            headers={"CF-IPCountry": "US", "CF-Connecting-IP": "203.0.113.10"},
            json={
                "full_name": "Traveling User",
                "age": 28,
                "email": "traveler@example.com",
                "password": "A-Strong-Password-2026",
                "password_confirmation": "A-Strong-Password-2026",
                "country_of_origin": "CU",
                "accept_terms": True,
            },
        )
        assert response.status_code == 201
        current = await client.get(
            "/api/v1/auth/me",
            headers={"CF-IPCountry": "CU", "CF-Connecting-IP": "198.51.100.20"},
        )
        assert current.status_code == 200
        assert current.json()["session"]["detected_country"] == "CU"
        assert current.json()["session"]["content_country"] == "CU"
    finally:
        settings.trust_cloudflare_headers = previous
