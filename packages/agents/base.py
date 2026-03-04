from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from packages.schemas.phase16 import AgentContextSnapshotJSON, AgentPerceptionJSON, AgentPlanJSON


@dataclass(frozen=True)
class AgentIdentity:
    name: str
    version: str
    supported_packs: tuple[str, ...]


class AgentInterface(Protocol):
    identity: AgentIdentity

    def perceive(self, context: AgentContextSnapshotJSON) -> AgentPerceptionJSON: ...

    def propose(self, context: AgentContextSnapshotJSON, perception: AgentPerceptionJSON) -> AgentPlanJSON | None: ...
