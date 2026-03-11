import uuid
import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .routers.admin import router as admin_router
from .routers.ads import router as ads_router
from .routers.agents import router as agents_router
from .routers.analytics import router as analytics_router
from .routers.approvals import router as approvals_router
from .routers.audit import router as audit_router
from .routers.auth import router as auth_router
from .routers.billing import router as billing_router
from .routers.brand import router as brand_router
from .routers.campaigns import router as campaigns_router
from .routers.compliance import router as compliance_router
from .routers.connectors import router as connectors_router
from .routers.content import router as content_router
from .routers.events import router as events_router
from .routers.health import router as health_router
from .routers.inbox import router as inbox_router
from .routers.leads import router as leads_router
from .routers.leads import sla_router
from .routers.links import router as links_router
from .routers.onboarding import router as onboarding_router
from .routers.ops import router as ops_router
from .routers.optimization import router as optimization_router
from .routers.orgs import router as org_router
from .routers.presence import router as presence_router
from .routers.publish import router as publish_router
from .routers.real_estate import router as real_estate_router
from .routers.reputation import router as reputation_router
from .routers.seo import router as seo_router
from .routers.verticals import router as vertical_router
from .routers.workflows import router as workflows_router
from .services.verticals import validate_pack
from .settings import settings

app = FastAPI(title="OmniFlow API", version="0.1.0")
logger = logging.getLogger("omniflow.api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:  # type: ignore[override]
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin"
    return response


@app.middleware("http")
async def csrf_validation_middleware(request: Request, call_next) -> Response:  # type: ignore[override]
    if request.method in {"POST", "PUT", "DELETE"}:
        session_cookie = request.cookies.get(settings.auth_cookie_name)
        if session_cookie:
            csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name)
            csrf_header = request.headers.get("x-csrf-token")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                raise HTTPException(status_code=403, detail="csrf validation failed")
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:  # type: ignore[override]
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        json.dumps(
            {
                "service": "api",
                "event_type": "request_complete",
                "request_id": request_id,
                "org_id": request.headers.get("X-Org-Id"),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": exc.errors(), "request_id": request_id},
        headers={"X-Request-Id": request_id},
    )


@app.on_event("startup")
def validate_vertical_packs_on_startup() -> None:
    verticals_root = Path(__file__).resolve().parents[3] / "packages" / "verticals"
    if not verticals_root.exists():
        return
    for entry in verticals_root.iterdir():
        if not entry.is_dir():
            continue
        valid, errors = validate_pack(entry.name)
        if not valid:
            joined = "; ".join(errors)
            raise RuntimeError(f"Invalid vertical pack '{entry.name}': {joined}")
    logger.info(
        json.dumps(
            {
                "service": "api",
                "event_type": "startup_validated",
                "request_id": None,
                "org_id": None,
                "app_env": settings.app_env,
                "connector_mode": settings.connector_mode,
                "ai_mode": settings.ai_mode,
                "ads_mode": settings.ads_mode,
            }
        )
    )


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(org_router)
app.include_router(admin_router)
app.include_router(ops_router)
app.include_router(onboarding_router)
app.include_router(vertical_router)
app.include_router(events_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(campaigns_router)
app.include_router(content_router)
app.include_router(connectors_router)
app.include_router(publish_router)
app.include_router(brand_router)
app.include_router(links_router)
app.include_router(inbox_router)
app.include_router(leads_router)
app.include_router(sla_router)
app.include_router(presence_router)
app.include_router(seo_router)
app.include_router(reputation_router)
app.include_router(real_estate_router)
app.include_router(workflows_router)
app.include_router(approvals_router)
app.include_router(billing_router)
app.include_router(ads_router)
app.include_router(compliance_router)
app.include_router(optimization_router)
app.include_router(agents_router)
