import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from tube_explore import config
from tube_explore.models import Profile, QualityMode, SettingsDict

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


def _resolve_dir(
    profile_dir: str,
    request_dir: str | None,
    settings: SettingsDict,
) -> str:
    if request_dir:
        return request_dir
    if profile_dir:
        return profile_dir
    return os.getcwd()


# ── Download ──────────────────────────────────────────────────


def _download_with_profile(
    url: str,
    output_dir: str,
    profile: Profile,
    settings: SettingsDict,
    is_playlist: bool = False,
    video_range: str | None = None,
    audio_only: bool = False,
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

    if temp_dir and final_dir != temp_dir:
        _move_downloads(dl_dir, final_dir)
        dl_dir = final_dir

    if not HAS_FFMPEG and not audio_only:
        _route_to_outbox(dl_dir, outbox_dir)
        result["outbox"] = outbox_dir

    return result


def _route_to_outbox(src: str, outbox_dir: str) -> None:
    os.makedirs(outbox_dir, exist_ok=True)
    for entry in os.listdir(src):
        s = os.path.join(src, entry)
        d = os.path.join(outbox_dir, entry)
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
                shutil.rmtree(s)
            else:
                shutil.move(s, d)
        except OSError:
            pass


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
) -> dict[str, Any]:
    if profile is None:
        profile = Profile(id=0, name="_adhoc", created_at=datetime.now(), updated_at=datetime.now())
    if settings is None:
        settings = SettingsDict()

    out = _resolve_dir(profile.download_directory, output_dir, settings)
    return _download_with_profile(url, out, profile, settings, is_playlist=False, audio_only=audio_only)


def download_playlist(
    url: str,
    output_dir: str | None = None,
    profile: Profile | None = None,
    settings: SettingsDict | None = None,
    video_range: str | None = None,
    audio_only: bool = False,
) -> dict[str, Any]:
    if profile is None:
        profile = Profile(id=0, name="_adhoc", created_at=datetime.now(), updated_at=datetime.now())
    if settings is None:
        settings = SettingsDict()

    out = _resolve_dir(profile.download_directory, output_dir, settings)
    return _download_with_profile(
        url, out, profile, settings, is_playlist=True, video_range=video_range, audio_only=audio_only
    )
