from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActivityKind(str, Enum):
    LISTENING = "listening"
    WATCHING = "watching"
    IDLE = "idle"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class MediaType(str, Enum):
    MUSIC = "music"
    MOVIE = "movie"
    EPISODE = "episode"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MediaActivity:
    kind: ActivityKind
    source: str
    media_type: MediaType = MediaType.UNKNOWN
    title: str = ""
    artist: str = ""
    album: str = ""
    show_title: str = ""
    season: int | None = None
    episode: int | None = None
    episode_title: str = ""
    player_state: str = ""
    message: str = ""
    raw: dict[str, Any] | None = None

    @property
    def is_active(self) -> bool:
        return self.kind in {ActivityKind.LISTENING, ActivityKind.WATCHING}

    @classmethod
    def idle(cls, source: str, message: str = "No active playback") -> "MediaActivity":
        return cls(kind=ActivityKind.IDLE, source=source, message=message)

    @classmethod
    def unavailable(cls, source: str, message: str) -> "MediaActivity":
        return cls(kind=ActivityKind.UNAVAILABLE, source=source, message=message)

    @classmethod
    def error(cls, source: str, message: str) -> "MediaActivity":
        return cls(kind=ActivityKind.ERROR, source=source, message=message)


@dataclass(frozen=True)
class FormattedPresence:
    text: str
    activity_type: int
    source: str


DISCORD_ACTIVITY_TYPES = {
    ActivityKind.LISTENING: 2,
    ActivityKind.WATCHING: 3,
}
