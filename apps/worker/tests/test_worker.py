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


def test_scheduler_tick_skips_when_auto_posting_disabled(monkeypatch) -> None:
    job = SimpleNamespace(id=uuid.uuid4(), org_id=uuid.uuid4())

    class _DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def scalars(self, stmt):  # noqa: ANN001
            return SimpleNamespace(all=lambda: [job])

    class _DelayCounter:
        def __init__(self) -> None:
            self.calls = 0

        def delay(self, _value: str) -> None:
            self.calls += 1

    delay_counter = _DelayCounter()
    monkeypatch.setattr(worker_main, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(worker_main, "_org_feature_enabled", lambda db, org_id, key, fallback: False)
    monkeypatch.setattr(worker_main.publish_job_execute, "delay", delay_counter.delay)

    assert worker_main.scheduler_tick() == 0
    assert delay_counter.calls == 0


def test_connector_breaker_allows_half_open_after_cooldown() -> None:
    now = worker_main._now()
    account = SimpleNamespace(status="circuit_open")
    health = SimpleNamespace(consecutive_failures=3, last_error_at=now - worker_main.timedelta(seconds=601))

    class _DummySession:
        def __init__(self) -> None:
            self.calls = 0

        def scalar(self, stmt):  # noqa: ANN001
            self.calls += 1
            return account if self.calls == 1 else health

    db = _DummySession()
    is_open = worker_main._connector_breaker_open(
        db=db,
        org_id=uuid.uuid4(),
        provider="meta",
        account_ref="acct-1",
    )

    assert is_open is False
    assert account.status == "linked"
    assert health.consecutive_failures == 0