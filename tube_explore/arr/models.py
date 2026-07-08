from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ArrKind = Literal["radarr", "sonarr"]


class ArrInstance(BaseModel):
    id: str
    name: str
    base_url: str
    api_key_encrypted: str
    kind: ArrKind = "radarr"
    tube_write_path: str
    arr_import_path: str
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
    arr_version: str | None = None
    created_at: datetime
    updated_at: datetime


class ArrInstanceCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    kind: ArrKind = "radarr"
    tube_write_path: str
    arr_import_path: str
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str = "move"
    enabled: bool = True
    is_default: bool = False


class ArrInstanceUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    tube_write_path: str | None = None
    arr_import_path: str | None = None
    host_path_hint: str | None = None
    default_profile_id: str | None = None
    default_quality_profile_id: int | None = None
    default_root_folder_path: str | None = None
    import_mode: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class ArrInstanceStats(BaseModel):
    arr_instance_id: str
    missing_count: int = 0
    monitored_count: int = 0
    unmonitored_missing_count: int = 0
    root_folder_count: int = 0
    queue_count: int = 0
    imports_24h: int = 0
    last_sync_at: datetime | None = None
    updated_at: datetime


class ArrMissingItemCache(BaseModel):
    arr_instance_id: str
    item_id: int
    kind: ArrKind = "radarr"
    title: str
    year: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    tvdb_id: int | None = None
    monitored: bool | None = None
    has_file: bool | None = None
    quality_profile_id: int | None = None
    quality_profile_name: str | None = None
    root_folder_path: str | None = None
    item_path: str | None = None
    poster_url: str | None = None
    overview: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    series_id: int | None = None
    series_title: str | None = None
    cached_at: datetime


class ArrDownloadLink(BaseModel):
    id: str
    task_id: str
    arr_instance_id: str
    arr_item_id: int
    kind: ArrKind = "radarr"
    title: str
    year: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    tvdb_id: int | None = None
    source_url: str
    local_staging_dir: str
    arr_staging_dir: str
    local_final_file_path: str | None = None
    arr_final_file_path: str | None = None
    created_at: datetime
    updated_at: datetime


class ArrImportAttempt(BaseModel):
    id: str
    task_id: str
    arr_instance_id: str
    arr_item_id: int
    kind: ArrKind = "radarr"
    local_file_path: str | None = None
    arr_file_path: str | None = None
    status: str
    import_mode: str
    arr_command_id: str | None = None
    arr_item_file_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ── Sonarr Playlist Download Job Models ──────────────────────────


SONARR_PLAYLIST_JOB_STATUSES = (
    "queued", "running", "paused", "completed",
    "partially_completed", "failed", "cancelled",
)

SONARR_PLAYLIST_ITEM_STATUSES = (
    "queued", "skipped_existing", "skipped_by_user",
    "downloading", "downloaded",
    "staging", "import_requested", "importing", "imported",
    "failed_download", "failed_stage", "failed_import",
    "cancelled",
)

IMPORT_STRATEGIES = ("manual_import", "DownloadedEpisodesScan")


class SonarrPlaylistDownloadJob(BaseModel):
    id: str
    mapping_id: str
    arr_instance_id: str
    series_id: int
    series_title: str
    season_number: int | None = None
    playlist_url: str
    status: str = "queued"
    total_items: int = 0
    queued_items: int = 0
    skipped_items: int = 0
    downloaded_items: int = 0
    imported_items: int = 0
    failed_items: int = 0
    current_item_id: str | None = None
    task_id: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class SonarrPlaylistDownloadItem(BaseModel):
    id: str
    job_id: str
    mapping_item_id: str
    playlist_index: int
    source_url: str
    source_title: str
    episode_id: int
    series_id: int
    season_number: int
    episode_number: int
    absolute_episode_number: int | None = None
    episode_title: str
    status: str
    confidence: str
    action: str
    download_attempts: int = 0
    import_attempts: int = 0
    work_dir: str | None = None
    local_download_path: str | None = None
    local_stage_dir: str | None = None
    local_stage_file: str | None = None
    arr_stage_path: str | None = None
    sonarr_command_id: int | None = None
    sonarr_episode_file_id: int | None = None
    sonarr_episode_file_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    downloaded_at: datetime | None = None
    imported_at: datetime | None = None


class SonarrPlaylistImportAttempt(BaseModel):
    id: str
    item_id: str
    job_id: str
    attempt_number: int
    local_stage_file: str
    arr_stage_path: str
    import_strategy: str
    sonarr_command_id: int | None = None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
