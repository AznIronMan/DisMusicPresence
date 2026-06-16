from __future__ import annotations

import platform
import subprocess

from ..models import ActivityKind, MediaActivity, MediaType
from ..settings import Settings
from .base import SourceCapability, SourceProvider


APPLESCRIPT = """
tell application "System Events"
    if not (exists process "Music") then return "not_running"
end tell

tell application "Music"
    if player state is not playing then
        return "idle" & linefeed & (player state as string)
    end if

    set currentTrack to current track
    set trackName to ""
    set artistName to ""
    set albumName to ""

    try
        set trackName to name of currentTrack
    end try
    try
        set artistName to artist of currentTrack
    end try
    try
        set albumName to album of currentTrack
    end try

    return "playing" & linefeed & trackName & linefeed & artistName & linefeed & albumName
end tell
""".strip()


class AppleMusicProvider(SourceProvider):
    name = "apple_music"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def capability(self) -> SourceCapability:
        enabled = self.settings.bool("apple_music.enabled", True)
        supported = platform.system() == "Darwin"
        if not enabled:
            return SourceCapability(self.name, False, supported, True, "Apple Music source is disabled.")
        if not supported:
            return SourceCapability(self.name, enabled, False, True, "Apple Music is supported on macOS only.")
        return SourceCapability(self.name, enabled, True, True, "Apple Music source is available.")

    def poll(self) -> MediaActivity:
        capability = self.capability()
        if not capability.enabled:
            return MediaActivity.idle(self.name, capability.message)
        if not capability.supported:
            return MediaActivity.unavailable(self.name, capability.message)

        try:
            result = subprocess.run(
                ["osascript", "-e", APPLESCRIPT],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return MediaActivity.error(self.name, f"Apple Music check failed: {exc}")

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Apple Music automation failed.").strip()
            return MediaActivity.error(self.name, message)

        lines = result.stdout.splitlines()
        state = lines[0].strip() if lines else ""
        if state == "not_running":
            return MediaActivity.idle(self.name, "Apple Music is not running.")
        if state == "idle":
            player_state = lines[1].strip() if len(lines) > 1 else "idle"
            return MediaActivity.idle(self.name, f"Apple Music is {player_state}.")
        if state != "playing":
            return MediaActivity.idle(self.name, "Apple Music is not playing.")

        title = lines[1].strip() if len(lines) > 1 else ""
        artist = lines[2].strip() if len(lines) > 2 else ""
        album = lines[3].strip() if len(lines) > 3 else ""
        if not title:
            return MediaActivity.error(self.name, "Apple Music is playing but track metadata is unavailable.")

        return MediaActivity(
            kind=ActivityKind.LISTENING,
            source="Apple Music",
            media_type=MediaType.MUSIC,
            title=title,
            artist=artist,
            album=album,
            player_state="playing",
        )
