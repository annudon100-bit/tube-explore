from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tube_explore.models import AudioFormat, FormatType, QualityMode
from tube_explore.schemas import _to_camel

_CAMEL_CONFIG = ConfigDict(
    alias_generator=_to_camel,
    populate_by_name=True,
    from_attributes=True,
)

ArrKind = Literal["radarr", "sonarr"]


class ArrInstanceResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    name: str
    base_url: str
    kind: ArrKind = "radarr"
    api_key_preview: str = Field(..., description="First 8 chars of API key")
    tube_write_path: str
    arr_import_path: str
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str = "move"
    enabled: bool = True
    is_default: bool = False
    status: str = "unknown"
    health_message: str | None = None
    arr_version: str | None = None
    last_sync_at: str | None = None
    last_test_at: str | None = None
    created_at: str
    updated_at: str


class ArrInstanceUpsertRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str = Field(..., min_length=1, max_length=128)
    base_url: str = Field(..., pattern=r"^https?://")
    kind: ArrKind = "radarr"
    api_key: str | None = Field(None, min_length=1)
    tube_write_path: str = Field(..., min_length=1)
    arr_import_path: str = Field(..., min_length=1)
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str = "move"
    enabled: bool = True


class ArrInstanceTestRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    base_url: str | None = None
    api_key: str | None = None
    tube_write_path: str | None = None


class ArrInstanceTestResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    ok: bool
    can_connect: bool = False
    api_key_valid: bool = False
    tube_write_path_writable: bool = False
    root_folders_loaded: bool = False
    arr_import_path_visible: bool | None = None
    arr_version: str | None = None
    warnings: list[str] = []
    errors: list[str] = []


class ArrSummaryResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    total_instances: int
    active_connections: int
    missing_items: int
    monitored_items: int
    imports_24h: int
    last_sync_at: str | None = None
    instance_statuses: dict[str, int] = {}


class ArrMissingItem(BaseModel):
    model_config = _CAMEL_CONFIG

    instance_id: str
    item_id: int
    kind: ArrKind = "radarr"
    title: str
    year: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    tvdb_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    series_id: int | None = None
    series_title: str | None = None
    monitored: bool | None = None
    has_file: bool | None = None
    quality_profile_id: int | None = None
    quality_profile_name: str | None = None
    root_folder_path: str | None = None
    item_path: str | None = None
    poster_url: str | None = None
    overview: str | None = None
    arr_url: str | None = None
    local_workflow_status: str | None = None
    linked_task_id: str | None = None


class ArrMissingItemListResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    items: list[ArrMissingItem]
    total: int
    instance: dict | None = None


class ArrDownloadRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    url: str = Field(..., pattern=r"^https?://\S+")
    instance_id: str | None = None
    item_id: int | None = None
    kind: ArrKind = "radarr"
    item_title: str | None = None
    item_year: int | None = None
    profile_id: str | None = None
    download_quality_mode: QualityMode | None = None
    download_quality_value: int | None = None
    download_format: str | None = None
    format_type: FormatType | None = None
    remux_to: str | None = None
    embed_metadata: bool | None = None
    embed_thumbnail: bool | None = None
    subtitles: bool | None = None
    subtitle_langs: str | None = None


class ArrTaskIntegrationResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    task_id: str
    arr_instance_id: str
    arr_instance_name: str
    arr_item_id: int
    kind: ArrKind = "radarr"
    title: str
    year: int | None = None
    download_status: str
    import_status: str
    import_mode: str = "move"
    local_file_path: str | None = None
    arr_file_path: str | None = None
    arr_url: str | None = None
    command_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ArrRootFolder(BaseModel):
    model_config = _CAMEL_CONFIG

    id: int
    path: str
    accessible: bool = True
    free_space: int | None = None


class ArrQualityProfile(BaseModel):
    model_config = _CAMEL_CONFIG

    id: int
    name: str


class ArrQueueItem(BaseModel):
    model_config = _CAMEL_CONFIG

    item_id: int
    item_title: str
    status: str
    size: int | None = None
    progress: float | None = None


class TaskIntegration(BaseModel):
    model_config = _CAMEL_CONFIG

    type: str = "radarr"
    instance_id: str
    instance_name: str
    item_id: int | None = None
    item_title: str | None = None
    item_year: int | None = None
    import_status: str = "none"
    import_mode: str | None = None
    import_error: str | None = None
    arr_path: str | None = None
    local_path: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    series_id: int | None = None
    series_title: str | None = None


