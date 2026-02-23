from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from redis.exceptions import RedisError

from ..redis_client import get_redis_client


def _current_bucket(window_seconds: int) -> int:
    now = int(datetime.now(UTC).timestamp())
    return now // window_seconds


def enforce_org_rate_limit(
    org_id: uuid.UUID,
    bucket_name: str,
    max_requests: int,
    window_seconds: int = 60,
) -> None:
    if max_requests <= 0:
        return
    bucket = _current_bucket(window_seconds)
    key = f"ratelimit:{org_id}:{bucket_name}:{bucket}"
    ttl = max(1, window_seconds)
    try:
        redis = get_redis_client()
        current = redis.incr(key)
        if int(current) == 1:
            redis.expire(key, ttl)
        if int(current) > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"rate limit exceeded for {bucket_name}",
            )
    except HTTPException:
        raise
    except RedisError:
        # Degrade open if Redis is unavailable.
        return
