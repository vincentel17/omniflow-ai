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
    monkeypatch.setattr(worker_main, "_org_is_active", lambda db, org_id: True)
    monkeypatch.setattr(worker_main.publish_job_execute, "delay", delay_counter.delay)

    assert worker_main.scheduler_tick() == 0
    assert delay_counter.calls == 0


def test_publish_job_execute_marks_job_succeeded(monkeypatch) -> None:
    org_id = uuid.uuid4()
    content_id = uuid.uuid4()
    job_id = uuid.uuid4()
    content = SimpleNamespace(
        id=content_id,
        org_id=org_id,
        channel="linkedin",
        risk_tier=1,
        text_rendered="Truth pass publish",
        media_refs_json=[],
        link_url="https://example.test/post",
        tags_json=["truth-pass"],
        status=worker_main.ContentItemStatus.APPROVED,
    )
    job = SimpleNamespace(
        id=job_id,
        org_id=org_id,
        content_item_id=content_id,
        provider="linkedin",
        account_ref="acct-demo",
        status=worker_main.PublishJobStatus.QUEUED,
        attempts=0,
        external_id=None,
        published_at=None,
        last_error=None,
    )

    class _DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __init__(self) -> None:
            self.calls = 0
            self.commits = 0

        def scalar(self, stmt):  # noqa: ANN001
            self.calls += 1
            return job if self.calls == 1 else content

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            self.commits += 1

    class _Publisher:
        def publish_post(self, payload):  # noqa: ANN001
            return {"external_id": "live-linkedin-123"}

    db = _DummySession()
    monkeypatch.setattr(worker_main, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker_main, "_org_is_active", lambda db, org_id: True)
    monkeypatch.setattr(worker_main, "_org_feature_enabled", lambda db, org_id, key, fallback: True)
    monkeypatch.setattr(worker_main, "_provider_publish_enabled", lambda db, org_id, provider: True)
    monkeypatch.setattr(worker_main, "_connector_breaker_open", lambda db, org_id, provider, account_ref: False)
    monkeypatch.setattr(worker_main, "_write_system_event", lambda **kwargs: None)
    monkeypatch.setattr(worker_main, "_write_system_audit", lambda **kwargs: None)
    monkeypatch.setattr(worker_main, "get_publisher", lambda provider, org_id, account_ref, db: _Publisher())

    result = worker_main.publish_job_execute.run(str(job_id))

    assert result == "succeeded"
    assert job.status == worker_main.PublishJobStatus.SUCCEEDED
    assert content.status == worker_main.ContentItemStatus.PUBLISHED
    assert job.external_id == "live-linkedin-123"
    assert job.attempts == 1
    assert db.commits == 1


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
