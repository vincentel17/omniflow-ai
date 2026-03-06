# Worker Pipeline Report

## Worker Task Inventory

| Task name | Function | Retries | Backoff |
|---|---|---:|---|
| `worker.health.ping` | `def ping() -> str:` | default | false |
| `worker.optimization.lead_model_train_tick` | `def lead_model_train_tick() -> int:` | default | false |
| `worker.publish.execute` | `def publish_job_execute(self: Celery, publish_job_id: str) -> str:` | 3 | true |
| `worker.publish.scheduler_tick` | `def scheduler_tick() -> int:` | default | false |
| `worker.demo.simulator_tick` | `def demo_simulator_tick() -> int:` | default | false |
| `worker.inbox.ingest_poll` | `def inbox_ingest_poll(provider: str = "meta", account_ref: str = "acct-main") -> str:` | default | false |
| `worker.sla.monitor_tick` | `def sla_monitor_tick() -> int:` | default | false |
| `worker.presence.audit_tick` | `def presence_audit_tick() -> int:` | default | false |
| `worker.reputation.sla_tick` | `def reputation_sla_tick() -> int:` | default | false |
| `worker.workflow.evaluate` | `def workflow_evaluate(event_id: str) -> str:` | default | false |
| `worker.workflow.action.execute` | `def workflow_action_execute(self: Celery, action_run_id: str) -> str:` | 3 | true |
| `worker.workflow.approval.apply` | `def workflow_approval_apply(approval_id: str) -> str:` | default | false |
| `worker.agents.run_create` | `def agent_run_create(event_id: str | None = None, trigger: str = "event", org_id: str | None = None) -> str:` | default | false |
| `worker.agents.execute` | `def agent_execute(agent_run_id: str) -> str:` | default | false |
| `worker.agents.schedule_tick` | `def agent_schedule_tick() -> int:` | default | false |
| `worker.agents.metrics_tick` | `def agent_metrics_tick() -> int:` | default | false |
| `worker.billing.status_sync_tick` | `def billing_status_sync_tick() -> int:` | default | false |
| `worker.usage.aggregator_tick` | `def usage_aggregator_tick() -> int:` | default | false |
| `worker.retention.enforcer_tick` | `def retention_enforcer_tick() -> int:` | default | false |

## Status Transition Expectations

- Publish jobs: `queued -> running -> succeeded/failed/canceled`
- Workflow runs/actions: `queued/running -> succeeded/failed/blocked/approval_pending`
- Agent runs: `planned/proposed/approved/executing/succeeded/failed/blocked`

## Idempotency Evidence

- `publish_jobs` has org-scoped idempotency key enforcement.
- `workflow_action_runs` has org-scoped unique idempotency enforcement.
- `connector_workflow_runs` has org-scoped unique idempotency enforcement.
- Agent execution derives stable keys from org/run/step/target references before invoking workflow actions.

## Failure Capture / DLQ

- Connector dead-letter storage exists in `connector_dead_letters`.
- Workflow and agent failures persist sanitized `error_json` on run/action tables.
- Replayability today is operationally available through requeue/re-execute endpoints rather than a separate DLQ UI for every task family.

## Verification Evidence

- Existing worker unit coverage: `apps/worker/tests/test_worker.py`.
- Existing publish scheduling integration coverage: `apps/api/tests/test_phase3_integration.py`.
- Truth-pass final verification should include at least one publish job lifecycle run in mock mode under the pinned Node runtime.

## Readiness Checks

- `/ready` is expected to reflect DB + Redis readiness and must be checked against healthy local dependencies during final verification.
