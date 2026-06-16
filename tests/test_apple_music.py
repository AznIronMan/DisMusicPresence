from pathlib import Path
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dis_music_presence.models import ActivityKind
from dis_music_presence.settings import DEFAULT_SETTINGS, Settings
from dis_music_presence.sources.apple_music import AppleMusicProvider


class AppleMusicProviderTests(unittest.TestCase):
    def test_non_macos_is_unavailable(self) -> None:
        settings = Settings(path=Path("dmp.settings"), values=dict(DEFAULT_SETTINGS))
        provider = AppleMusicProvider(settings)

        with patch("platform.system", return_value="Linux"):
            activity = provider.poll()

        self.assertEqual(activity.kind, ActivityKind.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
