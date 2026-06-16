from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dis_music_presence.settings import init_settings, load_settings, set_setting


class SettingsTests(unittest.TestCase):
    def test_initializes_and_reads_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dmp.settings"

            init_settings(path)
            settings = load_settings(path)

            self.assertEqual(settings.get("app.poll_interval_seconds"), "15")
            self.assertTrue(settings.bool("discord.enabled"))

    def test_updates_setting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dmp.settings"
            init_settings(path)

            set_setting(path, "plex.enabled", "true")
            settings = load_settings(path)

            self.assertTrue(settings.bool("plex.enabled"))

    def test_redacts_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dmp.settings"
            init_settings(path)
            set_setting(path, "plex.token", "secret-value")

            settings = load_settings(path)

            self.assertEqual(settings.redacted()["plex.token"], "<redacted>")


if __name__ == "__main__":
    unittest.main()
