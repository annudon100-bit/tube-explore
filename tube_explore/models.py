from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FileProgress(BaseModel):
    index: int
    title: str | None = None
    percent: float = 0.0
    speed: str | None = None
    eta: str | None = None
    status: str = "pending"
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    channel: str | None = None
    duration: int | None = None
    format_info: str | None = None


class QualityMode(StrEnum):
    best = "best"
    least = "least"
    at_most = "at_most"
    at_least = "at_least"


class AudioFormat(StrEnum):
    best = "best"
    aac = "aac"
    alac = "alac"
    flac = "flac"
    m4a = "m4a"
    mp3 = "mp3"
    opus = "opus"
    vorbis = "vorbis"
    wav = "wav"


class RemuxTarget(StrEnum):
    mp4 = "mp4"
    mkv = "mkv"
    webm = "webm"
    mov = "mov"
    avi = "avi"
    flv = "flv"


class FormatType(StrEnum):
    video_audio = "video+audio"
    video_only = "video-only"
    audio_only = "audio-only"


class CodecPreference(StrEnum):
    any = "any"
    h264 = "h264"
    h265 = "h265"
    vp9 = "vp9"
    av1 = "av1"


SEED_PROFILES: list[dict[str, Any]] = [
    {"name": "best-video", "label": "Best available quality with metadata", "download_quality_mode": "best", "embed_metadata": True, "embed_thumbnail": True, "subtitles": False},
    {"name": "1080p", "label": "HD 1080p", "download_quality_mode": "at_most", "download_quality_value": 1080},
    {"name": "720p", "label": "HD 720p", "download_quality_mode": "at_most", "download_quality_value": 720},
    {"name": "4k", "label": "Ultra HD 4K", "download_quality_mode": "at_most", "download_quality_value": 2160},
    {"name": "audio-best", "label": "Best quality audio only", "format_type": "audio-only"},
    {"name": "audio-mp3", "label": "MP3 audio", "format_type": "audio-only", "audio_format": "mp3", "audio_quality": "320K"},
    {"name": "smallest", "label": "Smallest file size", "download_quality_mode": "least"},
]


class Profile(BaseModel):
    id: int
    name: str
    label: str = ""
    download_directory: str = ""
    download_format: str | None = None
    download_quality_mode: QualityMode = QualityMode.best
    download_quality_value: int | None = None
    format_type: FormatType = FormatType.video_audio
    codec_preference: CodecPreference = CodecPreference.any
    container_preference: str | None = None
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


class ProfileCreate(BaseModel):
    name: str = Field(..., description="Unique profile name")
    label: str | None = None
    download_directory: str | None = None
    download_format: str | None = None
    download_quality_mode: QualityMode = QualityMode.best
    download_quality_value: int | None = None
    format_type: FormatType = FormatType.video_audio
    codec_preference: CodecPreference = CodecPreference.any
    container_preference: str | None = None
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


class ProfileUpdate(BaseModel):
    name: str | None = None
    label: str | None = None
    download_directory: str | None = None
    download_format: str | None = None
    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    format_type: FormatType | None = None
    codec_preference: CodecPreference | None = None
    container_preference: str | None = None
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


class SettingsDict(BaseModel):
    rate_limit: str = ""
    temp_directory: str = ""
    retry_count: int = 3
    socket_timeout: int = 30
    max_parallel_downloads: int = 2


class TaskInfo(BaseModel):
    id: str
    type: str
    url: str
    params: dict[str, object] = {}
    status: str = "pending"
    progress_percent: int = 0
    file_progress: list[dict[str, object]] = []
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: Any = None

    progress_step: str | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: str | None = None
    eta: str | None = None
    elapsed: int | None = None
    thumbnail_path: str | None = None
    title: str | None = None
    channel: str | None = None
    duration: int | None = None
    format_info: list[dict] | None = None
    current_index: int | None = None
    total_items: int | None = None
    integration: str | None = None
    integration_meta: dict[str, object] | None = None


# ── Radarr models ──────────────────────────────────────────────


class RadarrInstance(BaseModel):
    id: str
    name: str
    base_url: str
    api_key_encrypted: str
    tube_write_path: str
    radarr_import_path: str
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str = "move"
    enabled: bool = True
    is_default: bool = False
    last_test_status: str | None = None
    last_test_message: str | None = None
    last_test_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_message: str | None = None
    last_sync_at: datetime | None = None
    radarr_version: str | None = None
    created_at: datetime
    updated_at: datetime


class RadarrInstanceCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    tube_write_path: str
    radarr_import_path: str
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str = "move"
    enabled: bool = True
    is_default: bool = False


class RadarrInstanceUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    tube_write_path: str | None = None
    radarr_import_path: str | None = None
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class RadarrInstanceStats(BaseModel):
    radarr_instance_id: str
    missing_count: int = 0
    monitored_count: int = 0
    unmonitored_missing_count: int = 0
    root_folder_count: int = 0
    queue_count: int = 0
    imports_24h: int = 0
    last_sync_at: datetime | None = None
    updated_at: datetime


class RadarrMissingMovieCache(BaseModel):
    radarr_instance_id: str
    movie_id: int
    title: str
    year: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    monitored: bool | None = None
    has_file: bool | None = None
    quality_profile_id: int | None = None
    quality_profile_name: str | None = None
    root_folder_path: str | None = None
    movie_path: str | None = None
    poster_url: str | None = None
    overview: str | None = None
    cached_at: datetime


class RadarrDownloadLink(BaseModel):
    id: str
    task_id: str
    radarr_instance_id: str
    radarr_movie_id: int
    title: str
    year: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    source_url: str
    local_staging_dir: str
    radarr_staging_dir: str
    local_final_file_path: str | None = None
    radarr_final_file_path: str | None = None
    created_at: datetime
    updated_at: datetime


class RadarrImportAttempt(BaseModel):
    id: str
    task_id: str
    radarr_instance_id: str
    radarr_movie_id: int
    local_file_path: str | None = None
    radarr_file_path: str | None = None
    status: str
    import_mode: str
    radarr_command_id: str | None = None
    radarr_movie_file_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
