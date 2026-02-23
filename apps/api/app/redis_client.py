from __future__ import annotations

from redis import Redis

from .settings import settings


def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)

