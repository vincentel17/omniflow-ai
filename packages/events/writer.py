from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EventPayload:
    source: str
    channel: str
    event_type: str
    campaign_id: str | None = None
    content_id: str | None = None
    lead_id: str | None = None
    actor_id: str | None = None
    payload_json: dict[str, Any] = field(default_factory=dict)


def build_event_payload(data: EventPayload) -> dict[str, Any]:
    return {
        "source": data.source,
        "channel": data.channel,
        "campaign_id": data.campaign_id,
        "content_id": data.content_id,
        "lead_id": data.lead_id,
        "actor_id": data.actor_id,
        "type": data.event_type,
        "payload_json": data.payload_json,
    }
