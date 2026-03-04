from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.phase16 import AgentContextSnapshotJSON, AgentPlanJSON

from .supervisor import SupervisorAgent


@dataclass
class AgentOrchestrator:
    supervisor: SupervisorAgent

    @classmethod
    def build_default(cls) -> "AgentOrchestrator":
        return cls(supervisor=SupervisorAgent())

    def propose(self, context: AgentContextSnapshotJSON) -> list[AgentPlanJSON]:
        return self.supervisor.propose(context)
