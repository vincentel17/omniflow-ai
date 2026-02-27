import uuid

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

from .routers.ads import router as ads_router
from .routers.analytics import router as analytics_router
from .routers.approvals import router as approvals_router
from .routers.audit import router as audit_router
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
from .routers.orgs import router as org_router
from .routers.presence import router as presence_router
from .routers.publish import router as publish_router
from .routers.real_estate import router as real_estate_router
from .routers.reputation import router as reputation_router
from .routers.seo import router as seo_router
from .routers.verticals import router as vertical_router
from .routers.workflows import router as workflows_router

app = FastAPI(title="OmniFlow API", version="0.1.0")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next) -> Response:  # type: ignore[override]
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


app.include_router(health_router)
app.include_router(org_router)
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
app.include_router(ads_router)
app.include_router(compliance_router)


