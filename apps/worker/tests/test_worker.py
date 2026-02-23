import uuid
from types import SimpleNamespace

from omniflow_worker.main import _publish_mock, ping


def test_ping_task() -> None:
    assert ping() == "pong"


def test_publish_mock_returns_stable_external_id() -> None:
    content = SimpleNamespace(id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    result = _publish_mock(provider="linkedin", account_ref="acct", content=content)
    assert result == "mock-linkedin-acct-aaaaaaaa"
