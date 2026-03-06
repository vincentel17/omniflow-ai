from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.integration
async def test_http_exception_includes_request_id(seeded_context: dict[str, str]) -> None:
    request_id = "truth-pass-http-404"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/campaigns/00000000-0000-0000-0000-000000000000",
            headers={**seeded_context, "X-Request-Id": request_id},
        )

    assert response.status_code == 404
    assert response.headers["X-Request-Id"] == request_id
    payload = response.json()
    assert payload["request_id"] == request_id
    assert isinstance(payload["detail"], str) and payload["detail"]


@pytest.mark.integration
async def test_validation_error_includes_request_id(seeded_context: dict[str, str]) -> None:
    request_id = "truth-pass-http-422"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/campaigns/plan",
            headers={**seeded_context, "X-Request-Id": request_id},
            json={"channels": ["linkedin"], "objectives": ["Missing date"]},
        )

    assert response.status_code == 422
    assert response.headers["X-Request-Id"] == request_id
    payload = response.json()
    assert payload["detail"] == "Validation failed"
    assert payload["request_id"] == request_id
    assert payload["errors"]
