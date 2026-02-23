from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from redis import Redis

STATE_PREFIX = "omniflow:oauth:state:"
STATE_TTL_SECONDS = 600


def create_oauth_state(
    redis_client: Redis,
    org_id: uuid.UUID,
    provider: str,
) -> str:
    state = uuid.uuid4().hex
    payload = {
        "org_id": str(org_id),
        "provider": provider,
        "created_at": datetime.now(UTC).isoformat(),
    }
    redis_client.setex(f"{STATE_PREFIX}{state}", STATE_TTL_SECONDS, json.dumps(payload))
    return state


def consume_oauth_state(redis_client: Redis, state: str) -> dict[str, str] | None:
    key = f"{STATE_PREFIX}{state}"
    raw = redis_client.get(key)
    if raw is None:
        return None
    redis_client.delete(key)
    data = json.loads(raw)
    return {
        "org_id": str(data["org_id"]),
        "provider": str(data["provider"]),
        "created_at": str(data["created_at"]),
    }

