from __future__ import annotations

from dataclasses import dataclass

from ..models import MediaActivity


@dataclass(frozen=True)
class SourceCapability:
    name: str
    enabled: bool
    supported: bool
    configured: bool
    message: str


class SourceProvider:
    name = "source"

    def poll(self) -> MediaActivity:
        raise NotImplementedError

    def capability(self) -> SourceCapability:
        return SourceCapability(
            name=self.name,
            enabled=True,
            supported=True,
            configured=True,
            message="Available",
        )
