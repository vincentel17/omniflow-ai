from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import check_db_health
from ..redis_client import get_redis_client
from ..settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, object]:
    checks = {"db": "ok", "redis": "ok"}
    try:
        check_db_health()
    except Exception:
        checks["db"] = "down"
    try:
        get_redis_client().ping()
    except Exception:
        checks["redis"] = "down"
    if checks["db"] != "ok" or checks["redis"] != "ok":
        raise HTTPException(status_code=503, detail={"status": "not_ready", "env": settings.app_env, "checks": checks})
    return {"status": "ready", "env": settings.app_env, "checks": checks}


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/healthz/db")
def healthz_db() -> dict[str, str]:
    try:
        check_db_health()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}

