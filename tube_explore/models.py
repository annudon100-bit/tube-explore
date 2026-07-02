from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QualityMode(StrEnum):
    best = "best"
    least = "least"
    at_most = "at_most"
    at_least = "at_least"


class Container(StrEnum):
    mp4 = "mp4"
    mkv = "mkv"
    webm = "webm"
    mp3 = "mp3"
    flac = "flac"
    m4a = "m4a"
    opus = "opus"
    wav = "wav"
    mov = "mov"
    avi = "avi"


class VideoCodec(StrEnum):
    h264 = "h264"
    hevc = "hevc"
    av1 = "av1"
    vp9 = "vp9"


class AudioCodec(StrEnum):
    aac = "aac"
    mp3 = "mp3"
    opus = "opus"
    flac = "flac"
    vorbis = "vorbis"


class OutputExt(StrEnum):
    mp4 = "mp4"
    mkv = "mkv"
    webm = "webm"
    mp3 = "mp3"
    m4a = "m4a"
    flac = "flac"
    opus = "opus"
    wav = "wav"
    mov = "mov"
    avi = "avi"


class ConversionPreset(BaseModel):
    id: int
    name: str
    label: str = ""
    container: Container
    video_codec: VideoCodec | None = None
    video_bitrate: str | None = None
    video_fps: float | None = None
    video_preset: str | None = None
    video_pixfmt: str | None = None
    audio_codec: AudioCodec | None = None
    audio_bitrate: str | None = None
    audio_samplerate: int | None = None
    audio_channels: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    output_ext: OutputExt
    created_at: datetime
    updated_at: datetime


class ConversionPresetCreate(BaseModel):
    name: str = Field(..., description="Unique preset name")
    label: str | None = None
    container: Container = Field(..., description="Output container")
    video_codec: VideoCodec | None = Field(None, description="Video codec")
    video_bitrate: str | None = Field(None, description="Video bitrate (e.g. 5M, 10M)")
    video_fps: float | None = Field(None, description="Video framerate")
    video_preset: str | None = Field(None, description="ffmpeg encoding preset (slow, medium, fast)")
    video_pixfmt: str | None = Field(None, description="Pixel format (yuv420p, yuv444p10le)")
    audio_codec: AudioCodec | None = Field(None, description="Audio codec")
    audio_bitrate: str | None = Field(None, description="Audio bitrate (e.g. 128k, 320k)")
    audio_samplerate: int | None = Field(None, description="Audio sample rate in Hz")
    audio_channels: int | None = Field(None, description="Number of audio channels")
    max_width: int | None = Field(None, description="Max output width (pixels)")
    max_height: int | None = Field(None, description="Max output height (pixels)")
    output_ext: OutputExt = Field(..., description="Output file extension")


class ConversionPresetUpdate(BaseModel):
    name: str | None = None
    label: str | None = None
    container: Container | None = None
    video_codec: VideoCodec | None = None
    video_bitrate: str | None = None
    video_fps: float | None = None
    video_preset: str | None = None
    video_pixfmt: str | None = None
    audio_codec: AudioCodec | None = None
    audio_bitrate: str | None = None
    audio_samplerate: int | None = None
    audio_channels: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    output_ext: OutputExt | None = None


SEED_PRESETS: list[dict[str, Any]] = [
    {"name": "MP4 4K", "label": "H.264 MP4 up to 2160p", "container": "mp4", "video_codec": "h264", "audio_codec": "aac", "max_height": 2160, "output_ext": "mp4"},
    {"name": "MP4 1080p", "label": "H.264 MP4 up to 1080p", "container": "mp4", "video_codec": "h264", "audio_codec": "aac", "max_height": 1080, "output_ext": "mp4"},
    {"name": "MP4 720p", "label": "H.264 MP4 up to 720p", "container": "mp4", "video_codec": "h264", "audio_codec": "aac", "max_height": 720, "output_ext": "mp4"},
    {"name": "MKV 4K HDR", "label": "HEVC MKV up to 2160p", "container": "mkv", "video_codec": "hevc", "video_pixfmt": "yuv420p10le", "audio_codec": "flac", "max_height": 2160, "output_ext": "mkv"},
    {"name": "MKV 1080p", "label": "HEVC MKV up to 1080p", "container": "mkv", "video_codec": "hevc", "audio_codec": "flac", "max_height": 1080, "output_ext": "mkv"},
    {"name": "WebM VP9 4K", "label": "VP9 WebM up to 2160p", "container": "webm", "video_codec": "vp9", "audio_codec": "opus", "max_height": 2160, "output_ext": "webm"},
    {"name": "WebM VP9 1080p", "label": "VP9 WebM up to 1080p", "container": "webm", "video_codec": "vp9", "audio_codec": "opus", "max_height": 1080, "output_ext": "webm"},
    {"name": "MP3 320kbps", "label": "MP3 320 kbps audio", "container": "mp3", "audio_codec": "mp3", "audio_bitrate": "320k", "output_ext": "mp3"},
    {"name": "MP3 128kbps", "label": "MP3 128 kbps audio", "container": "mp3", "audio_codec": "mp3", "audio_bitrate": "128k", "output_ext": "mp3"},
    {"name": "AAC 256kbps", "label": "AAC 256 kbps audio in M4A", "container": "m4a", "audio_codec": "aac", "audio_bitrate": "256k", "output_ext": "m4a"},
    {"name": "FLAC Lossless", "label": "FLAC lossless audio", "container": "flac", "audio_codec": "flac", "output_ext": "flac"},
    {"name": "Opus 96kbps", "label": "Opus 96 kbps audio", "container": "opus", "audio_codec": "opus", "audio_bitrate": "96k", "output_ext": "opus"},
]


class Profile(BaseModel):
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


class ProfileCreate(BaseModel):
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


class ProfileUpdate(BaseModel):
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
    progress_percent: int = 0
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: Any = None


class OutboxFile(BaseModel):
    id: str
    file_name: str
    file_size: int
    media_url: str | None = None
    task_id: str | None = None
    quality_mode: str | None = None
    quality_value: int | None = None
    convert_preset: str | None = None
    status: str = "pending"
    error: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class OutboxFileCreate(BaseModel):
    id: str
    file_name: str
    file_size: int
    media_url: str | None = None
    task_id: str | None = None
    quality_mode: str | None = None
    quality_value: int | None = None
    convert_preset: str | None = None
    status: str = "pending"
    error: str | None = None
    created_at: datetime
