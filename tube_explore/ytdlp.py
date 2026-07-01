import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from contextlib import suppress
from datetime import datetime
from typing import Any

from tube_explore import config, db
from tube_explore.models import ConversionPreset, Profile, QualityMode, SettingsDict

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def ensure_binary() -> str:
    paths = [
        os.path.join(SCRIPT_DIR, "yt-dlp"),
        "/tmp/yt-dlp",
        shutil.which("yt-dlp"),
    ]
    for p in paths:
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    dest = os.path.join(SCRIPT_DIR, "yt-dlp")
    print(f"Downloading yt-dlp to {dest}...", flush=True)
    try:
        urllib.request.urlretrieve(YTDLP_URL, dest)
        os.chmod(dest, 0o755)
        return dest
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"Failed to download yt-dlp: {e}") from e


def _run(args: list[str], timeout: int = 120, capture: bool = True) -> str | None:
    bin_path = ensure_binary()
    cmd = [bin_path, "--no-warnings"] + args
    if capture:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(err)
        return result.stdout
    else:
        subprocess.run(cmd, timeout=timeout)
        return None


# ── Profile → format-string helpers ──────────────────────────


def _build_video_format_str(
    mode: QualityMode,
    value: int | None = None,
    ext: str | None = None,
) -> str:
    if mode == QualityMode.least:
        video = "worstvideo"
        audio = "worstaudio"
        fallback = "worst"
    elif mode == QualityMode.at_most:
        v = value or 1080
        video = f"bestvideo[height<={v}]"
        audio = "bestaudio"
        fallback = f"best[height<={v}]"
    elif mode == QualityMode.at_least:
        v = value or 480
        video = f"bestvideo[height>={v}]"
        audio = "bestaudio"
        fallback = f"best[height>={v}]"
    else:
        video = "bestvideo"
        audio = "bestaudio"
        fallback = "best"

    if ext:
        video += f"[ext={ext}]"
        audio += f"[ext={ext}]"
    return f"{video}+{audio}/{fallback}"


def _build_audio_format_str(mode: QualityMode, ext: str | None = None) -> str:
    if mode == QualityMode.least:
        base = "worstaudio"
        fallback = "worst"
    else:
        base = "bestaudio"
        fallback = "best"
    if ext:
        base += f"[ext={ext}]"
    return f"{base}/{fallback}"


def _build_args(
    output_path: str,
    template: str,
    profile: Profile,
    settings: SettingsDict,
    url: str,
    is_playlist: bool = False,
    audio_only: bool = False,
) -> list[str]:
    if audio_only:
        fmt = _build_audio_format_str(profile.download_quality_mode, profile.download_format)
    else:
        fmt = _build_video_format_str(
            profile.download_quality_mode, profile.download_quality_value, profile.download_format
        )

    args = ["--no-overwrites", "--newline"]
    if is_playlist:
        args.append("--yes-playlist")

    args += ["-f", fmt, "-o", template]
    if not HAS_FFMPEG:
        args += ["--merge-output-format", "mp4"]

    if profile.embed_metadata and HAS_FFMPEG:
        args.append("--embed-metadata")
    if profile.embed_thumbnail and HAS_FFMPEG:
        args.append("--embed-thumbnail")
    if profile.subtitles:
        args.append("--write-subs")
        if profile.subtitle_langs:
            args.append(f"--sub-langs={profile.subtitle_langs}")
        args.append("--embed-subs")

    rate = settings.rate_limit.strip()
    if rate:
        args += ["--limit-rate", rate]

    if settings.socket_timeout:
        args += ["--socket-timeout", str(settings.socket_timeout)]

    args.append(url)
    return args


# ── Conversion engine ─────────────────────────────────────────


def _build_conversion_args(
    input_path: str,
    output_path: str,
    preset: ConversionPreset,
) -> list[str]:
    args = ["-i", input_path]

    if preset.video_codec:
        codec_map = {"h264": "libx264", "hevc": "libx265", "av1": "libaom-av1", "vp9": "libvpx-vp9"}
        args += ["-c:v", codec_map.get(preset.video_codec, preset.video_codec)]

    if preset.video_bitrate:
        args += ["-b:v", preset.video_bitrate]

    if preset.video_fps:
        args += ["-r", str(preset.video_fps)]

    if preset.video_preset:
        args += ["-preset", preset.video_preset]

    if preset.video_pixfmt:
        args += ["-pix_fmt", preset.video_pixfmt]

    if preset.audio_codec:
        codec_map = {"aac": "aac", "mp3": "libmp3lame", "opus": "libopus", "flac": "flac", "vorbis": "libvorbis"}
        args += ["-c:a", codec_map.get(preset.audio_codec, preset.audio_codec)]

    if preset.audio_bitrate:
        args += ["-b:a", preset.audio_bitrate]

    if preset.audio_samplerate:
        args += ["-ar", str(preset.audio_samplerate)]

    if preset.audio_channels:
        args += ["-ac", str(preset.audio_channels)]

    vf_parts: list[str] = []
    if preset.max_width or preset.max_height:
        w = preset.max_width or -1
        h = preset.max_height or -1
        vf_parts.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")

    if vf_parts:
        args += ["-vf", ",".join(vf_parts)]

    args += ["-y", output_path]
    return args


