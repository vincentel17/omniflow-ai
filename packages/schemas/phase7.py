from __future__ import annotations

from pydantic import BaseModel, Field


class CMAComparableInputJSON(BaseModel):
    address: str = Field(min_length=1, max_length=500)
    status: str = Field(pattern="^(sold|active|pending)$")
    sold_price: int | None = Field(default=None, ge=0)
    list_price: int | None = Field(default=None, ge=0)
    beds: float | None = Field(default=None, ge=0)
    baths: float | None = Field(default=None, ge=0)
    sqft: int | None = Field(default=None, ge=0)
    year_built: int | None = Field(default=None, ge=0)
    days_on_market: int | None = Field(default=None, ge=0)
    distance_miles: float | None = Field(default=None, ge=0)
    adjustments_json: dict[str, object] = Field(default_factory=dict)


class CMAPricingJSON(BaseModel):
    suggested_range_low: int = Field(ge=0)
    suggested_range_high: int = Field(ge=0)
    suggested_price: int = Field(ge=0)
    rationale_points: list[str] = Field(default_factory=list, max_length=10)
    narrative: str = Field(min_length=1)
    disclaimers: list[str] = Field(default_factory=list, max_length=8)


class ListingPackageJSON(BaseModel):
    description_variants: dict[str, str] = Field(default_factory=dict)
    key_features: list[str] = Field(default_factory=list, max_length=30)
    open_house_plan: dict[str, object] = Field(default_factory=dict)
    social_campaign_pack: dict[str, object] = Field(default_factory=dict)
    disclaimers: list[str] = Field(default_factory=list, max_length=8)
