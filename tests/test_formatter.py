from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dis_music_presence.formatter import PresenceFormatter
from dis_music_presence.models import ActivityKind, MediaActivity, MediaType


class FormatterTests(unittest.TestCase):
    def test_formats_listening_presence(self) -> None:
        activity = MediaActivity(
            kind=ActivityKind.LISTENING,
            source="Apple Music",
            media_type=MediaType.MUSIC,
            title="Song",
            artist="Artist",
        )

        presence = PresenceFormatter().format(activity)

        self.assertIsNotNone(presence)
        self.assertEqual(presence.text, "Listening to \u266a Artist - Song")
        self.assertEqual(presence.activity_type, 2)

    def test_formats_episode_presence(self) -> None:
        activity = MediaActivity(
            kind=ActivityKind.WATCHING,
            source="Plex",
            media_type=MediaType.EPISODE,
            show_title="Show",
            season=1,
            episode=2,
            episode_title="Pilot",
        )

        presence = PresenceFormatter().format(activity)

        self.assertIsNotNone(presence)
        self.assertEqual(presence.text, "Watching Show - S01E02 - Pilot")
        self.assertEqual(presence.activity_type, 3)

    def test_idle_activity_has_no_presence(self) -> None:
        presence = PresenceFormatter().format(MediaActivity.idle("test"))

        self.assertIsNone(presence)


if __name__ == "__main__":
    unittest.main()
