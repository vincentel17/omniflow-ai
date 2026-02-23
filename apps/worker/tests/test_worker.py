import uuid
from types import SimpleNamespace

from omniflow_worker import main as worker_main
from omniflow_worker.main import _publish_mock, inbox_ingest_poll, ping


def test_ping_task() -> None:
    assert ping() == "pong"


def test_publish_mock_returns_stable_external_id() -> None:
    content = SimpleNamespace(id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
    result = _publish_mock(provider="linkedin", account_ref="acct", content=content)
    assert result == "mock-linkedin-acct-aaaaaaaa"


def test_inbox_ingest_poll_noop_in_mock_mode() -> None:
    assert inbox_ingest_poll(provider="meta", account_ref="acct-main") == "noop_mock_mode"


def test_presence_audit_tick_handles_empty_orgs(monkeypatch) -> None:
    class _DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalars(self, stmt):  # noqa: ANN001
            return SimpleNamespace(all=lambda: [])

        def commit(self) -> None:
            return None

    monkeypatch.setattr(worker_main, "SessionLocal", lambda: _DummySession())
    assert worker_main.presence_audit_tick() == 0


def test_reputation_sla_tick_handles_no_reviews(monkeypatch) -> None:
    class _DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalars(self, stmt):  # noqa: ANN001
            return SimpleNamespace(all=lambda: [])

        def commit(self) -> None:
            return None

    monkeypatch.setattr(worker_main, "SessionLocal", lambda: _DummySession())
    assert worker_main.reputation_sla_tick() == 0