def _run_conversion(dl_dir: str, preset: ConversionPreset) -> str | None:
    if not HAS_FFMPEG:
        return None

    video_exts = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".ts"}
    candidates: list[tuple[str, int]] = []

    for entry in os.listdir(dl_dir):
        path = os.path.join(dl_dir, entry)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext in video_exts:
            candidates.append((path, os.path.getsize(path)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1], reverse=True)
    input_path = candidates[0][0]
    base = os.path.splitext(input_path)[0]
    output_path = f"{base}.{preset.output_ext}"

    args = _build_conversion_args(input_path, output_path, preset)
    cmd = ["ffmpeg"] + args

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        stderr = getattr(e, "stderr", str(e)) or str(e)
        raise RuntimeError(f"Conversion failed: {stderr[:500]}") from e

    for entry in os.listdir(dl_dir):
        path = os.path.join(dl_dir, entry)
        if path == output_path:
            continue
        if os.path.isfile(path) and os.path.splitext(entry)[1].lower() in video_exts | {".opus", ".m4a", ".aac", ".flac", ".mp3", ".wav", ".ogg"}:
            with suppress(OSError):
                os.remove(path)

    return output_path


def _resolve_dir(
    profile_dir: str,
    request_dir: str | None,
) -> str:
    if request_dir:
        return request_dir
    if profile_dir:
        return profile_dir
    return os.getcwd()


def _record_outbox_files(
    filenames: list[str],
    outbox_dir: str,
    media_url: str | None = None,
    task_id: str | None = None,
    quality_mode: str | None = None,
    quality_value: int | None = None,
    convert_preset: str | None = None,
) -> None:
    from datetime import UTC, datetime

    from tube_explore.models import OutboxFileCreate

    now = datetime.now(UTC)
    for name in filenames:
        fpath = os.path.join(outbox_dir, name)
        if not os.path.isfile(fpath):
            continue
        fsize = os.path.getsize(fpath)
        record = OutboxFileCreate(
            id=str(uuid.uuid4()),
            file_name=name,
            file_size=fsize,
            media_url=media_url,
            task_id=task_id,
            quality_mode=quality_mode,
            quality_value=quality_value,
            convert_preset=convert_preset,
            created_at=now,
        )
        db.insert_outbox_file(record)


# ── Download ──────────────────────────────────────────────────


