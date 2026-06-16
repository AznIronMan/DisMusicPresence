from __future__ import annotations

import hashlib
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from .models import MediaActivity
from .settings import Settings


MAX_FILEBIN_UPLOAD_BYTES = 10 * 1024 * 1024
FILEBIN_TIMEOUT_SECONDS = 10
APPLE_CATALOG_TIMEOUT_SECONDS = 5
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class ArtworkError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtworkAsset:
    image_url: str
    image_text: str = ""


@dataclass(frozen=True)
class UploadedArtwork(ArtworkAsset):
    bin_name: str = ""
    filename: str = ""
    sha256: str = ""
    delete_bin: bool = False


class ArtworkManager:
    def __init__(
        self,
        settings: Settings,
        filebin_client: FilebinClient | None = None,
        apple_catalog_client: AppleCatalogClient | None = None,
        allow_upload: bool = True,
    ) -> None:
        self.settings = settings
        self._filebin_client = filebin_client
        self._apple_catalog_client = apple_catalog_client
        self.allow_upload = allow_upload
        self._uploaded: UploadedArtwork | None = None
        self._uploaded_path: Path | None = None
        self._catalog_cache: dict[tuple[str, str, str], ArtworkAsset | None] = {}

    def resolve(self, activity: MediaActivity) -> ArtworkAsset | None:
        provider = self.settings.get("artwork.provider", "none").strip().lower() or "none"
        if provider == "none":
            return None
        if provider == "custom_url":
            return self._custom_url(activity)
        if provider == "apple_catalog":
            return self._apple_catalog(activity)
        if provider == "filebin":
            artwork = self._filebin(activity)
            if artwork is not None:
                return artwork
            return self._apple_catalog(activity)
        raise ArtworkError("artwork.provider must be none, custom_url, apple_catalog, or filebin.")

    def cleanup(self) -> None:
        if self._uploaded is None:
            return
        if self.settings.bool("artwork.filebin.delete_on_shutdown", True):
            self._client().delete(self._uploaded)
        self._uploaded = None
        self._uploaded_path = None

    def _custom_url(self, activity: MediaActivity) -> ArtworkAsset | None:
        url = self.settings.get("artwork.custom_url").strip()
        if not url:
            return None
        _validate_public_url(url)
        return ArtworkAsset(image_url=url, image_text=self._image_text(activity))

    def _filebin(self, activity: MediaActivity) -> ArtworkAsset | None:
        if not self.allow_upload:
            return None
        path_value = self.settings.get("artwork.filebin.path").strip()
        if not path_value:
            return None
        path = Path(path_value).expanduser().resolve()
        if not path.is_file():
            raise ArtworkError(f"Artwork file not found: {path}")

        file_bytes = path.read_bytes()
        if len(file_bytes) > MAX_FILEBIN_UPLOAD_BYTES:
            raise ArtworkError("Artwork file is too large for DisMusicPresence Filebin uploads.")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type not in SUPPORTED_IMAGE_TYPES:
            raise ArtworkError(f"Unsupported artwork image type: {content_type}")

        digest = hashlib.sha256(file_bytes).hexdigest()
        if self._uploaded and self._uploaded_path == path and self._uploaded.sha256 == digest:
            return self._uploaded

        self.cleanup()
        bin_name = self.settings.get("artwork.filebin.bin").strip()
        delete_bin = not bin_name
        if not bin_name:
            bin_name = f"dmp-{uuid.uuid4().hex[:16]}"
        filename = _artwork_filename(path, digest)
        uploaded = self._client().upload(
            bin_name=bin_name,
            filename=filename,
            content=file_bytes,
            content_type=content_type,
            sha256=digest,
            image_text=self._image_text(activity),
            delete_bin=delete_bin,
        )
        self._uploaded = uploaded
        self._uploaded_path = path
        return uploaded

    def _apple_catalog(self, activity: MediaActivity) -> ArtworkAsset | None:
        if not self.settings.bool("artwork.apple_catalog.enabled", True):
            return None
        if activity.source != "Apple Music" or not activity.title:
            return None

        cache_key = (activity.artist.casefold(), activity.album.casefold(), activity.title.casefold())
        if cache_key in self._catalog_cache:
            return self._catalog_cache[cache_key]

        artwork = self._catalog_client().lookup(
            artist=activity.artist,
            album=activity.album,
            title=activity.title,
            country=self.settings.get("artwork.apple_catalog.country", "US"),
            size=self.settings.int("artwork.apple_catalog.size", 600),
            image_text=self._image_text(activity),
        )
        self._catalog_cache[cache_key] = artwork
        return artwork

    def _image_text(self, activity: MediaActivity) -> str:
        configured = self.settings.get("artwork.custom_text").strip()
        if configured:
            return configured
        if activity.album and activity.artist:
            return f"{activity.album} - {activity.artist}"
        return activity.album or activity.title or activity.source

    def _client(self) -> FilebinClient:
        if self._filebin_client is None:
            self._filebin_client = FilebinClient(self.settings.get("artwork.filebin.base_url"))
        return self._filebin_client

    def _catalog_client(self) -> AppleCatalogClient:
        if self._apple_catalog_client is None:
            self._apple_catalog_client = AppleCatalogClient()
        return self._apple_catalog_client


