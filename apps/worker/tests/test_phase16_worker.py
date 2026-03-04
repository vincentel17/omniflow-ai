import uuid

from omniflow_worker.main import _agent_step_idempotency_key, _should_run_agent_schedule


def test_phase16_agent_idempotency_key_is_stable() -> None:
    org_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    run_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    key_a = _agent_step_idempotency_key(org_id, run_id, "step-1", "lead:123")
    key_b = _agent_step_idempotency_key(org_id, run_id, "step-1", "lead:123")
    key_c = _agent_step_idempotency_key(org_id, run_id, "step-2", "lead:123")

    assert key_a == key_b
    assert key_a != key_c
    assert key_a.startswith("agent-step-")


def test_phase16_agent_schedule_window_check() -> None:
    assert _should_run_agent_schedule(schedule_enabled=True, now_hour=8, scheduled_hour=8) is True
    assert _should_run_agent_schedule(schedule_enabled=False, now_hour=8, scheduled_hour=8) is False
    assert _should_run_agent_schedule(schedule_enabled=True, now_hour=9, scheduled_hour=8) is False

