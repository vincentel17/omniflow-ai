from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..models import Event


def write_event(
    db: Session,
    org_id: uuid.UUID,
    source: str,
    channel: str,
    event_type: str,
    payload_json: dict[str, Any] | None = None,
    campaign_id: str | None = None,
    content_id: str | None = None,
    lead_id: str | None = None,
    actor_id: str | None = None,
) -> Event:
    event = Event(
        org_id=org_id,
        source=source,
        channel=channel,
        type=event_type,
        payload_json=payload_json or {},
        campaign_id=campaign_id,
        content_id=content_id,
        lead_id=lead_id,
        actor_id=actor_id,
    )
    db.add(event)
    db.flush()
    return event
