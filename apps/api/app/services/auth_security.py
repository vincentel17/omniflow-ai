from __future__ import annotations

import json
import logging
import secrets
import uuid
from typing import Final

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from ..models import AuthAuditEvent
from ..redis_client import get_redis_client

logger = logging.getLogger("omniflow.api.security")

LOGIN_RATE_LIMIT_WINDOW_SECONDS: Final[int] = 5 * 60
LOGIN_RATE_LIMIT_MAX_ATTEMPTS: Final[int] = 5


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    client_host = request.client.host if request.client else ""
    return client_host or "unknown"


def issue_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def enforce_login_rate_limit(request: Request) -> None:
    ip_address = get_client_ip(request)
    key = f"auth:login:{ip_address}"
    try:
        redis = get_redis_client()
        current = redis.incr(key)
        if int(current) == 1:
            redis.expire(key, LOGIN_RATE_LIMIT_WINDOW_SECONDS)
        if int(current) > LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            logger.warning(
                json.dumps(
                    {
                        "service": "api",
                        "event_type": "security_rate_limit_exceeded",
                        "request_id": getattr(request.state, "request_id", None),
                        "user_id": None,
                        "org_id": None,
                        "ip_address": ip_address,
                    }
                )
            )
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many login attempts")
    except HTTPException:
        raise
    except RedisError:
        return


def log_auth_event(
    db: Session,
    request: Request,
    event_type: str,
    user_id: uuid.UUID | None,
    org_id: uuid.UUID | None,
) -> None:
    event = AuthAuditEvent(
        user_id=user_id,
        org_id=org_id,
        event_type=event_type,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.add(event)
    logger.info(
        json.dumps(
            {
                "service": "api",
                "event_type": event_type,
                "request_id": getattr(request.state, "request_id", None),
                "user_id": str(user_id) if user_id else None,
                "org_id": str(org_id) if org_id else None,
                "ip_address": event.ip_address,
            }
        )
    )
