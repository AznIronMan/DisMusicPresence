from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dis_music_presence.models import ActivityKind, MediaType
from dis_music_presence.settings import DEFAULT_SETTINGS, Settings
from dis_music_presence.sources.plex import PlexProvider


def _settings(**overrides: str) -> Settings:
    values = dict(DEFAULT_SETTINGS)
    values.update(
        {
            "plex.enabled": "true",
            "plex.provider": "auto",
            "plex.username": "alex",
            "tautulli.url": "http://tautulli.local",
            "tautulli.api_key": "key",
            "plex.url": "http://plex.local:32400",
            "plex.token": "token",
        }
    )
    values.update(overrides)
    return Settings(path=Path("dmp.settings"), values=values)


class PlexProviderTests(unittest.TestCase):
    def test_tautulli_episode_matches_configured_user(self) -> None:
        provider = PlexProvider(_settings())
        sessions = [
            {"user": "other", "state": "playing", "media_type": "movie", "title": "Wrong"},
            {
                "user": "alex",
                "state": "playing",
                "media_type": "episode",
                "title": "Pilot",
                "grandparent_title": "Show",
                "parent_media_index": "1",
                "media_index": "2",
            },
        ]

        activity = provider._activity_from_tautulli_sessions(sessions)

        self.assertEqual(activity.kind, ActivityKind.WATCHING)
        self.assertEqual(activity.media_type, MediaType.EPISODE)
        self.assertEqual(activity.show_title, "Show")
        self.assertEqual(activity.season, 1)
        self.assertEqual(activity.episode, 2)

    def test_tautulli_requires_matching_user(self) -> None:
        provider = PlexProvider(_settings(plex_username="alex"))

        activity = provider._activity_from_tautulli_sessions(
            [{"user": "other", "state": "playing", "media_type": "movie", "title": "Wrong"}]
        )

        self.assertEqual(activity.kind, ActivityKind.IDLE)

    def test_plex_xml_movie_matches_user_id(self) -> None:
        provider = PlexProvider(_settings(**{"plex.username": "", "plex.user_id": "42"}))
        xml = ET.fromstring(
            """
            <MediaContainer>
              <Video type="movie" title="Movie">
                <User id="42" title="alex" />
                <Player state="playing" />
              </Video>
            </MediaContainer>
            """
        )

        activity = provider._activity_from_plex_videos(xml.findall(".//Video"))

        self.assertEqual(activity.kind, ActivityKind.WATCHING)
        self.assertEqual(activity.media_type, MediaType.MOVIE)
        self.assertEqual(activity.title, "Movie")


if __name__ == "__main__":
    unittest.main()
