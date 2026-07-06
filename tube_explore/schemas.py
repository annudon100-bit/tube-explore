import os
import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tube_explore.models import AudioFormat, FormatType, QualityMode


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


_CAMEL_CONFIG = ConfigDict(
    alias_generator=_to_camel,
    populate_by_name=True,
    from_attributes=True,
)


def _validate_quality_mode(mode: QualityMode | None, value: int | None) -> None:
    if mode in (QualityMode.at_most, QualityMode.at_least) and value is None:
        raise ValueError(f"Quality value is required when mode is '{mode}'")


# URL validation pattern and format marker for OpenAPI spec
_URL_FORMAT: Any = {"format": "uri"}
_URL_PATTERN = r"^https?://\S+"


# ── Search ────────────────────────────────────────────────────


class SearchResult(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str = Field(..., description="Media video ID")
    title: str | None = None
    url: str = Field(..., json_schema_extra=_URL_FORMAT, description="Full watch URL")
    duration: int | None = None
    channel: str | None = None
    channel_url: str | None = Field(None, validation_alias="channelUrl", json_schema_extra=_URL_FORMAT)
    thumbnail: str | None = None


class SearchResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    query: str = Field(..., min_length=1, description="Search query string")
    count: int
    results: list[SearchResult]


# ── Format / Metadata ─────────────────────────────────────────


class FormatInfo(BaseModel):
    model_config = _CAMEL_CONFIG

    format_id: str = Field(..., description="yt-dlp format identifier")
    ext: str | None = None
    width: int | None = None
    height: int | None = None
    filesize: int | None = None
    vcodec: str | None = None
    acodec: str | None = None
    abr: float | None = None
    vbr: float | None = None
    fps: float | None = None


class MetadataResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    title: str | None = None
    url: str = Field(..., json_schema_extra=_URL_FORMAT)
    duration: int | None = None
    channel: str | None = None
    channel_url: str | None = Field(None, validation_alias="channelUrl", json_schema_extra=_URL_FORMAT)
    thumbnail: str | None = None
    description: str | None = None
    view_count: int | None = Field(None, validation_alias="viewCount")
    like_count: int | None = Field(None, validation_alias="likeCount")
    formats: list[FormatInfo] = []
    best_height: int | None = Field(None, validation_alias="bestHeight")


class PlaylistEntry(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    title: str | None = None
    url: str = Field(..., json_schema_extra=_URL_FORMAT)
    duration: int | None = None
    channel: str | None = None


class PlaylistResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str = Field(..., json_schema_extra=_URL_FORMAT)
    count: int
    total_duration: int = Field(0, validation_alias="totalDuration")
    entries: list[PlaylistEntry]


# ── Download requests ─────────────────────────────────────────


class DownloadVideoRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str = Field(..., pattern=_URL_PATTERN, json_schema_extra=_URL_FORMAT, description="Media video URL")
    output_dir: str | None = Field(None, description="Relative subdirectory appended to the profile's download directory")
    download_path_override: str | None = Field(None, alias="downloadPathOverride", description="Relative subdirectory appended to the profile's download directory. Alternative to outputDir.")
    profile_id: str | None = Field(None, alias="profileId", description="Name of an existing profile to use")
    audio_only: bool = False
    audio_format: AudioFormat | None = None
    audio_quality: str | None = None
    remux_to: str | None = None

    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
    format_type: FormatType | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None

    @model_validator(mode="after")
    def _check_quality_values(self) -> Self:
        if self.download_quality_mode is not None:
            _validate_quality_mode(self.download_quality_mode, self.download_quality_value)
        return self


class DownloadPlaylistRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str = Field(..., pattern=_URL_PATTERN, json_schema_extra=_URL_FORMAT, description="Media playlist URL")
    output_dir: str | None = Field(None, description="Relative subdirectory appended to the profile's download directory")
    download_path_override: str | None = Field(None, alias="downloadPathOverride", description="Overrides all path segments except the download base directory")
    playlist_directory: str | None = Field(None, alias="playlistDirectory", description="Relative subdirectory appended to output dir for playlist grouping")
    include_playlist_dir: bool = Field(True, alias="includePlaylistDir", description="When True, %(playlist_title)s is appended to the output template")
    profile_id: str | None = Field(None, alias="profileId", description="Name of an existing profile to use")
    range: str | None = Field(None, pattern=r"^\d+(-\d+)?$", description="Playlist item range, e.g. 1-5")
    audio_only: bool = False
    audio_format: AudioFormat | None = None
    audio_quality: str | None = None
    remux_to: str | None = None

    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
    format_type: FormatType | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None

    @model_validator(mode="after")
    def _check_quality_values(self) -> Self:
        if self.download_quality_mode is not None:
            _validate_quality_mode(self.download_quality_mode, self.download_quality_value)
        return self


class DownloadTaskCreatedResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    task_id: str = Field(..., description="Task ID for status polling")
    status: Literal["pending"] = Field("pending", description="Initial task status")
    status_url: str = Field(..., description="URL to poll task status")


# ── File type classification ────────────────────────────────────

_FILE_EXT_TYPE_MAP: dict[str, str] = {
    ".mp4": "video", ".webm": "video", ".mkv": "video",
    ".avi": "video", ".mov": "video", ".flv": "video", ".m4v": "video",
    ".mp3": "audio", ".m4a": "audio", ".aac": "audio",
    ".flac": "audio", ".opus": "audio", ".wav": "audio", ".ogg": "audio",
    ".wma": "audio",
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".gif": "image", ".webp": "image", ".bmp": "image", ".svg": "image",
}

_FILE_DETAIL_MAP: dict[str, str] = {
    ".mp4": "Video", ".webm": "Video", ".mkv": "Video",
    ".avi": "Video", ".mov": "Video", ".flv": "Video", ".m4v": "Video",
    ".mp3": "Audio", ".m4a": "Audio", ".aac": "Audio",
    ".flac": "Audio", ".opus": "Audio", ".wav": "Audio", ".ogg": "Audio",
    ".wma": "Audio",
    ".jpg": "Image", ".jpeg": "Image", ".png": "Image",
    ".gif": "Image", ".webp": "Image", ".bmp": "Image", ".svg": "Image",
}


def classify_file_extension(filepath: str) -> str:
    _, ext = os.path.splitext(filepath)
    return ext.lower() if ext else ""


def classify_file_type(filepath: str) -> str:
    return _FILE_EXT_TYPE_MAP.get(classify_file_extension(filepath), "other")


def classify_file_format(filepath: str) -> str:
    ext = classify_file_extension(filepath)
    return ext.lstrip(".").upper() if ext else ""


def classify_file_detail(filepath: str) -> str:
    return _FILE_DETAIL_MAP.get(classify_file_extension(filepath), "File")


# ── File Progress ──────────────────────────────────────────────


class FileProgress(BaseModel):
    model_config = _CAMEL_CONFIG

    index: int
    title: str | None = None
    percent: float = 0.0
    speed: str | None = None
    eta: str | None = None
    status: str = "pending"
    downloaded_bytes: int | None = Field(None, validation_alias="downloadedBytes")
    total_bytes: int | None = Field(None, validation_alias="totalBytes")
    channel: str | None = None
    duration: int | None = None
    format_info: list[FormatInfo] | None = Field(None, validation_alias="formatInfo")
    thumbnail_url: str | None = Field(None, validation_alias="thumbnailUrl")


# ── Task ──────────────────────────────────────────────────────


class DownloadedFile(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique file identifier")
    name: str = Field(..., description="File name (relative path from output directory)")
    size: int = Field(..., description="File size in bytes")
    path: str = Field(..., description="Absolute path to the file on disk")
    file_type: str = Field("other", description="File category: video, audio, playlist, image, or other")
    format: str = Field("", description="File format extension (e.g. MP4, MP3)")
    detail: str = Field("File", description="Human-readable detail (e.g. 1080p, Audio)")
    file_extension: str = Field("", description="File extension with dot (e.g. .mp4)")


class FileInfo(DownloadedFile):
    model_config = _CAMEL_CONFIG

    task_id: str = Field(..., description="ID of the download task that produced this file")
    source_url: str | None = Field(None, description="Source media URL", json_schema_extra=_URL_FORMAT)
    created_at: datetime = Field(..., description="When the file was downloaded")
    thumbnail_url: str | None = Field(None, description="URL to the file's thumbnail image")


class FilesListResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    items: list[FileInfo] = Field(..., description="Paginated list of files")
    total: int = Field(..., description="Total number of matching files (across all pages)")


class FileCategory(BaseModel):
    model_config = _CAMEL_CONFIG

    type: str = Field(..., description="File type key (video, audio, playlist, image, other)")
    label: str = Field(..., description="Human-readable category label")
    size: int = Field(..., description="Total size of files in this category in bytes")
    count: int = Field(..., description="Number of files in this category")


class FileStatsResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    total_used: int = Field(..., validation_alias="totalUsed", description="Total storage used in bytes")
    total_capacity: int = Field(..., validation_alias="totalCapacity", description="Total storage capacity in bytes")
    categories: list[FileCategory] = Field(..., description="Breakdown by file type category")


ProgressStep = Literal["fetching_metadata", "preparing", "downloading", "merging", "converting", "finalizing"]


class TaskResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    type: Literal["video", "playlist"]
    url: str
    params: dict[str, object] = {}
    status: Literal["pending", "running", "completed", "failed", "cancelled", "paused"] = "pending"
    progress_percent: int = Field(0, validation_alias="progressPercent")
    progress_step: ProgressStep | None = Field(None, validation_alias="progressStep")
    file_progress: list[FileProgress] | None = Field(None, validation_alias="fileProgress")
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: list[DownloadedFile] | None = None

    downloaded_bytes: int | None = Field(None, validation_alias="downloadedBytes")
    total_bytes: int | None = Field(None, validation_alias="totalBytes")
    speed: str | None = None
    eta: str | None = None
    elapsed: int | None = None
    thumbnail_path: str | None = Field(None, validation_alias="thumbnailPath")
    title: str | None = None
    channel: str | None = None
    duration: int | None = None
    format_info: list[FormatInfo] | None = Field(None, validation_alias="formatInfo")
    current_index: int | None = Field(None, validation_alias="currentIndex")
    total_items: int | None = Field(None, validation_alias="totalItems")


# ── Profile ───────────────────────────────────────────────────


class ProfileCreateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_ -]+$", description="Unique profile name")
    label: str | None = None
    download_directory: str | None = None
    download_format: str | None = None
    download_quality_mode: QualityMode = QualityMode.best
    download_quality_value: int | None = None
    format_type: FormatType = FormatType.video_audio
    audio_format: AudioFormat | None = None
    audio_quality: str | None = None
    remux_to: str | None = None
    include_playlist_dir: bool = True
    filename_template: str | None = None
    playlist_template: str | None = None
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    subtitles: bool = False
    subtitle_langs: str | None = None

    @model_validator(mode="after")
    def _check_quality_values(self) -> Self:
        _validate_quality_mode(self.download_quality_mode, self.download_quality_value)
        return self


class ProfileUpdateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str | None = None
    label: str | None = None
    download_directory: str | None = None
    download_format: str | None = None
    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    format_type: FormatType | None = None
    audio_format: AudioFormat | None = None
    audio_quality: str | None = None
    remux_to: str | None = None
    filename_template: str | None = None
    playlist_template: str | None = None
    include_playlist_dir: bool | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None

    @model_validator(mode="after")
    def _check_quality_values(self) -> Self:
        if self.download_quality_mode is not None:
            _validate_quality_mode(self.download_quality_mode, self.download_quality_value)
        return self


class ProfileResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: int
    name: str
    label: str = ""
    download_directory: str = ""
    download_format: str | None = None
    download_quality_mode: QualityMode = QualityMode.best
    download_quality_value: int | None = None
    format_type: FormatType = FormatType.video_audio
    audio_format: AudioFormat | None = None
    audio_quality: str | None = None
    remux_to: str | None = None
    include_playlist_dir: bool = True
    filename_template: str = "%(title)s [%(id)s].%(ext)s"
    playlist_template: str = "%(playlist_title)s/%(playlist_index)02d - %(title)s [%(id)s].%(ext)s"
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    subtitles: bool = False
    subtitle_langs: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Settings ──────────────────────────────────────────────────


class SettingsResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    rate_limit: str = ""
    temp_directory: str = ""
    retry_count: int = 3
    socket_timeout: int = 30


class SettingsUpdateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    rate_limit: str | None = None
    temp_directory: str | None = None
    retry_count: int | None = None
    socket_timeout: int | None = None


# ── Health ────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    status: str = "ok"
    has_ffmpeg: bool = Field(False, validation_alias="hasFfmpeg")
    ffmpeg_version: str | None = Field(None, validation_alias="ffmpegVersion")
    has_ytdlp: bool = Field(False, validation_alias="hasYtdlp")
    ytdlp_version: str | None = Field(None, validation_alias="ytdlpVersion")
    download_directory_writable: bool = Field(True, validation_alias="downloadDirectoryWritable")
    temp_directory_writable: bool = Field(True, validation_alias="tempDirectoryWritable")
    worker_running: bool = Field(False, validation_alias="workerRunning")
    sse_connected: bool = Field(False, validation_alias="sseConnected")


# ── Generic ───────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    detail: str = Field(..., description="Human-readable error message")


class OkResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    ok: bool = True
