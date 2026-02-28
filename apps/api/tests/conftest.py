from __future__ import annotations
# ruff: noqa: E402

import os
import sys
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

API_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = Path(__file__).resolve().parents[2] / "worker"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from app.models import Membership, Org, Role, User

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_ORG_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OTHER_ORG_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _build_default_db_url() -> str:
    user = os.environ.get("POSTGRES_USER", "omniflow")
    password = os.environ.get("POSTGRES_PASSWORD", "omniflow")
    database = os.environ.get("POSTGRES_DB", "omniflow")
    host = os.environ.get("TEST_POSTGRES_HOST", os.environ.get("POSTGRES_HOST", "localhost"))
    port = os.environ.get(
        "TEST_POSTGRES_PORT",
        os.environ.get("POSTGRES_PORT_HOST", os.environ.get("POSTGRES_PORT", "5432")),
    )
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def _wait_for_database(db_url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        engine = create_engine(db_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2)
        finally:
            engine.dispose()
    raise RuntimeError(f"Postgres not reachable for integration tests at {db_url}") from last_error


def _reset_phase10_enums(db_url: str) -> None:
    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TYPE IF EXISTS workflow_action_run_status_enum CASCADE"))
            connection.execute(text("DROP TYPE IF EXISTS workflow_run_status_enum CASCADE"))
            connection.execute(text("DROP TYPE IF EXISTS workflow_trigger_type_enum CASCADE"))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.environ.get("DATABASE_URL", _build_default_db_url())


@pytest.fixture(scope="session")
def migrated_db(db_url: str) -> Generator[None, None, None]:
    _wait_for_database(db_url)
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    try:
        command.downgrade(config, "base")
    except Exception:  # noqa: BLE001
        pass
    _reset_phase10_enums(db_url)
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest.fixture()
def db_session(migrated_db: None, db_url: str) -> Generator[Session, None, None]:
    engine = create_engine(db_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    with factory() as session:
        # Truncate all org-scoped and global entities between integration test cases.
        session.execute(
            text(
                "TRUNCATE TABLE workflow_action_runs, workflow_runs, workflows, publish_jobs, approvals, content_items, campaign_plans, brand_profiles, link_clicks, link_tracking, org_settings, "
                "sla_configs, nurture_tasks, lead_assignments, lead_scores, inbox_messages, inbox_threads, leads, stages, pipelines, "
                "reputation_request_campaigns, reputation_reviews, seo_work_items, presence_tasks, presence_findings, presence_audit_runs, "
                "re_listing_packages, re_cma_comparables, re_cma_reports, re_communication_logs, re_document_requests, "
                "re_checklist_items, re_checklist_templates, re_deals, "
                "onboarding_sessions, "
                "connector_dead_letters, connector_workflow_runs, connector_health, oauth_tokens, connector_accounts, data_retention_policies, dsar_requests, permission_audit_reports, usage_metrics, org_subscriptions, subscription_plans, global_admins, predictive_lead_scores, posting_optimizations, ad_budget_recommendations, model_metadata, org_optimization_settings, "
                "audit_logs, events, vertical_packs, vertical_pack_registry, integrations, memberships, users, orgs "
                "RESTART IDENTITY CASCADE"
            )
        )
        session.commit()
    with factory() as session:
        yield session
        session.rollback()
    engine.dispose()


@pytest.fixture()
def seeded_context(db_session: Session) -> dict[str, str]:
    user = User(id=TEST_USER_ID, email="integration@omniflow.local")
    org = Org(id=TEST_ORG_ID, name="Integration Org")
    other_org = Org(id=OTHER_ORG_ID, name="Other Integration Org")
    db_session.add_all([user, org, other_org])
    db_session.flush()
    db_session.add_all(
        [
            Membership(org_id=TEST_ORG_ID, user_id=TEST_USER_ID, role=Role.OWNER),
            Membership(org_id=OTHER_ORG_ID, user_id=TEST_USER_ID, role=Role.OWNER),
        ]
    )
    db_session.commit()
    return {
        "X-Omniflow-User-Id": str(TEST_USER_ID),
        "X-Omniflow-Org-Id": str(TEST_ORG_ID),
        "X-Omniflow-Role": Role.OWNER.value,
    }




