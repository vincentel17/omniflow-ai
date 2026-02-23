from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .models import RiskTier, Role


class OrgCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class MembershipUpsertRequest(BaseModel):
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: Role


class MembershipResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    created_at: datetime


class VerticalPackSelectRequest(BaseModel):
    pack_slug: str = Field(min_length=1, max_length=100)


class VerticalPackResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    pack_slug: str
    created_at: datetime


class EventCreateRequest(BaseModel):
    source: str
    channel: str
    campaign_id: str | None = None
    content_id: str | None = None
    lead_id: str | None = None
    actor_id: str | None = None
    type: str
    payload_json: dict[str, object] = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    source: str
    channel: str
    campaign_id: str | None = None
    content_id: str | None = None
    lead_id: str | None = None
    actor_id: str | None = None
    type: str
    payload_json: dict[str, object]
    created_at: datetime


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    target_type: str
    target_id: str
    risk_tier: RiskTier
    metadata_json: dict[str, object]
    created_at: datetime
