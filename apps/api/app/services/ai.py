from __future__ import annotations

from datetime import date
from typing import Any

from packages.schemas import CampaignPlanJSON, CampaignPlanPost, ContentItemJSON

from ..settings import settings


def _mock_campaign_plan(week_start_date: date, channels: list[str], objectives: list[str]) -> CampaignPlanJSON:
    primary_channel = channels[0] if channels else "linkedin"
    return CampaignPlanJSON(
        week_start=week_start_date,
        objectives=objectives or ["Generate qualified leads"],
        themes=["Customer outcomes", "Proof points"],
        channels=channels or ["linkedin"],
        posts=[
            CampaignPlanPost(
                channel=primary_channel,
                account_ref="default",
                hook="Turn engagement into attributable pipeline this week.",
                value_points=[
                    "Track every touchpoint from post to lead",
                    "Prioritize fast-response opportunities",
                ],
                cta="Book a strategy call",
                compliance_notes=[],
            )
        ],
    )


def _mock_content_item(post: dict[str, Any]) -> ContentItemJSON:
    return ContentItemJSON(
        channel=str(post.get("channel", "linkedin")),
        caption=f"{post.get('hook', 'Weekly update')}\n\n{post.get('cta', 'Learn more')}",
        hashtags=["#RevenueOps", "#SMB"],
        cta=str(post.get("cta", "Learn more")),
        link_url=None,
        media_prompt="Professional team discussing customer growth metrics",
        disclaimers=[str(note) for note in post.get("compliance_notes", [])],
    )


def generate_campaign_plan(week_start_date: date, channels: list[str], objectives: list[str]) -> CampaignPlanJSON:
    if settings.ai_mode == "live":
        raise NotImplementedError("AI live mode is not implemented yet")
    return _mock_campaign_plan(week_start_date=week_start_date, channels=channels, objectives=objectives)


def generate_content_items(plan_json: CampaignPlanJSON) -> list[ContentItemJSON]:
    if settings.ai_mode == "live":
        raise NotImplementedError("AI live mode is not implemented yet")
    return [_mock_content_item(post.model_dump()) for post in plan_json.posts]
