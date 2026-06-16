from __future__ import annotations

import re
from collections import defaultdict

from .models import ActivityKind, DISCORD_ACTIVITY_TYPES, FormattedPresence, MediaActivity, MediaType
from .settings import DEFAULT_SETTINGS, Settings


class PresenceFormatter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def format(self, activity: MediaActivity) -> FormattedPresence | None:
        if not activity.is_active:
            return None

        values = self._values(activity)
        if activity.kind is ActivityKind.LISTENING:
            template = self._setting("format.listening")
        elif activity.media_type is MediaType.EPISODE:
            template = self._setting("format.watching_episode")
        else:
            template = self._setting("format.watching_movie")

        text = _clean_text(template.format_map(defaultdict(str, values)))
        if not text:
            return None

        activity_type = DISCORD_ACTIVITY_TYPES.get(activity.kind, 0)
        return FormattedPresence(text=text, activity_type=activity_type, source=activity.source)

    def _setting(self, key: str) -> str:
        if self.settings is None:
            return DEFAULT_SETTINGS[key]
        return self.settings.get(key, DEFAULT_SETTINGS[key])

    def _values(self, activity: MediaActivity) -> dict[str, str]:
        title = activity.title or activity.episode_title or activity.show_title
        artist = activity.artist or "Unknown Artist"
        episode_code = _episode_code(activity.season, activity.episode)
        episode_title = activity.episode_title or activity.title
        show_title = activity.show_title or activity.title
        values = {
            "source": activity.source,
            "player_state": activity.player_state,
            "title": title,
            "artist": artist,
            "album": activity.album,
            "show_title": show_title,
            "season": "" if activity.season is None else str(activity.season),
            "episode": "" if activity.episode is None else str(activity.episode),
            "episode_code": episode_code,
            "episode_title": episode_title,
        }
        return values


def _episode_code(season: int | None, episode: int | None) -> str:
    if season is None and episode is None:
        return ""
    if season is None:
        return f"E{episode:02d}"
    if episode is None:
        return f"S{season:02d}"
    return f"S{season:02d}E{episode:02d}"


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+-\s+-\s+", " - ", text)
    text = re.sub(r"\s+-\s*$", "", text)
    text = re.sub(r"^\s*-\s+", "", text)
    return text.strip()