class AppleCatalogClient:
    def __init__(self, base_url: str = "https://itunes.apple.com/search") -> None:
        self.base_url = base_url
        _validate_public_url(base_url)

    def lookup(
        self,
        *,
        artist: str,
        album: str,
        title: str,
        country: str,
        size: int,
        image_text: str,
    ) -> ArtworkAsset | None:
        query = _catalog_query(artist=artist, album=album, title=title, country=country)
        url = f"{self.base_url}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(url, headers={"User-Agent": "DisMusicPresence/0.3.0"})
        try:
            with urllib.request.urlopen(request, timeout=APPLE_CATALOG_TIMEOUT_SECONDS) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise ArtworkError(f"Apple catalog lookup failed with HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ArtworkError(f"Apple catalog lookup failed: {exc.reason}") from exc

        try:
            payload = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ArtworkError(f"Apple catalog returned invalid JSON: {exc}") from exc

        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            return None

        best = _best_catalog_result(results, artist=artist, album=album, title=title)
        if best is None:
            return None
        artwork_url = best.get("artworkUrl100")
        if not isinstance(artwork_url, str) or not artwork_url:
            return None
        return ArtworkAsset(image_url=_resize_apple_artwork_url(artwork_url, size), image_text=image_text)


class FilebinClient:
    def __init__(self, base_url: str = "https://filebin.net") -> None:
        self.base_url = base_url.rstrip("/")
        _validate_public_url(self.base_url)

    def upload(
        self,
        *,
        bin_name: str,
        filename: str,
        content: bytes,
        content_type: str,
        sha256: str,
        image_text: str,
        delete_bin: bool,
    ) -> UploadedArtwork:
        url = self._file_url(bin_name, filename)
        request = urllib.request.Request(
            url,
            data=content,
            method="POST",
            headers={
                "Content-Type": content_type,
                "Content-Length": str(len(content)),
                "Content-SHA256": sha256,
                "User-Agent": "DisMusicPresence/0.3.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=FILEBIN_TIMEOUT_SECONDS) as response:
                body = response.read()
                status = getattr(response, "status", response.getcode())
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise ArtworkError(f"Filebin upload failed with HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ArtworkError(f"Filebin upload failed: {exc.reason}") from exc

        if status != 201:
            raise ArtworkError(f"Filebin upload failed with HTTP {status}.")

        self._validate_upload_response(body)
        return UploadedArtwork(
            image_url=url,
            image_text=image_text,
            bin_name=bin_name,
            filename=filename,
            sha256=sha256,
            delete_bin=delete_bin,
        )

    def delete(self, upload: UploadedArtwork) -> None:
        if upload.delete_bin:
            url = self._bin_url(upload.bin_name)
        else:
            url = self._file_url(upload.bin_name, upload.filename)
        request = urllib.request.Request(url, method="DELETE", headers={"User-Agent": "DisMusicPresence/0.3.0"})
        try:
            with urllib.request.urlopen(request, timeout=FILEBIN_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", response.getcode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise ArtworkError(f"Filebin delete failed with HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ArtworkError(f"Filebin delete failed: {exc.reason}") from exc
        if status not in {200, 404}:
            raise ArtworkError(f"Filebin delete failed with HTTP {status}.")

    def _file_url(self, bin_name: str, filename: str) -> str:
        return f"{self._bin_url(bin_name)}/{urllib.parse.quote(filename)}"

    def _bin_url(self, bin_name: str) -> str:
        return f"{self.base_url}/{urllib.parse.quote(bin_name)}"

    def _validate_upload_response(self, body: bytes) -> None:
        if not body:
            return
        try:
            decoded = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return
        if not isinstance(decoded, dict) or "file" not in decoded:
            raise ArtworkError("Filebin upload returned an unexpected response.")


def _validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ArtworkError(f"Invalid public artwork URL: {url}")


def _artwork_filename(path: Path, digest: str) -> str:
    suffix = path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".img"
    return f"dmp-artwork-{digest[:12]}{suffix}"


def _catalog_query(*, artist: str, album: str, title: str, country: str) -> dict[str, str]:
    terms = " ".join(part for part in [artist, album, title] if part).strip()
    return {
        "term": terms or title,
        "media": "music",
        "entity": "song",
        "limit": "10",
        "country": country or "US",
    }


def _best_catalog_result(
    results: list[object],
    *,
    artist: str,
    album: str,
    title: str,
) -> dict[str, object] | None:
    candidates = [result for result in results if isinstance(result, dict) and result.get("artworkUrl100")]
    if not candidates:
        return None
    best = max(candidates, key=lambda result: _catalog_score(result, artist=artist, album=album, title=title))
    if _catalog_score(best, artist=artist, album=album, title=title) <= 0:
        return None
    return best


def _catalog_score(result: dict[str, object], *, artist: str, album: str, title: str) -> int:
    score = 0
    track_name = str(result.get("trackName") or "")
    artist_name = str(result.get("artistName") or "")
    collection_name = str(result.get("collectionName") or "")
    if _matches(track_name, title):
        score += 4
    if _matches(artist_name, artist):
        score += 3
    if album and _matches(collection_name, album):
        score += 2
    return score


def _matches(left: str, right: str) -> bool:
    if not left or not right:
        return False
    left_norm = _normalize_text(left)
    right_norm = _normalize_text(right)
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().replace("&", "and").split())


def _resize_apple_artwork_url(url: str, size: int) -> str:
    safe_size = max(60, min(size, 3000))
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    filename = path.rsplit("/", 1)[-1]
    if "x" not in filename:
        return url
    parts = filename.split(".")
    if len(parts) < 2:
        return url
    stem = parts[0]
    suffix = ".".join(parts[1:])
    stem_parts = stem.split("x")
    if len(stem_parts) < 2 or not stem_parts[0].isdigit():
        return url
    resized = f"{safe_size}x{safe_size}bb.{suffix}"
    new_path = path.rsplit("/", 1)[0] + "/" + resized
    return urllib.parse.urlunparse(parsed._replace(path=new_path))
