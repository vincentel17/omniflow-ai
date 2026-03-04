from __future__ import annotations

from collections.abc import Iterable

from packages.schemas.phase16 import AgentContextSnapshotJSON, AgentPlanJSON

from .base import AgentIdentity, AgentInterface
from .mocks import GrowthAgent, InboxAgent, PresenceAgent, RealEstateOpsAgent, ReputationAgent, SEOAgent


class SupervisorAgent:
    identity = AgentIdentity(name="SupervisorAgent", version="1.0.0", supported_packs=("generic", "real-estate", "home-care"))

    def __init__(self) -> None:
        self._agents: list[AgentInterface] = [
            InboxAgent(),
            GrowthAgent(),
            PresenceAgent(),
            SEOAgent(),
            ReputationAgent(),
            RealEstateOpsAgent(),
        ]

    def select_agents(self, context: AgentContextSnapshotJSON) -> list[AgentInterface]:
        needs_inbox = int(context.inbox_summary.get("sla_breaches", 0)) > 0 or int(context.inbox_summary.get("open_threads", 0)) > 10
        needs_growth = int(context.leads_summary.get("stale", 0)) > 0 or int(context.leads_summary.get("new", 0)) > 0
        needs_presence = float(context.presence_summary.get("latest_score", 100) or 100) < 70
        needs_seo = needs_presence or int(context.seo_summary.get("drafts_pending", 0)) == 0
        needs_reputation = int(context.reputation_summary.get("unresponded_negative_reviews", 0)) > 0
        needs_re_ops = context.active_pack_slug == "real-estate" and int((context.re_ops_summary or {}).get("overdue_checklists", 0)) > 0

        selected: list[AgentInterface] = []
        for agent in self._agents:
            if context.active_pack_slug not in agent.identity.supported_packs and "generic" not in agent.identity.supported_packs:
                continue
            if agent.identity.name == "RealEstateOpsAgent" and context.active_pack_slug != "real-estate":
                continue
            if agent.identity.name == "InboxAgent" and not needs_inbox:
                continue
            if agent.identity.name == "GrowthAgent" and not needs_growth:
                continue
            if agent.identity.name == "PresenceAgent" and not needs_presence:
                continue
            if agent.identity.name == "SEOAgent" and not needs_seo:
                continue
            if agent.identity.name == "ReputationAgent" and not needs_reputation:
                continue
            if agent.identity.name == "RealEstateOpsAgent" and not needs_re_ops:
                continue
            selected.append(agent)
        if not selected:
            for agent in self._agents:
                if agent.identity.name == "GrowthAgent":
                    selected.append(agent)
                    break
        return selected

    def propose(self, context: AgentContextSnapshotJSON) -> list[AgentPlanJSON]:
        plans: list[AgentPlanJSON] = []
        for agent in self.select_agents(context):
            perception = agent.perceive(context)
            plan = agent.propose(context, perception)
            if plan is not None:
                plans.append(plan)
        return self._resolve_conflicts(plans)

    def _resolve_conflicts(self, plans: Iterable[AgentPlanJSON]) -> list[AgentPlanJSON]:
        seen_task_targets: set[str] = set()
        seen_publish_slots: set[str] = set()
        out: list[AgentPlanJSON] = []

        for plan in plans:
            filtered_steps = []
            for step in plan.steps:
                if step.action_type == "CREATE_TASK":
                    key = step.target_ref
                    if key in seen_task_targets:
                        continue
                    seen_task_targets.add(key)
                if step.action_type == "SCHEDULE_PUBLISH":
                    channel = str(step.inputs_json.get("channel", "default"))
                    account = str(step.inputs_json.get("account_ref", "default"))
                    when = str(step.inputs_json.get("schedule_at", "unspecified"))
                    slot = f"{channel}:{account}:{when}"
                    if slot in seen_publish_slots:
                        continue
                    seen_publish_slots.add(slot)
                filtered_steps.append(step)
            if not filtered_steps:
                continue
            out.append(plan.model_copy(update={"steps": filtered_steps}))
        return out
