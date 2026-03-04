from __future__ import annotations

import sys
import uuid
from pathlib import Path

from sqlalchemy import func, select

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AgentRun,
    Approval,
    ContentItem,
    Event,
    InboxMessage,
    InboxThread,
    InboxThreadStatus,
    Lead,
    Org,
    OrgSettings,
    PresenceAuditRun,
    PublishJob,
    ReputationReview,
    SEOWorkItem,
    Workflow,
    WorkflowActionRun,
    WorkflowRun,
)


SEED_VERSION = "qa-standard-v1"
NS = uuid.UUID("7f2f16c1-8664-48ee-a5ef-7dd2d5ac7b26")


def _uid(*parts: object) -> uuid.UUID:
    return uuid.uuid5(NS, ":".join(str(p) for p in parts))


def _count(db, model, **filters) -> int:
    return int(db.scalar(select(func.count(model.id)).filter_by(**filters)) or 0)


def _count_where(db, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def main() -> None:
    failures: list[str] = []
    primary_keys = ["alpha", "beta"]
    expected = {
        "leads": 50,
        "threads": 25,
        "messages": 60,
        "content": 12,
        "publish_jobs": 8,
        "presence_runs": 3,
        "seo_items": 10,
        "reviews": 20,
        "workflows": 5,
        "workflow_runs": 10,
        "workflow_actions": 8,
        "agent_runs": 6,
        "approvals": 8,
    }

    with SessionLocal() as db:
        for key in ("alpha", "beta", "gamma"):
            org_id = _uid("org", key)
            org = db.scalar(select(Org).where(Org.id == org_id))
            if org is None:
                failures.append(f"missing org {key}")
                continue
            settings = db.scalar(select(OrgSettings).where(OrgSettings.org_id == org_id))
            if settings is None or not isinstance(settings.settings_json, dict):
                failures.append(f"missing org_settings for {key}")
            else:
                if settings.settings_json.get("qa_seed_version") != SEED_VERSION:
                    failures.append(f"seed version mismatch for {key}")

        for key in primary_keys:
            org_id = _uid("org", key)

            checks = {
                "leads": _count(db, Lead, org_id=org_id),
                "threads": _count(db, InboxThread, org_id=org_id),
                "messages": _count(db, InboxMessage, org_id=org_id),
                "content": _count(db, ContentItem, org_id=org_id),
                "publish_jobs": _count(db, PublishJob, org_id=org_id),
                "presence_runs": _count(db, PresenceAuditRun, org_id=org_id),
                "seo_items": _count(db, SEOWorkItem, org_id=org_id),
                "reviews": _count(db, ReputationReview, org_id=org_id),
                "workflows": _count(db, Workflow, org_id=org_id),
                "workflow_runs": _count(db, WorkflowRun, org_id=org_id),
                "workflow_actions": _count(db, WorkflowActionRun, org_id=org_id),
                "agent_runs": _count(db, AgentRun, org_id=org_id),
                "approvals": _count(db, Approval, org_id=org_id),
            }
            for name, value in checks.items():
                if value != expected[name]:
                    failures.append(f"{key}: expected {name}={expected[name]}, got {value}")

            open_threads = _count_where(
                db,
                select(func.count(InboxThread.id)).where(
                    InboxThread.org_id == org_id,
                    InboxThread.status == InboxThreadStatus.OPEN,
                ),
            )
            if open_threads != 15:
                failures.append(f"{key}: expected open threads=15, got {open_threads}")

            closed_threads = _count_where(
                db,
                select(func.count(InboxThread.id)).where(
                    InboxThread.org_id == org_id,
                    InboxThread.status == InboxThreadStatus.CLOSED,
                ),
            )
            if closed_threads != 10:
                failures.append(f"{key}: expected closed threads=10, got {closed_threads}")

            expected_unresponded_neg = 4 if key == "alpha" else 2
            unresponded_neg = _count_where(
                db,
                select(func.count(ReputationReview.id)).where(
                    ReputationReview.org_id == org_id,
                    ReputationReview.rating <= 2,
                    ReputationReview.responded_at.is_(None),
                ),
            )
            if unresponded_neg != expected_unresponded_neg:
                failures.append(
                    f"{key}: expected unresponded negative reviews={expected_unresponded_neg}, got {unresponded_neg}"
                )

        alpha_sla = _count_where(
            db,
            select(func.count(Event.id)).where(
                Event.org_id == _uid("org", "alpha"),
                Event.type == "SLA_BREACH",
            ),
        )
        if alpha_sla != 3:
            failures.append(f"alpha: expected SLA_BREACH events=3, got {alpha_sla}")

    if failures:
        print("QA standard smoke FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("QA standard smoke PASSED")
    print("- orgs present: alpha, beta, gamma")
    print("- primary org envelopes match expected deterministic counts")
    print("- critical signal checks passed (SLA breaches, inbox statuses, unresponded negatives)")


if __name__ == "__main__":
    main()
