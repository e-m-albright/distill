"""API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    """Health endpoint returns ok."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
