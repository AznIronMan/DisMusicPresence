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
        allow_upload: bool = True,
    ) -> None:
        self.settings = settings
        self._filebin_client = filebin_client
        self.allow_upload = allow_upload
        self._uploaded: UploadedArtwork | None = None
        self._uploaded_path: Path | None = None

    def resolve(self, activity: MediaActivity) -> ArtworkAsset | None:
        provider = self.settings.get("artwork.provider", "none").strip().lower() or "none"
        if provider == "none":
            return None
        if provider == "custom_url":
            return self._custom_url(activity)
        if provider == "filebin":
            return self._filebin(activity)
        raise ArtworkError("artwork.provider must be none, custom_url, or filebin.")

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
                "User-Agent": "DisMusicPresence/0.2.0",
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
        request = urllib.request.Request(url, method="DELETE", headers={"User-Agent": "DisMusicPresence/0.2.0"})
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
