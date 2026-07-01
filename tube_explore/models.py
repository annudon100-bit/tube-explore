from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class QualityMode(StrEnum):
    best = "best"
    least = "least"
    at_most = "at_most"
    at_least = "at_least"


class Profile(BaseModel):
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


class ProfileCreate(BaseModel):
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


class ProfileUpdate(BaseModel):
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


class SettingsDict(BaseModel):
    rate_limit: str = ""
    temp_directory: str = ""
    retry_count: int = 3
    socket_timeout: int = 30


class TaskInfo(BaseModel):
    id: str
    type: str
    url: str
    params: dict[str, object] = {}
    status: str = "pending"
    created_at: datetime
    error: str | None = None
