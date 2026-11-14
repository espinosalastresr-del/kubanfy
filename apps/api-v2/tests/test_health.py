import pytest


@pytest.mark.asyncio
async def test_liveness_endpoint(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_checks_database(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
