import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(api_client: AsyncClient):
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "postings" in data
