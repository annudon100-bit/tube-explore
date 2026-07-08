import json
import logging
import os
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from typing import Any

from tube_explore import config, db
from tube_explore.models import AudioFormat, CodecPreference, FormatType, Profile, QualityMode
from tube_explore.schemas import classify_file_extension, classify_file_format, classify_file_type, classify_file_detail

logger = logging.getLogger(__name__)

# Track output file paths per task so cancel can clean up precisely
_task_output_files: dict[str, list[str]] = {}
_task_output_files_lock = threading.Lock()


def _track_output_file(task_id: str, filepath: str) -> None:
    with _task_output_files_lock:
        if task_id not in _task_output_files:
            _task_output_files[task_id] = []
        _task_output_files[task_id].append(filepath)


def _extract_video_id(url: str) -> str | None:
    m = re.search(r'(?:v=|youtu\.be/|/shorts/|/embed/|/v/)([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None


def _get_task_output_files(task_id: str) -> list[str]:
    with _task_output_files_lock:
        return list(_task_output_files.get(task_id, []))


def _clear_task_output_files(task_id: str) -> None:
    with _task_output_files_lock:
        _task_output_files.pop(task_id, None)


def _try_remove(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
            logger.debug("Removed file: %s", path)
    except OSError as e:
        logger.warning("Failed to remove %s: %s", path, e)


# yt-dlp stderr progress regexes
_PLAYLIST_PAT = re.compile(r"\[download\] Downloading (?:video|item) (\d+) of (\d+)")
_PROGRESS_PAT = re.compile(r"\[download\]\s+([\d.]+)%")
_DEST_PAT = re.compile(r"\[download\] (?:Destination:\s+)?(?:temp=|home=)?(/.+)")
_COMPLETE_PAT = re.compile(r"\[download\]\s+100%")
_INFO_PAT = re.compile(r"\[info\] .+ Downloading \d+ format\(s\)")
_MERGER_PAT = re.compile(r'\[Merger\] Merging formats into "(.+?)"')
_EXTRACT_AUDIO_PAT = re.compile(r"\[ExtractAudio\] Destination:")
_REMUX_PAT = re.compile(r"\[VideoRemuxer\] Remuxing")
_DELETE_ORIG_PAT = re.compile(r"Deleting original file")
_PLAYLIST_DL_PAT = re.compile(r"\[download\] Downloading playlist:")
_PLAYLIST_ITEMS_PAT = re.compile(r"Downloading (\d+) items")
_ALREADY_DL_PAT = re.compile(r"\[download\] (.+?) has already been downloaded")
_TOTAL_BYTES_PAT = re.compile(r"of\s+([\d.]+)\s*([KMG]iB)")
_THUMBNAIL_PAT = re.compile(r"\[info\] Writing video thumbnail \d+ to: (?:temp=|home=)?(.+)")

def _extract_title_from_path(filepath: str) -> str:
    """Extract a clean video title from a yt-dlp output path.

    Handles templates like:
      /path/to/01 - Video Title [videoid].ext
      /path/to/Video Title [videoid].f401.ext
    Returns just the video title.
    """
    fn = os.path.basename(filepath)
    name, _ = os.path.splitext(fn)
    # Remove yt-dlp format specifier suffix (e.g. .f401, .f251)
    name = re.sub(r"\.f\d+$", "", name)
    # Remove trailing [videoId]
    name = re.sub(r"\s*\[[^\]]*\]$", "", name)
    # Remove leading playlist index
    name = re.sub(r"^\d+ - ", "", name)
    return name.strip()


# Phase definitions with percentage ranges
PHASES = [
    ("fetching_metadata", 0, 8),
    ("preparing", 8, 14),
    ("downloading", 14, 72),
    ("merging", 72, 84),
    ("converting", 84, 96),
    ("finalizing", 96, 100),
]
PHASE_MAP = {name: (start, end) for name, start, end in PHASES}

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_YTDLP = shutil.which("yt-dlp") is not None or os.path.isfile(os.path.join(SCRIPT_DIR, "yt-dlp"))
THUMBNAIL_DIR = os.path.join(config.get_metadata_dir(), "thumbnails")

# Track running download processes for cancellation
_running_procs: dict[str, subprocess.Popen] = {}
_proc_lock = threading.Lock()

# Track paused tasks so _run knows to suppress RuntimeError on SIGTERM exit
_paused_tasks: set[str] = set()
_paused_lock = threading.Lock()


class PauseError(Exception):
    """Raised inside _run when the process was intentionally paused."""
    pass


def get_ffmpeg_version() -> str | None:
    if not HAS_FFMPEG:
        return None
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        line = result.stdout.split("\n")[0]
        parts = line.split("version")
        return parts[1].strip().split()[0] if len(parts) > 1 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_ytdlp_version() -> str | None:
    try:
        binary = ensure_binary()
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10)
        return result.stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


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


def cache_thumbnail(video_id: str, thumbnail_url: str | None) -> str | None:
    """Download and cache a video thumbnail. Returns the relative path from
    METADATA_DIRECTORY/thumbnails, or None on failure."""
    if not thumbnail_url:
        return None
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    ext = thumbnail_url.rsplit(".", 1)[-1].split("?")[0] if "." in thumbnail_url else "jpg"
    dest = os.path.join(THUMBNAIL_DIR, f"{video_id}.{ext}")
    if os.path.isfile(dest):
        return f"thumbnails/{video_id}.{ext}"
    try:
        urllib.request.urlretrieve(thumbnail_url, dest)
        return f"thumbnails/{video_id}.{ext}"
    except (urllib.error.URLError, OSError) as e:
        logger.warning("Failed to cache thumbnail for %s: %s", video_id, e)
        return None


def _parse_total_bytes(line: str) -> int | None:
    """Parse total bytes from a yt-dlp progress line like '45.2% of   51.16MiB'."""
    m = _TOTAL_BYTES_PAT.search(line)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    multipliers = {"KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4}
    mult = multipliers.get(unit, 1)
    return int(val * mult)


def _run(
    args: list[str],
    timeout: int = 120,
    capture: bool = True,
    progress_callback: Any | None = None,
    task_id: str | None = None,
    file_complete_callback: Any | None = None,
    temp_dir: str | None = None,
    download_base: str | None = None,
) -> str | None:
    """Run yt-dlp. When capture=True, returns stdout (for metadata queries).
    When capture=False, streams output line-by-line for progress parsing.
    progress_callback(overall_percent: int, file_progress: list[dict], extra: dict | None)
    is called on each progress update. 'extra' contains: step, downloaded_bytes,
    total_bytes, speed, eta.
    file_complete_callback(file_path: str, index: int) is called in a daemon thread
    when each individual file reaches 100%.
    """
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

    # ── Download mode: stream stdout and parse progress ──────
    fp_list: list[dict[str, Any]] = []
    current_index = 0
    fp_total = 1
    _completed_indices: set[int] = set()
    current_phase = "fetching_metadata"
    prev_phase = "fetching_metadata"
    current_total_bytes: int | None = None
    current_downloaded_bytes: int = 0
    current_speed: str | None = None
    current_eta: str | None = None

    def _ensure(idx: int) -> None:
        while len(fp_list) <= idx:
            fp_list.append({
                "index": len(fp_list),
                "title": None,
                "percent": 0.0,
                "speed": None,
                "eta": None,
                "status": "pending",
            })

    def _set_phase(phase: str) -> bool:
        nonlocal current_phase, prev_phase
        if phase != current_phase:
            prev_phase = current_phase
            current_phase = phase
            return True
        return False

    def _build_extra() -> dict:
        return {
            "step": current_phase,
            "downloaded_bytes": current_downloaded_bytes,
            "total_bytes": current_total_bytes,
            "speed": current_speed,
            "eta": current_eta,
            "current_index": current_index,
            "total_items": fp_total,
        }

    def _fire() -> None:
        if not progress_callback:
            return
        total_pct = sum(f["percent"] for f in fp_list) / len(fp_list) if fp_list else 0.0
        extra = _build_extra()
        logger.info("_fire: total_pct=%s extra=%s", total_pct, extra)
        progress_callback(int(total_pct), [dict(f) for f in fp_list], extra)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Register process for cancellation
    if task_id:
        with _proc_lock:
            _running_procs[task_id] = proc

    def _extract_progress_stats(line: str) -> tuple[float | None, str | None, str | None, int | None]:
        """Extract percent, speed, eta, total_bytes from any progress-like line."""
        m = _PROGRESS_PAT.search(line)
        if not m:
            return None, None, None, None
        pct = float(m.group(1))
        speed: str | None = None
        eta: str | None = None
        if " at " in line and " ETA " in line:
            try:
                after_pct = line.split("%", 1)[1]
                at_part = after_pct.split(" at ", 1)[1] if " at " in after_pct else ""
                speed = at_part.split(" ETA ")[0].strip() if " ETA " in at_part else None
                eta = at_part.split(" ETA ")[1].strip() if " ETA " in at_part else None
            except (IndexError, ValueError):
                pass
        total_bytes = _parse_total_bytes(line)
        return pct, speed, eta, total_bytes

    def _apply_stats(line: str) -> None:
        nonlocal current_speed, current_eta, current_total_bytes, current_downloaded_bytes
        pct, speed, eta, total_bytes = _extract_progress_stats(line)
        if pct is None:
            return
        downloaded = int(pct / 100.0 * total_bytes) if total_bytes else 0
        current_speed = speed
        current_eta = eta
        if total_bytes:
            current_total_bytes = total_bytes
            current_downloaded_bytes = downloaded

    _was_paused = False
    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\n")

                    # ── Extract stats from every line that has them ──
            _apply_stats(line)

            # ── Phase detection ─────────────────────────────
            if _INFO_PAT.search(line) and current_phase == "fetching_metadata":
                _set_phase("preparing")
                _fire()
                continue

            if _PLAYLIST_DL_PAT.search(line) or _PLAYLIST_ITEMS_PAT.search(line):
                _set_phase("preparing")
                _fire()
                continue

            # ── Thumbnail download (--embed-thumbnail) ────────
            m = _THUMBNAIL_PAT.search(line)
            if m:
                if task_id:
                    _track_output_file(task_id, m.group(1))
                continue

            # ── Playlist item index ──────────────────────────
            m = _PLAYLIST_PAT.search(line)
            if m:
                idx = int(m.group(1))
                total = int(m.group(2))
                fp_total = total
                # Fire callback for the previous file (idx>1 = at least one file done)
                if idx > 1 and file_complete_callback:
                    prev_idx = idx - 2
                    if prev_idx not in _completed_indices:
                        _ensure(prev_idx)
                        prev_path = fp_list[prev_idx].get("path", "")
                        if prev_path:
                            _completed_indices.add(prev_idx)
                            t = threading.Thread(target=file_complete_callback, args=(prev_path, prev_idx), daemon=True)
                            t.start()
                current_index = idx - 1
                _ensure(total - 1)
                fp_list[current_index]["status"] = "downloading"
                _set_phase("downloading")
                _fire()
                continue

            # ── Already downloaded (skip) ────────────────────
            m = _ALREADY_DL_PAT.search(line)
            if m:
                _ensure(current_index)
                dest_path = m.group(1)
                if temp_dir and download_base and dest_path.startswith(temp_dir):
                    rel = os.path.relpath(dest_path, temp_dir)
                    dest_path = os.path.normpath(os.path.join(download_base, rel))
                fp_list[current_index]["title"] = _extract_title_from_path(dest_path)
                fp_list[current_index]["path"] = dest_path
                fp_list[current_index]["percent"] = 100.0
                fp_list[current_index]["status"] = "completed"
                if task_id:
                    _track_output_file(task_id, dest_path)
                if file_complete_callback and current_index not in _completed_indices:
                    _completed_indices.add(current_index)
                    t = threading.Thread(target=file_complete_callback, args=(dest_path, current_index), daemon=True)
                    t.start()
                _fire()
                continue

            # ── Destination (file path = file start) ─────────
            m = _DEST_PAT.search(line)
            if m:
                _ensure(current_index)
                dest_path = m.group(1)
                # yt-dlp temp= prefix → file is in temp dir; resolve to final home dir
                if temp_dir and download_base and dest_path.startswith(temp_dir):
                    rel = os.path.relpath(dest_path, temp_dir)
                    dest_path = os.path.normpath(os.path.join(download_base, rel))
                fp_list[current_index]["title"] = _extract_title_from_path(dest_path)
                fp_list[current_index]["path"] = dest_path
                if task_id:
                    _track_output_file(task_id, dest_path)
                current_downloaded_bytes = 0
                current_total_bytes = None
                _set_phase("downloading")
                _fire()
                continue

            # ── Completing a file stream ─────────────────────
            if _COMPLETE_PAT.search(line) and not _MERGER_PAT.search(line):
                _ensure(current_index)
                fp_list[current_index]["percent"] = 100.0
                fp_list[current_index]["status"] = "completed"
                # Callback fires when next playlist item starts or at process end
                # (not here — this 100% may be a partial DASH stream)
                _fire()
                continue

            # ── Merging (DASH formats) ───────────────────────
            m = _MERGER_PAT.search(line)
            if m:
                _set_phase("merging")
                merger_path = m.group(1)
                # Handle temp=/home= prefixes yt-dlp adds with -P
                for prefix in ("temp=", "home="):
                    if merger_path.startswith(prefix):
                        merger_path = merger_path[len(prefix):]
                        break
                # yt-dlp may write the merged file to the temp dir first,
                # then move it to the home dir. Convert temp path to final path.
                if temp_dir and download_base and merger_path.startswith(temp_dir):
                    rel = os.path.relpath(merger_path, temp_dir)
                    merger_path = os.path.normpath(os.path.join(download_base, rel))
                _ensure(current_index)
                fp_list[current_index]["path"] = merger_path
                _fire()
                continue

            # ── Converting (audio extraction or remux) ───────
            if _EXTRACT_AUDIO_PAT.search(line) or _REMUX_PAT.search(line):
                _set_phase("converting")
                _fire()
                continue

            # ── Finalizing ───────────────────────────────────
            if _DELETE_ORIG_PAT.search(line):
                _set_phase("finalizing")
                _fire()
                continue

            # ── Progress line ────────────────────────────────
            m = _PROGRESS_PAT.search(line)
            if m:
                pct = float(m.group(1))
                _ensure(current_index)
                fp_list[current_index]["percent"] = pct
                fp_list[current_index]["speed"] = current_speed
                fp_list[current_index]["eta"] = current_eta
                fp_list[current_index]["status"] = "downloading"
                _fire()

        proc.wait()
        if task_id and _pop_paused(task_id):
            _was_paused = True
            raise PauseError(f"Task {task_id} was paused")
        # Fire callback for the last file (single downloads, or last file in playlist)
        if file_complete_callback and fp_list and current_index >= 0 and current_index not in _completed_indices:
            _completed_indices.add(current_index)
            last_path = fp_list[current_index].get("path", "")
            if last_path:
                t = threading.Thread(target=file_complete_callback, args=(last_path, current_index), daemon=True)
                t.start()
        if proc.returncode == 0:
            _set_phase("finalizing")
            _fire()
        elif proc.returncode == -9:
            pass
        else:
            logger.warning("yt-dlp exited with code %d during download", proc.returncode)
            raise RuntimeError(f"yt-dlp exited with code {proc.returncode}")
    finally:
        if task_id:
            with _proc_lock:
                _running_procs.pop(task_id, None)
            if not _was_paused:
                _clear_task_output_files(task_id)

    return None


def _pop_paused(task_id: str) -> bool:
    """Check if task_id is in the paused set and remove it. Thread-safe."""
    with _paused_lock:
        if task_id in _paused_tasks:
            _paused_tasks.remove(task_id)
            return True
        return False


def kill_process(task_id: str) -> None:
    """Terminate a running yt-dlp process for task_id without removing partial files."""
    with _proc_lock:
        proc = _running_procs.get(task_id)
    if proc:
        logger.info("Killing process for task %s (pid %d)", task_id, proc.pid)
        proc.terminate()


def cancel_download(task_id: str, cleanup_dirs: list[str] | None = None) -> None:
    """Terminate the running yt-dlp process and remove only this task's output files."""
    tracked = _get_task_output_files(task_id)
    _clear_task_output_files(task_id)

    with _proc_lock:
        proc = _running_procs.get(task_id)
    if proc:
        logger.info("Cancelling download task %s (pid %d)", task_id, proc.pid)
        proc.terminate()

    for filepath in tracked:
        base = filepath[:-5] if filepath.lower().endswith(".part") else filepath
        _try_remove(filepath)
        _try_remove(base)
        _try_remove(base + ".part")
        _try_remove(base + ".ytdl")
        _try_remove(base + ".temp")
        dirpath = os.path.dirname(base)
        basename = os.path.basename(base)
        if os.path.isdir(dirpath):
            for fname in os.listdir(dirpath):
                if fname.startswith(basename) and (
                    fname.lower().endswith((".frag", ".part", ".ytdl", ".temp"))
                    or ".frag" in fname.lower()
                ):
                    _try_remove(os.path.join(dirpath, fname))


def pause_download(task_id: str) -> bool:
    """Pause a running download by terminating the process. Partial files are preserved for resume."""
    with _proc_lock:
        proc = _running_procs.get(task_id)
    if proc and proc.poll() is None:
        logger.info("Pausing download task %s (pid %d)", task_id, proc.pid)
        with _paused_lock:
            _paused_tasks.add(task_id)
        proc.terminate()
        return True
    return False





# ── Format-string helpers ─────────────────────────────────────


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
    settings: dict[str, str],
    url: str,
    is_playlist: bool = False,
    audio_only: bool = False,
    audio_format: str | None = None,
    audio_quality: str | None = None,
    remux_to: str | None = None,
    download_base: str | None = None,
    temp_dir: str | None = None,
    continue_download: bool = False,
) -> list[str]:
    # Resolve effective values: request override > profile > built-in default
    eff_audio_only = audio_only or profile.format_type == FormatType.audio_only
    eff_audio_fmt = audio_format or (profile.audio_format.value if profile.audio_format else None)
    eff_audio_qual = audio_quality or profile.audio_quality or "192K"
    eff_remux = remux_to or profile.remux_to

    if eff_audio_only:
        fmt = _build_audio_format_str(profile.download_quality_mode, profile.download_format)
    else:
        fmt = _build_video_format_str(
            profile.download_quality_mode, profile.download_quality_value, profile.download_format
        )

    args = ["--no-overwrites", "--newline"]
    if continue_download:
        args.append("--continue")
    if is_playlist:
        args.append("--yes-playlist")

    # Use yt-dlp's path separation: home for final files, temp for .part files
    effective_base = download_base or config.get_download_dir()
    args += ["-P", f"home:{effective_base}"]

    eff_temp = (temp_dir or "").strip()
    if eff_temp:
        os.makedirs(eff_temp, exist_ok=True)
        args += ["-P", f"temp:{eff_temp}"]

    args += ["-f", fmt, "-o", template]
    if not HAS_FFMPEG:
        args += ["--merge-output-format", "mp4"]

    # ── Post-processor options ───────────────────────────────
    if eff_audio_only and eff_audio_fmt:
        args += ["-x", "--audio-format", eff_audio_fmt, "--audio-quality", eff_audio_qual]
    elif eff_remux:
        args.append(f"--remux-video={eff_remux}")

    # ── Codec preference (re-encode via VideoConvertor PP) ───
    if profile.codec_preference and profile.codec_preference != CodecPreference.any:
        codec_map = {
            CodecPreference.h264: "libx264",
            CodecPreference.h265: "libx265",
            CodecPreference.vp9: "libvpx-vp9",
            CodecPreference.av1: "libaom-av1",
        }
        enc = codec_map.get(profile.codec_preference)
        if enc and HAS_FFMPEG:
            args += ["--ppa", f"VideoConvertor:-c:v {enc}"]

    # ── Container preference ─────────────────────────────────
    if profile.container_preference and not eff_audio_only:
        args += ["--merge-output-format", profile.container_preference]

    # ── Metadata / subs ──────────────────────────────────────
    if profile.embed_metadata and HAS_FFMPEG:
        args.append("--embed-metadata")
    if profile.embed_thumbnail and HAS_FFMPEG:
        args.append("--embed-thumbnail")
    if profile.subtitles:
        args.append("--write-subs")
        if profile.subtitle_langs:
            args.append(f"--sub-langs={profile.subtitle_langs}")
        args.append("--embed-subs")

    rate = settings.get("rate_limit", "").strip()
    if rate:
        args += ["--limit-rate", rate]

    timeout_val = settings.get("socket_timeout", "")
    if timeout_val:
        try:
            args += ["--socket-timeout", str(int(timeout_val))]
        except (ValueError, TypeError):
            pass

    args.append(url)
    return args


# ── Download ──────────────────────────────────────────────────


def _download_with_profile(
    url: str,
    output_dir: str,
    profile: Profile,
    settings: dict[str, str],
    is_playlist: bool = False,
    video_range: str | None = None,
    audio_only: bool = False,
    audio_format: str | None = None,
    audio_quality: str | None = None,
    remux_to: str | None = None,
    task_id: str | None = None,
    progress_callback: Any | None = None,
    include_playlist_dir: bool | None = None,
    download_base: str | None = None,
    temp_dir: str | None = None,
    continue_download: bool = False,
    file_complete_callback: Any | None = None,
) -> dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    existing = set()
    for dirpath, _dirnames, filenames in os.walk(output_dir):
        for fn in filenames:
            existing.add(os.path.normpath(os.path.join(dirpath, fn)))

    effective_base = download_base or config.get_download_dir()
    rel_path = os.path.relpath(output_dir, effective_base)

    eff_include_pl = include_playlist_dir if include_playlist_dir is not None else profile.include_playlist_dir

    if is_playlist:
        if eff_include_pl:
            template = os.path.join(rel_path, profile.playlist_template)
        else:
            template = os.path.join(rel_path, profile.filename_template)
    else:
        template = os.path.join(rel_path, profile.filename_template)

    args = _build_args(
        output_dir, template, profile, settings, url,
        is_playlist=is_playlist,
        audio_only=audio_only,
        audio_format=audio_format,
        audio_quality=audio_quality,
        remux_to=remux_to,
        download_base=effective_base,
        temp_dir=temp_dir,
        continue_download=continue_download,
    )

    if video_range:
        args.insert(0, f"--playlist-items={video_range}")

    _run(args, capture=False, progress_callback=progress_callback, task_id=task_id,
         file_complete_callback=file_complete_callback,
         temp_dir=temp_dir, download_base=effective_base)

    all_files = _collect_files(output_dir, is_playlist=is_playlist, audio_only=audio_only)
    files = [f for f in all_files if os.path.normpath(f["path"]) not in existing]
    if not files and all_files:
        video_id = _extract_video_id(url)
        if video_id:
            files = [f for f in all_files if video_id in f.get("name", "")]
        if not files:
            files = [f for f in all_files if f.get("fileType") in ("video", "audio", "playlist")]
        if not files:
            files = all_files
    return {"files": files}


def _collect_files(directory: str, is_playlist: bool = False, audio_only: bool = False) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(directory):
        rel = os.path.relpath(dirpath, directory)
        if rel != "." and (rel.startswith("radarr") or rel.startswith("sonarr")):
            dirnames[:] = []
            continue
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            ext = classify_file_extension(path)
            file_type = classify_file_type(path)
            fmt = classify_file_format(path)
            detail = classify_file_detail(path)

            # Override type for playlist tasks: group all files under
            # a playlist category regardless of individual file extension.
            if is_playlist and file_type in ("video", "audio"):
                file_type = "playlist"
                fmt = "Playlist"
                detail = "Video"

            if audio_only and file_type == "video":
                file_type = "audio"

            files.append({
                "id": str(uuid.uuid4()),
                "name": os.path.relpath(path, directory),
                "size": os.path.getsize(path),
                "path": path,
                "fileType": file_type,
                "format": fmt,
                "detail": detail,
                "fileExtension": ext,
            })
    return files


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


def _parse_video_formats(info: dict) -> list[dict[str, Any]]:
    formats: list[dict[str, Any]] = []
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
    return formats


def _build_metadata(video_id: str, info: dict) -> dict:
    formats = _parse_video_formats(info)
    heights = sorted(set(f["height"] for f in formats if f["height"]), reverse=True)
    return {
        "id": video_id,
        "title": info.get("title"),
        "url": f"https://www.youtube.com/watch?v={video_id}",
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


def get_metadata(url: str) -> dict:
    stdout = _run(["--dump-single-json", "--flat-playlist", url], timeout=60)
    assert stdout is not None
    info = json.loads(stdout)

    if "entries" in info:
        entries = info.get("entries", [])
        dur = sum(e.get("duration", 0) or 0 for e in entries)
        thumb = info.get("thumbnail")
        if not thumb:
            thumbs = info.get("thumbnails") or []
            if thumbs:
                thumb = thumbs[-1]["url"]
        if not thumb and entries:
            thumb = entries[0].get("thumbnail")
        return {
            "id": info.get("id", ""),
            "title": info.get("title") or (entries[0].get("title") if entries else None),
            "url": url,
            "duration": dur,
            "channel": info.get("channel") or info.get("uploader") or (entries[0].get("channel") if entries else None),
            "channelUrl": info.get("channel_url") or info.get("uploader_url"),
            "thumbnail": thumb,
            "description": info.get("description"),
            "viewCount": info.get("view_count"),
            "likeCount": info.get("like_count"),
            "formats": [],
            "bestHeight": None,
        }

    return _build_metadata(info["id"], info)


def get_playlist_info(url: str) -> list[dict[str, Any]]:
    stdout = _run(["--flat-playlist", "--dump-json", url], timeout=120)
    assert stdout is not None
    entries: list[dict[str, Any]] = []
    for line in stdout.strip().splitlines():
        if not line:
            continue
        e = json.loads(line)
        thumbnails = e.get("thumbnails") or []
        thumbnail_url = thumbnails[-1]["url"] if thumbnails else None
        entries.append(
            {
                "id": e["id"],
                "title": e.get("title"),
                "url": f"https://www.youtube.com/watch?v={e['id']}",
                "duration": e.get("duration"),
                "channel": e.get("channel") or e.get("uploader"),
                "thumbnail_url": thumbnail_url,
            }
        )
    return entries


def download_video(
    url: str,
    output_dir: str | None = None,
    profile: Profile | None = None,
    settings: dict[str, str] | None = None,
    audio_only: bool = False,
    audio_format: str | None = None,
    audio_quality: str | None = None,
    remux_to: str | None = None,
    task_id: str | None = None,
    progress_callback: Any | None = None,
    download_base: str | None = None,
    temp_dir: str | None = None,
    continue_download: bool = False,
    file_complete_callback: Any | None = None,
) -> dict[str, Any]:
    if profile is None:
        profile = Profile(id=0, name="_adhoc", created_at=datetime.now(), updated_at=datetime.now())
    if settings is None:
        settings = db.get_all_settings()

    out = output_dir or profile.download_directory or os.getcwd()
    return _download_with_profile(
        url, out, profile, settings,
        is_playlist=False,
        audio_only=audio_only,
        audio_format=audio_format,
        audio_quality=audio_quality,
        remux_to=remux_to,
        task_id=task_id,
        progress_callback=progress_callback,
        download_base=download_base,
        temp_dir=temp_dir,
        continue_download=continue_download,
        file_complete_callback=file_complete_callback,
    )


def download_playlist(
    url: str,
    output_dir: str | None = None,
    profile: Profile | None = None,
    settings: dict[str, str] | None = None,
    video_range: str | None = None,
    audio_only: bool = False,
    audio_format: str | None = None,
    audio_quality: str | None = None,
    remux_to: str | None = None,
    task_id: str | None = None,
    progress_callback: Any | None = None,
    include_playlist_dir: bool | None = None,
    download_base: str | None = None,
    temp_dir: str | None = None,
    continue_download: bool = False,
    file_complete_callback: Any | None = None,
) -> dict[str, Any]:
    if profile is None:
        profile = Profile(id=0, name="_adhoc", created_at=datetime.now(), updated_at=datetime.now())
    if settings is None:
        settings = db.get_all_settings()

    out = output_dir or profile.download_directory or os.getcwd()
    return _download_with_profile(
        url, out, profile, settings,
        is_playlist=True,
        video_range=video_range,
        audio_only=audio_only,
        audio_format=audio_format,
        audio_quality=audio_quality,
        remux_to=remux_to,
        task_id=task_id,
        progress_callback=progress_callback,
        include_playlist_dir=include_playlist_dir,
        download_base=download_base,
        temp_dir=temp_dir,
        continue_download=continue_download,
        file_complete_callback=file_complete_callback,
    )
