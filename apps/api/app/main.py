from fastapi import FastAPI

from .routers.audit import router as audit_router
from .routers.brand import router as brand_router
from .routers.campaigns import router as campaigns_router
from .routers.content import router as content_router
from .routers.connectors import router as connectors_router
from .routers.events import router as events_router
from .routers.health import router as health_router
from .routers.links import router as links_router
from .routers.orgs import router as org_router
from .routers.publish import router as publish_router
from .routers.verticals import router as vertical_router

app = FastAPI(title="OmniFlow API", version="0.1.0")
app.include_router(health_router)
app.include_router(org_router)
app.include_router(vertical_router)
app.include_router(events_router)
app.include_router(audit_router)
app.include_router(campaigns_router)
app.include_router(content_router)
app.include_router(connectors_router)
app.include_router(publish_router)
app.include_router(brand_router)
app.include_router(links_router)
