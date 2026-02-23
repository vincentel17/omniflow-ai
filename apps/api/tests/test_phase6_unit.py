from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models import InboxMessage, InboxMessageDirection, LinkClick, LinkTracking, Org
from app.services.analytics import (
    calculate_first_response_metrics,
    calculate_staff_reduction_index,
    click_counts_by_content,
)


def test_staff_reduction_index_calculation() -> None:
    result = calculate_staff_reduction_index(
        action_counts={
            "REPLY_SUGGESTED": 3,
            "PRESENCE_AUDIT_RUN": 1,
        },
        total_actions=10,
    )
    assert result["estimated_minutes_saved_total"] == 19
    assert result["breakdown_by_action_type"]["REPLY_SUGGESTED"] == 9
    assert result["breakdown_by_action_type"]["PRESENCE_AUDIT_RUN"] == 10
    assert result["automation_coverage_rate"] == 40.0


def test_first_response_time_calculation() -> None:
    thread_id = uuid.uuid4()
    now = datetime.now(UTC)
    messages = [
        InboxMessage(
            org_id=uuid.uuid4(),
            thread_id=thread_id,
            external_message_id="m1",
            direction=InboxMessageDirection.INBOUND,
            sender_ref="lead",
            sender_display="Lead",
            body_text="Hello",
            body_raw_json={},
            flags_json={},
            created_at=now,
        ),
        InboxMessage(
            org_id=uuid.uuid4(),
            thread_id=thread_id,
            external_message_id="m2",
            direction=InboxMessageDirection.OUTBOUND,
            sender_ref="agent",
            sender_display="Agent",
            body_text="Hi there",
            body_raw_json={},
            flags_json={},
            created_at=now + timedelta(minutes=12),
        ),
    ]

    metrics = calculate_first_response_metrics(messages, response_time_minutes=15)
    assert metrics.avg_minutes == 12.0
    assert metrics.within_sla_percent == 100.0
    assert metrics.measured_threads == 1


def test_click_counts_by_content_attribution(db_session) -> None:
    org_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    db_session.add(Org(id=org_id, name="Unit Test Org"))
    db_session.flush()

    link = LinkTracking(
        org_id=org_id,
        short_code="abc12345",
        destination_url="https://example.com",
        utm_json={"content_id": "content-42", "channel": "linkedin"},
    )
    db_session.add(link)
    db_session.flush()

    db_session.add_all(
        [
            LinkClick(org_id=org_id, tracked_link_id=link.id, short_code=link.short_code),
            LinkClick(org_id=org_id, tracked_link_id=link.id, short_code=link.short_code),
        ]
    )
    db_session.commit()

    counts = click_counts_by_content(
        db=db_session,
        org_id=org_id,
        from_dt=datetime.now(UTC) - timedelta(days=1),
        to_dt=datetime.now(UTC) + timedelta(days=1),
    )
    assert counts["content-42"] == 2
