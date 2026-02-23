from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import REChecklistTemplate, REDeal, RECMAComparable, VerticalPack
from .verticals import load_pack_template


def ensure_real_estate_pack(db: Session, org_id: Any) -> bool:
    selected = db.scalar(select(VerticalPack).where(VerticalPack.org_id == org_id, VerticalPack.deleted_at.is_(None)))
    return selected is not None and selected.pack_slug == "real-estate"


def get_required_disclaimers(policy_rules: dict[str, Any], key: str) -> list[str]:
    return [str(item) for item in policy_rules.get("content", {}).get("required_disclaimers", {}).get(key, [])]


def append_disclaimers(text: str, disclaimers: list[str]) -> str:
    out = text.strip()
    for disclaimer in disclaimers:
        if disclaimer.lower() not in out.lower():
            out = f"{out}\n{disclaimer}"
    return out


def calculate_cma_pricing(comps: list[RECMAComparable]) -> dict[str, Any]:
    price_per_sqft: list[float] = []
    direct_prices: list[int] = []
    for comp in comps:
        comp_price = comp.sold_price or comp.list_price
        if comp_price is None or comp_price <= 0:
            continue
        direct_prices.append(comp_price)
        if comp.sqft and comp.sqft > 0:
            price_per_sqft.append(comp_price / comp.sqft)

    if not direct_prices:
        return {
            "suggested_range_low": 0,
            "suggested_range_high": 0,
            "suggested_price": 0,
            "rationale_points": ["No valid comparable pricing data provided."],
        }

    med_price = int(median(direct_prices))
    spread = max(10_000, int(med_price * 0.04))
    if price_per_sqft:
        ppsf_med = round(median(price_per_sqft), 2)
        rationale = [f"Median price per sqft across comps: {ppsf_med}."]
    else:
        rationale = ["Median sale/list price used due to missing square footage on some comps."]
    rationale.extend(
        [
            f"Median comparable price observed: {med_price}.",
            "Range widened conservatively to absorb condition and micro-location variance.",
        ]
    )
    return {
        "suggested_range_low": max(0, med_price - spread),
        "suggested_range_high": med_price + spread,
        "suggested_price": med_price,
        "rationale_points": rationale,
    }


def render_cma_narrative(pricing: dict[str, Any], subject_property: dict[str, Any]) -> str:
    template = load_pack_template("real-estate", "cma_narrative.txt")
    return (
        template.replace("{{property_address}}", str(subject_property.get("address", "Subject Property")))
        .replace("{{range_low}}", str(pricing.get("suggested_range_low", 0)))
        .replace("{{range_high}}", str(pricing.get("suggested_range_high", 0)))
        .replace("{{suggested_price}}", str(pricing.get("suggested_price", 0)))
        .replace("{{rationale_1}}", str((pricing.get("rationale_points") or ["N/A"])[0]))
        .replace("{{rationale_2}}", str((pricing.get("rationale_points") or ["N/A", "N/A", "N/A"])[1]))
        .replace("{{rationale_3}}", str((pricing.get("rationale_points") or ["N/A", "N/A", "N/A"])[2]))
    )


def resolve_checklist_template(
    db: Session,
    org_id: Any,
    deal_type: str,
    name: str,
    state_code: str | None,
) -> REChecklistTemplate | None:
    stmt = select(REChecklistTemplate).where(
        REChecklistTemplate.org_id == org_id,
        REChecklistTemplate.name == name,
        REChecklistTemplate.deal_type == deal_type,
        REChecklistTemplate.deleted_at.is_(None),
    )
    if state_code:
        state_match = db.scalar(stmt.where(REChecklistTemplate.state_code == state_code))
        if state_match is not None:
            return state_match
    return db.scalar(stmt.where(REChecklistTemplate.state_code.is_(None)))


def compute_due_at(
    important_dates: dict[str, Any],
    anchor_field: str | None,
    offset_days: int,
) -> datetime | None:
    if not anchor_field:
        return None
    raw = important_dates.get(anchor_field)
    if not raw:
        return None
    try:
        base = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if base.tzinfo is None:
            base = base.replace(tzinfo=UTC)
    except ValueError:
        return None
    return base + timedelta(days=offset_days)


def build_listing_social_pack(property_address: str) -> dict[str, Any]:
    return {
        "channels": ["facebook", "instagram", "linkedin"],
        "posts": [
            {
                "channel": "facebook",
                "account_ref": "primary",
                "hook": f"Just listed: {property_address}",
                "value_points": ["Updated interior", "Great location", "Tour availability this weekend"],
                "cta": "Book your showing",
            },
            {
                "channel": "instagram",
                "account_ref": "primary",
                "hook": f"Open house this weekend at {property_address}",
                "value_points": ["Photo highlights", "Neighborhood access", "Move-in-ready details"],
                "cta": "DM for details",
            },
            {
                "channel": "linkedin",
                "account_ref": "primary",
                "hook": f"Market update + featured listing: {property_address}",
                "value_points": ["Price positioning", "Buyer demand signal", "Timeline to close"],
                "cta": "Request full listing packet",
            },
        ],
        "schedule_suggestions": ["T-5d", "T-2d", "T+1d follow-up"],
    }


def default_checklist_items_for_deal(deal: REDeal) -> list[dict[str, Any]]:
    return [
        {
            "title": "Confirm financing / proof of funds",
            "description": "Collect buyer financing evidence.",
            "anchor_date_field": "contract_date",
            "offset_days": 0,
        },
        {
            "title": "Schedule inspection",
            "description": "Coordinate inspector and stakeholders.",
            "anchor_date_field": "contract_date",
            "offset_days": 5,
        },
        {
            "title": "Review appraisal timeline",
            "description": "Track appraisal milestones with lender.",
            "anchor_date_field": "contract_date",
            "offset_days": 10,
        },
        {
            "title": "Pre-closing checklist",
            "description": "Finalize walkthrough and closing packet.",
            "anchor_date_field": "closing_date",
            "offset_days": -2,
        },
    ]
