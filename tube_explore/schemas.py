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

    id: str = Field(..., description="YouTube video ID")
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

    url: str = Field(..., description="YouTube video URL")
    output_dir: str | None = Field(None, description="Output directory")
    profile: str | None = Field(None, description="Name of an existing profile to use")
    format_str: str | None = Field(None, description="yt-dlp format string override", alias="format")
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

    url: str = Field(..., description="YouTube playlist URL")
    output_dir: str | None = Field(None, description="Output directory")
    profile: str | None = Field(None, description="Name of an existing profile to use")
    range: str | None = Field(None, description="Playlist item range, e.g. 1-5")
    format_str: str | None = Field(None, description="yt-dlp format string override", alias="format")
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


# ── Generic ───────────────────────────────────────────────────


class OkResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    ok: bool = True
