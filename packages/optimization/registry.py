from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .schema import ModelDescriptor, ModelStatus


@dataclass(slots=True)
class ModelRegistry:
    _models: dict[str, list[ModelDescriptor]]

    def __init__(self) -> None:
        self._models = {}

    def register(self, descriptor: ModelDescriptor) -> None:
        rows = self._models.setdefault(descriptor.name, [])
        if any(row.version == descriptor.version for row in rows):
            return
        rows.append(descriptor)
        rows.sort(key=lambda row: row.trained_at, reverse=True)

    def list(self, name: str | None = None) -> list[ModelDescriptor]:
        if name is not None:
            return list(self._models.get(name, []))
        merged: list[ModelDescriptor] = []
        for rows in self._models.values():
            merged.extend(rows)
        merged.sort(key=lambda row: row.trained_at, reverse=True)
        return merged

    def activate(self, *, name: str, version: str) -> ModelDescriptor | None:
        rows = self._models.get(name, [])
        target: ModelDescriptor | None = None
        for row in rows:
            if row.version == version:
                row.status = ModelStatus.ACTIVE
                target = row
            elif row.status == ModelStatus.ACTIVE:
                row.status = ModelStatus.INACTIVE
        return target

    def rollback(self, *, name: str, from_version: str) -> ModelDescriptor | None:
        rows = self._models.get(name, [])
        fallback: ModelDescriptor | None = None
        for row in rows:
            if row.version == from_version:
                row.status = ModelStatus.DEGRADED
                continue
            if fallback is None and row.status in {ModelStatus.INACTIVE, ModelStatus.EXPERIMENTAL}:
                fallback = row
        if fallback is not None:
            self.activate(name=name, version=fallback.version)
        return fallback

    def seed(
        self,
        *,
        name: str,
        version: str,
        training_window: str,
        metrics_json: dict[str, float],
        status: ModelStatus,
    ) -> ModelDescriptor:
        descriptor = ModelDescriptor(
            name=name,
            version=version,
            trained_at=datetime.now(UTC),
            training_window=training_window,
            metrics_json=metrics_json,
            status=status,
        )
        self.register(descriptor)
        return descriptor