class SonarrSeries(BaseModel):
    model_config = _CAMEL_CONFIG

    id: int
    title: str
    year: int | None = None
    tvdb_id: int | None = None
    imdb_id: str | None = None
    images: list[dict] | None = None
    overview: str | None = None
    monitored: bool = False
    season_count: int | None = None
    episode_count: int | None = None
    status: str | None = None
    network: str | None = None
    path: str | None = None
    quality_profile_id: int | None = None
    root_folder_path: str | None = None


class SonarrEpisode(BaseModel):
    model_config = _CAMEL_CONFIG

    id: int
    series_id: int
    episode_number: int
    season_number: int
    title: str
    overview: str | None = None
    air_date: str | None = None
    monitored: bool = False
    has_file: bool = False
    series_title: str | None = None
    images: list[dict] | None = None


# ── Sonarr Playlist Mapping ─────────────────────────────────────


class PlaylistInspectRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    series_id: int
    season_number: int | None = None
    playlist_url: str = Field(..., pattern=r"^https?://\S+")


class PlaylistEntryInfo(BaseModel):
    model_config = _CAMEL_CONFIG

    index: int
    title: str
    url: str
    duration: int | None = None
    thumbnail: str | None = None


class PlaylistInspectResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    entries: list[PlaylistEntryInfo]
    episodes: list[dict] = []
    series_title: str | None = None


class PlaylistMappingItemData(BaseModel):
    model_config = _CAMEL_CONFIG

    playlist_index: int
    episode_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str = ""
    video_title: str = ""
    video_url: str = ""
    video_duration: int | None = None
    action: Literal["download", "skip"] = "download"
    confidence: Literal["high", "medium", "low", "none", "manual"] = "none"


class CreatePlaylistMappingRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str = Field(..., min_length=1, max_length=256)
    series_id: int
    season_number: int | None = None
    playlist_url: str = Field(..., pattern=r"^https?://\S+")
    quality_profile_id: int | None = None
    root_folder_path: str | None = None
    auto_download: bool = False
    items: list[PlaylistMappingItemData] = []


class UpdatePlaylistMappingRequest(BaseModel):
    model_config = _CAMEL_CONFIG

    name: str | None = None
    quality_profile_id: int | None = None
    root_folder_path: str | None = None
    auto_download: bool | None = None
    status: Literal["draft", "ready", "cancelled"] | None = None
    items: list[PlaylistMappingItemData] | None = None


class PlaylistMappingItemResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    mapping_id: str
    playlist_index: int
    video_title: str
    video_url: str
    video_duration: int | None = None
    episode_id: int | None = None
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str = ""
    action: str = "download"
    confidence: str = "none"
    status: str = "pending"
    download_task_id: str | None = None
    created_at: str
    updated_at: str


class PlaylistMappingResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    name: str
    arr_instance_id: str
    series_id: int
    series_title: str = ""
    season_number: int | None = None
    playlist_url: str
    status: str = "draft"
    auto_download: bool = False
    quality_profile_id: int | None = None
    root_folder_path: str | None = None
    items: list[PlaylistMappingItemResponse] = []
    created_at: str
    updated_at: str


class PlaylistMappingListResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    mappings: list[PlaylistMappingResponse]
    total: int


class AutoMapResult(BaseModel):
    model_config = _CAMEL_CONFIG

    item_id: str
    playlist_index: int
    episode_id: int | None = None
    episode_label: str = ""
    confidence: str = "none"
    warning: str | None = None


class AutoMapResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    results: list[AutoMapResult]
    mapped_count: int
    total_count: int


class PlaylistDownloadResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    task_id: str
    status: str = "pending"
    status_url: str


# ── Sonarr Playlist Download Job ─────────────────────────────────


class PlaylistDownloadJobResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    mapping_id: str
    task_id: str | None = None
    instance_id: str
    series_id: int
    series_title: str
    season_number: int | None = None
    playlist_url: str
    status: str
    summary: dict = {}
    current_item_id: str | None = None
    error: str | None = None


class PlaylistDownloadItemResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    job_id: str
    playlist_index: int
    source_url: str
    source_title: str
    episode_id: int
    series_id: int
    season_number: int
    episode_number: int
    episode_title: str
    status: str
    confidence: str
    action: str
    download_attempts: int = 0
    import_attempts: int = 0
    local_stage_file: str | None = None
    arr_stage_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class PlaylistDownloadJobEnqueueResponse(BaseModel):
    model_config = _CAMEL_CONFIG

    job_id: str
    task_id: str | None = None
    status: str = "queued"
    status_url: str
