from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from tube_explore.models import QualityMode


def _to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


_CAMEL_CONFIG = ConfigDict(
    alias_generator=_to_camel,
    populate_by_name=True,
    from_attributes=True,
)


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
    profile: str | None = Field(None, description="Name of an existing profile to use")
    format_str: str | None = Field(None, description="yt-dlp format string override", alias="format")
    convert_preset: str | None = Field(None, description="Name of a conversion preset to apply")
    audio_only: bool = False

    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None


class DownloadPlaylistRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str = Field(..., description="Media playlist URL")
    output_dir: str | None = Field(None, description="Relative subdirectory appended to the profile's download directory")
    download_path_override: str | None = Field(None, alias="downloadPathOverride", description="Absolute path override for the final output destination. Ignores profile's download_directory.")
    profile: str | None = Field(None, description="Name of an existing profile to use")
    range: str | None = Field(None, description="Playlist item range, e.g. 1-5")
    format_str: str | None = Field(None, description="yt-dlp format string override", alias="format")
    convert_preset: str | None = Field(None, description="Name of a conversion preset to apply")
    audio_only: bool = False

    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None


# ── Task ──────────────────────────────────────────────────────


class TaskResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    type: str
    url: str
    params: dict[str, object] = {}
    status: str = "pending"
    created_at: datetime
    error: str | None = None


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


# ── Outbox ────────────────────────────────────────────────────


class OutboxEntry(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    modified_at: datetime = Field(..., description="Last modified timestamp")


# ── Generic ───────────────────────────────────────────────────


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
