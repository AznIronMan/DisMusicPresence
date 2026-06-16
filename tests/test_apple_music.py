from pathlib import Path
from types import SimpleNamespace
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

    def test_uses_configured_timeout(self) -> None:
        values = dict(DEFAULT_SETTINGS)
        values["apple_music.timeout_seconds"] = "12"
        settings = Settings(path=Path("dmp.settings"), values=values)
        provider = AppleMusicProvider(settings)

        with patch("platform.system", return_value="Darwin"), patch(
            "subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout="not_running\n", stderr=""),
        ) as run:
            provider.poll()

        self.assertEqual(run.call_args.kwargs["timeout"], 12)


if __name__ == "__main__":
    unittest.main()
