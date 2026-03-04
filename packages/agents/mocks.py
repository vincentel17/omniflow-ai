from __future__ import annotations

import uuid
from typing import Iterable

from packages.schemas.phase16 import (
    AgentContextSnapshotJSON,
    AgentObservation,
    AgentOpportunity,
    AgentPerceptionJSON,
    AgentPlanJSON,
    AgentPlanStepJSON,
)

from .base import AgentIdentity, AgentInterface


class _SimpleAgent(AgentInterface):
    identity: AgentIdentity

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        return AgentPerceptionJSON(observations=[], opportunities=[], risks=[])

    def propose(self, context: AgentContextSnapshotJSON, perception: AgentPerceptionJSON) -> AgentPlanJSON | None:
        if not perception.opportunities:
            return None
        step = self._build_step(context, perception.opportunities)
        if step is None:
            return None
        return AgentPlanJSON(
            plan_id=str(uuid.uuid4()),
            agent_name=self.identity.name,
            agent_version=self.identity.version,
            objective=step.expected_outcome,
            steps=[step],
            rationale=f"{self.identity.name} selected a bounded low-risk action.",
            rollback_strategy="Revert by marking created artifacts canceled/closed via workflow controls.",
        )

    def _build_step(
        self,
        context: AgentContextSnapshotJSON,
        opportunities: Iterable[AgentOpportunity],
    ) -> AgentPlanStepJSON | None:
        return None


class InboxAgent(_SimpleAgent):
    identity = AgentIdentity(name="InboxAgent", version="1.0.0", supported_packs=("generic", "real-estate", "home-care"))

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        breaches = int(context.inbox_summary.get("sla_breaches", 0))
        open_threads = int(context.inbox_summary.get("open_threads", 0))
        opportunities: list[AgentOpportunity] = []
        if breaches > 0:
            opportunities.append(AgentOpportunity(type="sla_breach", estimated_impact=80, estimated_effort=30, details={"count": breaches}))
        elif open_threads > 10:
            opportunities.append(AgentOpportunity(type="reply_backlog", estimated_impact=60, estimated_effort=25, details={"count": open_threads}))
        return AgentPerceptionJSON(
            observations=[AgentObservation(type="inbox", value={"open_threads": open_threads, "sla_breaches": breaches})],
            opportunities=opportunities,
            risks=[],
        )

    def _build_step(self, context: AgentContextSnapshotJSON, opportunities: Iterable[AgentOpportunity]) -> AgentPlanStepJSON | None:
        return AgentPlanStepJSON(
            step_id="inbox-draft-reply",
            action_type="DRAFT_REPLY",
            target_ref="thread:unassigned",
            inputs_json={"thread_id": "00000000-0000-0000-0000-000000000000", "body_text": "AI agent draft for fastest SLA recovery."},
            expected_outcome="Generate one safe response draft to reduce SLA backlog.",
            risk_tier=1,
            requires_approval=False,
        )


class GrowthAgent(_SimpleAgent):
    identity = AgentIdentity(name="GrowthAgent", version="1.0.0", supported_packs=("generic", "real-estate", "home-care"))

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        stale = int(context.leads_summary.get("stale", 0))
        opportunities: list[AgentOpportunity] = []
        if stale > 0:
            opportunities.append(AgentOpportunity(type="stale_leads", estimated_impact=70, estimated_effort=20, details={"count": stale}))
        return AgentPerceptionJSON(
            observations=[AgentObservation(type="leads", value=context.leads_summary)],
            opportunities=opportunities,
            risks=[],
        )

    def _build_step(self, context: AgentContextSnapshotJSON, opportunities: Iterable[AgentOpportunity]) -> AgentPlanStepJSON | None:
        return AgentPlanStepJSON(
            step_id="growth-content-draft",
            action_type="CREATE_CONTENT_DRAFT",
            target_ref="campaign:weekly",
            inputs_json={"channel": "web", "text": "High-intent conversion post draft", "template_key": "growth_agent"},
            expected_outcome="Create one draft for review and downstream scheduling.",
            risk_tier=1,
            requires_approval=False,
        )


