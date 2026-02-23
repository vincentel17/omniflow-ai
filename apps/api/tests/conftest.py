from __future__ import annotations
# ruff: noqa: E402

import os
import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.models import Membership, Org, Role, User

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_ORG_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
OTHER_ORG_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql+psycopg://omniflow:omniflow@localhost:5432/omniflow")


@pytest.fixture(scope="session")
def migrated_db(db_url: str) -> Generator[None, None, None]:
    config = Config("apps/api/alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
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
                "TRUNCATE TABLE publish_jobs, approvals, content_items, campaign_plans, brand_profiles, link_clicks, link_tracking, org_settings, "
                "sla_configs, nurture_tasks, lead_assignments, lead_scores, inbox_messages, inbox_threads, leads, stages, pipelines, "
                "reputation_request_campaigns, reputation_reviews, seo_work_items, presence_tasks, presence_findings, presence_audit_runs, "
                "re_listing_packages, re_cma_comparables, re_cma_reports, re_communication_logs, re_document_requests, "
                "re_checklist_items, re_checklist_templates, re_deals, "
                "onboarding_sessions, "
                "connector_dead_letters, connector_workflow_runs, connector_health, oauth_tokens, connector_accounts, "
                "audit_logs, events, vertical_packs, integrations, memberships, users, orgs "
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