def _download_with_profile(
    url: str,
    output_dir: str,
    profile: Profile,
    settings: SettingsDict,
    is_playlist: bool = False,
    video_range: str | None = None,
    audio_only: bool = False,
    conversion_preset: ConversionPreset | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    temp_dir = settings.temp_directory.strip()
    final_dir = output_dir
    outbox_dir = config.get_outbox_dir()

    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        dl_dir = temp_dir
    else:
        dl_dir = final_dir

    os.makedirs(dl_dir, exist_ok=True)

    if is_playlist:
        template = os.path.join(dl_dir, profile.playlist_template)
    else:
        template = os.path.join(dl_dir, profile.filename_template)

    args = _build_args(output_dir, template, profile, settings, url, is_playlist, audio_only)

    if video_range:
        args.insert(0, f"--playlist-items={video_range}")

    _run(args, capture=False)

    result: dict[str, Any] = {}

    if conversion_preset and HAS_FFMPEG:
        try:
            converted = _run_conversion(dl_dir, conversion_preset)
            if converted:
                result["converted"] = converted
        except RuntimeError:
            outbox_files = _route_to_outbox(dl_dir, outbox_dir)
            result["outbox"] = outbox_dir
            _record_outbox_files(
                outbox_files,
                outbox_dir,
                media_url=url,
                task_id=task_id,
                quality_mode=profile.download_quality_mode.value,
                quality_value=profile.download_quality_value,
                convert_preset=conversion_preset.name if conversion_preset else None,
            )
            return result

    if not HAS_FFMPEG and not audio_only:
        outbox_files = _route_to_outbox(dl_dir, outbox_dir)
        result["outbox"] = outbox_dir
        _record_outbox_files(
            outbox_files,
            outbox_dir,
            media_url=url,
            task_id=task_id,
            quality_mode=profile.download_quality_mode.value,
            quality_value=profile.download_quality_value,
            convert_preset=conversion_preset.name if conversion_preset else None,
        )
        return result

    if dl_dir != final_dir:
        os.makedirs(final_dir, exist_ok=True)
        _move_downloads(dl_dir, final_dir)

    result["files"] = _collect_files(final_dir)
    return result


def _collect_files(directory: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for entry in sorted(os.listdir(directory)):
        path = os.path.join(directory, entry)
        if os.path.isfile(path):
            files.append({
                "name": entry,
                "size": os.path.getsize(path),
                "path": path,
            })
    return files


def _route_to_outbox(src: str, outbox_dir: str) -> list[str]:
    os.makedirs(outbox_dir, exist_ok=True)
    moved: list[str] = []
    for entry in os.listdir(src):
        s = os.path.join(src, entry)
        d = os.path.join(outbox_dir, entry)
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
                shutil.rmtree(s)
            else:
                shutil.move(s, d)
            moved.append(entry)
        except OSError:
            pass
    return moved


def _move_downloads(src: str, dst: str) -> None:
    for entry in os.listdir(src):
        s = os.path.join(src, entry)
        d = os.path.join(dst, entry)
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
                shutil.rmtree(s)
            else:
                shutil.move(s, d)
        except OSError:
            pass


# ── Public API ────────────────────────────────────────────────


def search_videos(query: str, limit: int = 10) -> list[dict[str, Any]]:
    search_query = f"ytsearch{limit}:{query}"
    stdout = _run(["--flat-playlist", "--dump-json", search_query], timeout=30)
    assert stdout is not None
    results: list[dict[str, Any]] = []
    for line in stdout.strip().splitlines():
        if not line:
            continue
        e = json.loads(line)
        results.append(
            {
                "id": e["id"],
                "title": e.get("title"),
                "url": f"https://www.youtube.com/watch?v={e['id']}",
                "duration": e.get("duration"),
                "channel": e.get("channel") or e.get("uploader"),
                "channelUrl": e.get("channel_url") or e.get("uploader_url"),
                "thumbnail": e.get("thumbnail"),
            }
        )
    return results


def get_metadata(url: str) -> dict:
    stdout = _run(["--dump-json", url], timeout=60)
    assert stdout is not None
    info = json.loads(stdout)
    formats = []
    for f in info.get("formats", []):
        formats.append(
            {
                "formatId": f["format_id"],
                "ext": f.get("ext"),
                "width": f.get("width"),
                "height": f.get("height"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "abr": f.get("abr"),
                "vbr": f.get("vbr"),
                "fps": f.get("fps"),
            }
        )
    heights = sorted(set(f["height"] for f in formats if f["height"]), reverse=True)
    return {
        "id": info["id"],
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={info['id']}",
        "duration": info.get("duration"),
        "channel": info.get("channel") or info.get("uploader"),
        "channelUrl": info.get("channel_url") or info.get("uploader_url"),
        "thumbnail": info.get("thumbnail"),
        "description": info.get("description"),
        "viewCount": info.get("view_count"),
        "likeCount": info.get("like_count"),
        "formats": formats,
        "bestHeight": heights[0] if heights else None,
    }


def get_playlist_info(url: str) -> list[dict[str, Any]]:
    stdout = _run(["--flat-playlist", "--dump-json", url], timeout=120)
    assert stdout is not None
    entries: list[dict[str, Any]] = []
    for line in stdout.strip().splitlines():
        if not line:
            continue
        e = json.loads(line)
        entries.append(
            {
                "id": e["id"],
                "title": e.get("title"),
                "url": f"https://www.youtube.com/watch?v={e['id']}",
                "duration": e.get("duration"),
                "channel": e.get("channel") or e.get("uploader"),
            }
        )
    return entries


def download_video(
    url: str,
    output_dir: str | None = None,
    profile: Profile | None = None,
    settings: SettingsDict | None = None,
    audio_only: bool = False,
    conversion_preset: ConversionPreset | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    if profile is None:
        profile = Profile(id=0, name="_adhoc", created_at=datetime.now(), updated_at=datetime.now())
    if settings is None:
        settings = SettingsDict()

    out = _resolve_dir(profile.download_directory, output_dir)
    return _download_with_profile(url, out, profile, settings, is_playlist=False, audio_only=audio_only, conversion_preset=conversion_preset, task_id=task_id)


def download_playlist(
    url: str,
    output_dir: str | None = None,
    profile: Profile | None = None,
    settings: SettingsDict | None = None,
    video_range: str | None = None,
    audio_only: bool = False,
    conversion_preset: ConversionPreset | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    if profile is None:
        profile = Profile(id=0, name="_adhoc", created_at=datetime.now(), updated_at=datetime.now())
    if settings is None:
        settings = SettingsDict()

    out = _resolve_dir(profile.download_directory, output_dir)
    return _download_with_profile(
        url, out, profile, settings, is_playlist=True, video_range=video_range, audio_only=audio_only, conversion_preset=conversion_preset, task_id=task_id
    )