class PresenceAgent(_SimpleAgent):
    identity = AgentIdentity(name="PresenceAgent", version="1.0.0", supported_packs=("generic", "real-estate", "home-care"))

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        score = float(context.presence_summary.get("latest_score", 100) or 100)
        opportunities: list[AgentOpportunity] = []
        if score < 70:
            opportunities.append(AgentOpportunity(type="low_presence_score", estimated_impact=65, estimated_effort=15, details={"score": score}))
        return AgentPerceptionJSON(observations=[AgentObservation(type="presence", value={"latest_score": score})], opportunities=opportunities, risks=[])

    def _build_step(self, context: AgentContextSnapshotJSON, opportunities: Iterable[AgentOpportunity]) -> AgentPlanStepJSON | None:
        return AgentPlanStepJSON(
            step_id="presence-audit",
            action_type="RUN_PRESENCE_AUDIT",
            target_ref="presence:latest",
            inputs_json={},
            expected_outcome="Run guarded presence audit and surface findings.",
            risk_tier=0,
            requires_approval=False,
        )


class SEOAgent(_SimpleAgent):
    identity = AgentIdentity(name="SEOAgent", version="1.0.0", supported_packs=("generic", "real-estate", "home-care"))

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        pending = int(context.seo_summary.get("drafts_pending", 0))
        opportunities = [] if pending > 0 else [AgentOpportunity(type="seo_draft_gap", estimated_impact=55, estimated_effort=20, details={})]
        return AgentPerceptionJSON(observations=[AgentObservation(type="seo", value=context.seo_summary)], opportunities=opportunities, risks=[])

    def _build_step(self, context: AgentContextSnapshotJSON, opportunities: Iterable[AgentOpportunity]) -> AgentPlanStepJSON | None:
        return AgentPlanStepJSON(
            step_id="seo-content-draft",
            action_type="CREATE_CONTENT_DRAFT",
            target_ref="seo:cluster",
            inputs_json={"channel": "web", "template_key": "seo_agent", "text": "SEO draft generated for priority cluster."},
            expected_outcome="Create an SEO-first draft for approval.",
            risk_tier=1,
            requires_approval=False,
        )


class ReputationAgent(_SimpleAgent):
    identity = AgentIdentity(name="ReputationAgent", version="1.0.0", supported_packs=("generic", "real-estate", "home-care"))

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        unresponded_negative = int(context.reputation_summary.get("unresponded_negative_reviews", 0))
        opportunities = []
        if unresponded_negative > 0:
            opportunities.append(AgentOpportunity(type="negative_reviews", estimated_impact=75, estimated_effort=25, details={"count": unresponded_negative}))
        return AgentPerceptionJSON(observations=[AgentObservation(type="reputation", value=context.reputation_summary)], opportunities=opportunities, risks=[])

    def _build_step(self, context: AgentContextSnapshotJSON, opportunities: Iterable[AgentOpportunity]) -> AgentPlanStepJSON | None:
        return AgentPlanStepJSON(
            step_id="reputation-followup-task",
            action_type="CREATE_TASK",
            target_ref="lead:reputation",
            inputs_json={"title": "Respond to negative review", "template_key": "reputation_followup"},
            expected_outcome="Create a follow-up task for review remediation.",
            risk_tier=2,
            requires_approval=True,
        )


class RealEstateOpsAgent(_SimpleAgent):
    identity = AgentIdentity(name="RealEstateOpsAgent", version="1.0.0", supported_packs=("real-estate",))

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON:
        overdue = int((context.re_ops_summary or {}).get("overdue_checklists", 0))
        opportunities = []
        if overdue > 0:
            opportunities.append(AgentOpportunity(type="overdue_checklist", estimated_impact=70, estimated_effort=25, details={"count": overdue}))
        return AgentPerceptionJSON(observations=[AgentObservation(type="re_ops", value=context.re_ops_summary or {})], opportunities=opportunities, risks=[])

    def _build_step(self, context: AgentContextSnapshotJSON, opportunities: Iterable[AgentOpportunity]) -> AgentPlanStepJSON | None:
        return AgentPlanStepJSON(
            step_id="re-ops-task",
            action_type="CREATE_TASK",
            target_ref="deal:overdue",
            inputs_json={"title": "Resolve overdue deal checklist", "template_key": "re_ops_overdue"},
            expected_outcome="Create checklist remediation task for RE ops.",
            risk_tier=2,
            requires_approval=True,
        )
