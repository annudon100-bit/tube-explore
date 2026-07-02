import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tube_explore.models import QualityMode


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


# ── Search ────────────────────────────────────────────────────


class SearchResult(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str = Field(..., description="Media video ID")
    title: str | None = None
    url: str = Field(..., description="Full watch URL")
    duration: int | None = None
    channel: str | None = None
    channel_url: str | None = Field(None, validation_alias="channelUrl")
    thumbnail: str | None = None


class SearchResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    query: str
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
    url: str
    duration: int | None = None
    channel: str | None = None
    channel_url: str | None = Field(None, validation_alias="channelUrl")
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
    url: str
    duration: int | None = None
    channel: str | None = None


class PlaylistResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str
    count: int
    total_duration: int = Field(0, validation_alias="totalDuration")
    entries: list[PlaylistEntry]


# ── Download requests ─────────────────────────────────────────


class DownloadVideoRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str = Field(..., description="Media video URL")
    output_dir: str | None = Field(None, description="Relative subdirectory appended to the profile's download directory")
    download_path_override: str | None = Field(None, alias="downloadPathOverride", description="Absolute path override for the final output destination. Ignores profile's download_directory.")
    profile_id: str | None = Field(None, alias="profileId", description="Name of an existing profile to use")
    convert_preset: str | None = Field(None, description="Name of a conversion preset to apply")
    audio_only: bool = False

    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
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

    url: str = Field(..., description="Media playlist URL")
    output_dir: str | None = Field(None, description="Relative subdirectory appended to the profile's download directory")
    download_path_override: str | None = Field(None, alias="downloadPathOverride", description="Absolute path override for the final output destination. Ignores profile's download_directory.")
    profile_id: str | None = Field(None, alias="profileId", description="Name of an existing profile to use")
    range: str | None = Field(None, description="Playlist item range, e.g. 1-5")
    convert_preset: str | None = Field(None, description="Name of a conversion preset to apply")
    audio_only: bool = False

    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
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
    stream_url: str = Field(..., description="URL to stream task status updates via SSE")


# ── Task ──────────────────────────────────────────────────────


class DownloadedFile(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique file identifier")
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    path: str = Field(..., description="Absolute path to the file on disk")


class FileInfo(DownloadedFile):
    model_config = _CAMEL_CONFIG

    task_id: str = Field(..., description="ID of the download task that produced this file")
    source_url: str | None = Field(None, description="Source media URL")
    created_at: datetime = Field(..., description="When the file was downloaded")


class TaskResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    type: Literal["video", "playlist"]
    url: str
    params: dict[str, object] = {}
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    progress_percent: int = Field(0, validation_alias="progressPercent")
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: list[DownloadedFile] | None = None


class TaskResultResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    task_id: str = Field(..., description="Task ID")
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = Field(..., description="Task status")
    files: list[DownloadedFile] = Field(default_factory=list, description="List of downloaded files")


# ── Profile ───────────────────────────────────────────────────


class ProfileCreateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str = Field(..., description="Unique profile name")
    label: str | None = None
    download_directory: str | None = None
    download_format: str | None = None
    download_quality_mode: QualityMode = QualityMode.best
    download_quality_value: int | None = None
    convert_preset: str | None = None
    convert_format: str | None = None
    convert_quality_mode: QualityMode = QualityMode.best
    convert_quality_value: int | None = None
    filename_template: str | None = None
    playlist_template: str | None = None
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    subtitles: bool = False
    subtitle_langs: str | None = None

    @model_validator(mode="after")
    def _check_quality_values(self) -> Self:
        _validate_quality_mode(self.download_quality_mode, self.download_quality_value)
        _validate_quality_mode(self.convert_quality_mode, self.convert_quality_value)
        return self


class ProfileUpdateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str | None = None
    label: str | None = None
    download_directory: str | None = None
    download_format: str | None = None
    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    convert_preset: str | None = None
    convert_format: str | None = None
    convert_quality_mode: QualityMode | None = None
    convert_quality_value: int | None = None
    filename_template: str | None = None
    playlist_template: str | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None

    @model_validator(mode="after")
    def _check_quality_values(self) -> Self:
        if self.download_quality_mode is not None:
            _validate_quality_mode(self.download_quality_mode, self.download_quality_value)
        if self.convert_quality_mode is not None:
            _validate_quality_mode(self.convert_quality_mode, self.convert_quality_value)
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
    convert_preset: str | None = None
    convert_format: str | None = None
    convert_quality_mode: QualityMode = QualityMode.best
    convert_quality_value: int | None = None
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


# ── Outbox ────────────────────────────────────────────────────


class OutboxEntry(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str = Field(..., description="Unique file identifier")
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    media_url: str | None = Field(None, description="Source media URL")
    task_id: str | None = Field(None, description="Download task ID")
    quality_mode: str | None = Field(None, description="Quality mode used for download")
    quality_value: int | None = Field(None, description="Quality value used for download")
    convert_preset: str | None = Field(None, description="Conversion preset attempted")
    status: Literal["pending", "processing", "completed", "failed"] = Field("pending", description="Processing status (pending, processing, completed, failed)")
    error: str | None = Field(None, description="Error message if processing failed")
    created_at: datetime = Field(..., description="When the file was added to outbox")
    updated_at: datetime | None = Field(None, description="When the record was last updated")


class OutboxProcessRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    preset: str = Field(..., description="Conversion preset name to apply")
    download_directory: str | None = Field(None, alias="downloadDirectory", description="Directory to place the converted file. Defaults to current working directory.")


# ── Generic ───────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    detail: str = Field(..., description="Human-readable error message")


class OkResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    ok: bool = True


# ── Conversion Presets ───────────────────────────────────────


class ConversionPresetCreateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str = Field(..., description="Unique preset name")
    label: str | None = None
    container: str = Field(..., description="Output container (mp4, mkv, webm, mp3, flac)")
    video_codec: str | None = Field(None, description="Video codec (h264, hevc, av1, vp9)")
    video_bitrate: str | None = Field(None, description="Video bitrate (e.g. 5M)")
    video_fps: float | None = Field(None, description="Video framerate")
    video_preset: str | None = Field(None, description="ffmpeg encoding preset (slow, medium, fast)")
    video_pixfmt: str | None = Field(None, description="Pixel format (yuv420p, yuv444p10le)")
    audio_codec: str | None = Field(None, description="Audio codec (aac, mp3, opus, flac)")
    audio_bitrate: str | None = Field(None, description="Audio bitrate (e.g. 128k)")
    audio_samplerate: int | None = Field(None, description="Audio sample rate in Hz")
    audio_channels: int | None = Field(None, description="Number of audio channels")
    max_width: int | None = Field(None, description="Max output width (pixels)")
    max_height: int | None = Field(None, description="Max output height (pixels)")
    output_ext: str = Field(..., description="Output file extension")


class ConversionPresetUpdateRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str | None = None
    label: str | None = None
    container: str | None = None
    video_codec: str | None = None
    video_bitrate: str | None = None
    video_fps: float | None = None
    video_preset: str | None = None
    video_pixfmt: str | None = None
    audio_codec: str | None = None
    audio_bitrate: str | None = None
    audio_samplerate: int | None = None
    audio_channels: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    output_ext: str | None = None


class ConversionPresetResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: int
    name: str
    label: str = ""
    container: str
    video_codec: str | None = None
    video_bitrate: str | None = None
    video_fps: float | None = None
    video_preset: str | None = None
    video_pixfmt: str | None = None
    audio_codec: str | None = None
    audio_bitrate: str | None = None
    audio_samplerate: int | None = None
    audio_channels: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    output_ext: str
    created_at: datetime
    updated_at: datetime
