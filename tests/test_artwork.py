from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dis_music_presence.artwork import ArtworkManager, UploadedArtwork
from dis_music_presence.models import ActivityKind, MediaActivity, MediaType
from dis_music_presence.settings import DEFAULT_SETTINGS, Settings


def _settings(**overrides: str) -> Settings:
    values = dict(DEFAULT_SETTINGS)
    values.update(overrides)
    return Settings(path=Path("dmp.settings"), values=values)


def _activity() -> MediaActivity:
    return MediaActivity(
        kind=ActivityKind.LISTENING,
        source="Apple Music",
        media_type=MediaType.MUSIC,
        title="Song",
        artist="Artist",
        album="Album",
    )


class FakeFilebinClient:
    def __init__(self) -> None:
        self.uploads: list[dict[str, object]] = []
        self.deletes: list[UploadedArtwork] = []

    def upload(self, **kwargs: object) -> UploadedArtwork:
        self.uploads.append(kwargs)
        return UploadedArtwork(
            image_url=f"https://filebin.test/{kwargs['bin_name']}/{kwargs['filename']}",
            image_text=str(kwargs["image_text"]),
            bin_name=str(kwargs["bin_name"]),
            filename=str(kwargs["filename"]),
            sha256=str(kwargs["sha256"]),
            delete_bin=bool(kwargs["delete_bin"]),
        )

    def delete(self, upload: UploadedArtwork) -> None:
        self.deletes.append(upload)


class ArtworkManagerTests(unittest.TestCase):
    def test_custom_url_artwork(self) -> None:
        manager = ArtworkManager(
            _settings(
                **{
                    "artwork.provider": "custom_url",
                    "artwork.custom_url": "https://example.test/art.png",
                }
            )
        )

        artwork = manager.resolve(_activity())

        self.assertIsNotNone(artwork)
        self.assertEqual(artwork.image_url, "https://example.test/art.png")
        self.assertEqual(artwork.image_text, "Album - Artist")

    def test_custom_url_does_not_validate_unused_filebin_settings(self) -> None:
        manager = ArtworkManager(
            _settings(
                **{
                    "artwork.provider": "custom_url",
                    "artwork.custom_url": "https://example.test/art.png",
                    "artwork.filebin.base_url": "not-a-url",
                }
            )
        )

        artwork = manager.resolve(_activity())

        self.assertEqual(artwork.image_url, "https://example.test/art.png")

    def test_filebin_upload_reuses_same_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cover.png"
            path.write_bytes(b"png-bytes")
            fake = FakeFilebinClient()
            manager = ArtworkManager(
                _settings(
                    **{
                        "artwork.provider": "filebin",
                        "artwork.filebin.path": str(path),
                    }
                ),
                filebin_client=fake,
            )

            first = manager.resolve(_activity())
            second = manager.resolve(_activity())

            self.assertEqual(first, second)
            self.assertEqual(len(fake.uploads), 1)
            self.assertTrue(fake.uploads[0]["delete_bin"])

    def test_filebin_cleanup_deletes_uploaded_artwork(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cover.jpg"
            path.write_bytes(b"jpg-bytes")
            fake = FakeFilebinClient()
            manager = ArtworkManager(
                _settings(
                    **{
                        "artwork.provider": "filebin",
                        "artwork.filebin.path": str(path),
                        "artwork.filebin.bin": "custom-bin",
                    }
                ),
                filebin_client=fake,
            )

            manager.resolve(_activity())
            manager.cleanup()

            self.assertEqual(len(fake.deletes), 1)
            self.assertFalse(fake.deletes[0].delete_bin)

    def test_dry_run_does_not_upload_filebin_artwork(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cover.webp"
            path.write_bytes(b"webp-bytes")
            fake = FakeFilebinClient()
            manager = ArtworkManager(
                _settings(
                    **{
                        "artwork.provider": "filebin",
                        "artwork.filebin.path": str(path),
                    }
                ),
                filebin_client=fake,
                allow_upload=False,
            )

            artwork = manager.resolve(_activity())

            self.assertIsNone(artwork)
            self.assertEqual(fake.uploads, [])


if __name__ == "__main__":
    unittest.main()
