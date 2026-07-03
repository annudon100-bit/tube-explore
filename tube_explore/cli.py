import argparse
import json
import os

from tube_explore import config, db, ytdlp
from tube_explore.models import ProfileCreate, ProfileUpdate

# ── Info & Search ────────────────────────────────────────────


def cmd_info(args):
    meta = ytdlp.get_metadata(args.url)
    dur = meta["duration"]
    dur_str = f"{int(dur) // 60}:{int(dur) % 60:02d}" if dur else "?:??"
    print(f"Title: {meta['title']}")
    print(f"Duration: {dur_str}")
    print(f"Channel: {meta['channel']}")
    print(f"Best: {meta['bestHeight']}p" if meta["bestHeight"] else "Best: audio only")
    if args.json:
        print(json.dumps(meta, indent=2))


def cmd_search(args):
    results = ytdlp.search_videos(args.query, args.limit)
    for i, r in enumerate(results, 1):
        dur = r["duration"]
        dur_str = f"{int(dur) // 60}:{int(dur) % 60:02d}" if dur else "?:??"
        print(f"{i:>3}. [{dur_str}] {r['title'][:80]}")
        print(f"       {r['url']}")
        print(f"       {r['channel'] or ''}")
    print(f"\n{len(results)} results")


def cmd_download(args):
    settings = db.get_all_settings()
    profile = None
    if args.profile:
        p = db.get_profile_by_name(args.profile)
        if not p:
            print(f"Profile '{args.profile}' not found")
            return
        profile = p

    download_base = config.get_download_dir()
    temp_dir = settings.get("temp_directory", "").strip() or "/temp"

    # Build resolved output path like api.py's _resolve_output_path
    segments = [download_base]
    override = args.download_path_override
    if override:
        segments.append(override.lstrip("/").lstrip("\\"))
    else:
        profile_dir = (profile.download_directory or "").lstrip("/").lstrip("\\") if profile else ""
        if profile_dir:
            segments.append(profile_dir)
        if args.output:
            segments.append(args.output.lstrip("/").lstrip("\\"))

    out = os.path.join(*segments)

    kwargs = dict(
        output_dir=out, profile=profile, settings=settings,
        audio_only=args.audio_only,
        download_base=download_base,
        temp_dir=temp_dir,
    )

    if args.playlist:
        ytdlp.download_playlist(args.url, **kwargs, video_range=args.range)
    else:
        ytdlp.download_video(args.url, **kwargs)


def cmd_playlist(args):
    entries = ytdlp.get_playlist_info(args.url)
    total = len(entries)
    total_dur = sum(e["duration"] or 0 for e in entries)
    m, s = divmod(int(total_dur), 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    print(f"Playlist: {total} videos, total duration {' '.join(parts)}")
    for i, e in enumerate(entries, 1):
        dur = e["duration"]
        dur_str = f"{int(dur) // 60}:{int(dur) % 60:02d}" if dur else "?:??"
        print(f"  {i:>3}. [{dur_str}] {e['title'][:80]}")


# ── Profile subcommands ──────────────────────────────────────


def cmd_profile_list(args):
    rows = db.list_profiles()
    if not rows:
        print("No profiles")
        return
    for r in rows:
        print(f"{r.id:>3}  {r.name:<20}  {r.label or ''}")


def cmd_profile_show(args):
    p = db.get_profile_by_name(args.name) or db.get_profile(int(args.name))
    if not p:
        print(f"Profile '{args.name}' not found")
        return
    for k, v in p.model_dump().items():
        print(f"{k}: {v}")


def cmd_profile_create(args):
    data = ProfileCreate(name=args.name)
    if args.label:
        data.label = args.label
    if args.download_directory:
        data.download_directory = args.download_directory
    if args.download_format:
        data.download_format = args.download_format
    if args.download_quality_mode:
        data.download_quality_mode = args.download_quality_mode
    if args.download_quality_value is not None:
        data.download_quality_value = args.download_quality_value
    if args.audio_format:
        data.audio_format = args.audio_format
    if args.audio_quality:
        data.audio_quality = args.audio_quality
    if args.remux_to:
        data.remux_to = args.remux_to
    if args.format_type:
        data.format_type = args.format_type
    if args.embed_metadata is not None:
        data.embed_metadata = bool(args.embed_metadata)
    if args.embed_thumbnail is not None:
        data.embed_thumbnail = bool(args.embed_thumbnail)
    if args.subtitles is not None:
        data.subtitles = bool(args.subtitles)
    try:
        p = db.create_profile(data)
        print(f"Created profile '{p.name}' (id={p.id})")
    except Exception as e:
        print(f"Error: {e}")


def cmd_profile_update(args):
    p = db.get_profile_by_name(args.name)
    if not p:
        print(f"Profile '{args.name}' not found")
        return
    data = ProfileUpdate()
    if args.label is not None:
        data.label = args.label
    if args.download_directory is not None:
        data.download_directory = args.download_directory
    if args.download_format is not None:
        data.download_format = args.download_format
    if args.download_quality_mode is not None:
        data.download_quality_mode = args.download_quality_mode
    if args.download_quality_value is not None:
        data.download_quality_value = args.download_quality_value
    if args.audio_format is not None:
        data.audio_format = args.audio_format
    if args.audio_quality is not None:
        data.audio_quality = args.audio_quality
    if args.remux_to is not None:
        data.remux_to = args.remux_to
    if args.format_type is not None:
        data.format_type = args.format_type
    if args.embed_metadata is not None:
        data.embed_metadata = bool(args.embed_metadata)
    if args.embed_thumbnail is not None:
        data.embed_thumbnail = bool(args.embed_thumbnail)
    if args.subtitles is not None:
        data.subtitles = bool(args.subtitles)
    if not data.model_dump(exclude_none=True):
        print("No changes")
        return
    updated = db.update_profile(p.id, data)
    print(f"Updated profile '{updated.name}'")


def cmd_profile_delete(args):
    p = db.get_profile_by_name(args.name)
    if not p:
        print(f"Profile '{args.name}' not found")
        return
    db.delete_profile(p.id)
    print(f"Deleted profile '{args.name}'")


# ── Settings subcommands ─────────────────────────────────────


def cmd_settings_show(args):
    s = db.get_all_settings()
    for k, v in s.items():
        print(f"{k}: {v}")


def cmd_settings_set(args):
    key_map = {
        "rate-limit": "rate_limit",
        "temp-directory": "temp_directory",
        "retry-count": "retry_count",
        "socket-timeout": "socket_timeout",
    }
    db_key = key_map.get(args.key)
    if not db_key:
        print(f"Unknown setting '{args.key}'. Valid: {', '.join(key_map)}")
        return
    db.set_setting(db_key, args.value)
    print(f"Set {args.key} = {args.value}")


# ── Main ─────────────────────────────────────────────────────


def main():
    db.init_db()

    parser = argparse.ArgumentParser(description="Tube Explore - Media downloader & searcher")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Show video metadata")
    p_info.add_argument("url")
    p_info.add_argument("--json", action="store_true")
    p_info.set_defaults(func=cmd_info)

    p_search = sub.add_parser("search", help="Search videos")
    p_search.add_argument("query")
    p_search.add_argument("--limit", "-l", type=int, default=10)
    p_search.set_defaults(func=cmd_search)

    p_dl = sub.add_parser("download", help="Download video or playlist")
    p_dl.add_argument("url")
    p_dl.add_argument("--output", "-o", help="Relative subdirectory appended to the base download directory")
    p_dl.add_argument("--download-path-override", help="Relative subdirectory appended to the base download directory (alternative to --output)")
    p_dl.add_argument("--profile", "-p", help="Profile name")
    p_dl.add_argument("--format", "-f", help="Format string")
    p_dl.add_argument("--audio-only", "-a", action="store_true")
    p_dl.add_argument("--playlist", action="store_true")
    p_dl.add_argument("--range", "-r")
    p_dl.set_defaults(func=cmd_download)

    p_pl = sub.add_parser("playlist", help="List playlist contents")
    p_pl.add_argument("url")
    p_pl.set_defaults(func=cmd_playlist)

    p_profile = sub.add_parser("profile", help="Manage download profiles")
    pprof_sub = p_profile.add_subparsers(dest="profile_command", required=True)

    p_ls = pprof_sub.add_parser("list", help="List profiles")
    p_ls.set_defaults(func=cmd_profile_list)

    p_sh = pprof_sub.add_parser("show", help="Show profile details")
    p_sh.add_argument("name")
    p_sh.set_defaults(func=cmd_profile_show)

    p_cr = pprof_sub.add_parser("create", help="Create a profile")
    p_cr.add_argument("name")
    p_cr.add_argument("--label")
    p_cr.add_argument("--download-directory")
    p_cr.add_argument("--download-format")
    p_cr.add_argument("--download-quality-mode", choices=["best", "least", "at_most", "at_least"])
    p_cr.add_argument("--download-quality-value", type=int)
    p_cr.add_argument("--audio-format")
    p_cr.add_argument("--audio-quality")
    p_cr.add_argument("--remux-to")
    p_cr.add_argument("--format-type", choices=["video+audio", "video_only", "audio_only"])
    p_cr.add_argument("--embed-metadata", type=int, choices=[0, 1])
    p_cr.add_argument("--embed-thumbnail", type=int, choices=[0, 1])
    p_cr.add_argument("--subtitles", type=int, choices=[0, 1])
    p_cr.set_defaults(func=cmd_profile_create)

    p_up = pprof_sub.add_parser("update", help="Update a profile")
    p_up.add_argument("name")
    p_up.add_argument("--label")
    p_up.add_argument("--download-directory")
    p_up.add_argument("--download-format")
    p_up.add_argument("--download-quality-mode", choices=["best", "least", "at_most", "at_least"])
    p_up.add_argument("--download-quality-value", type=int)
    p_up.add_argument("--audio-format")
    p_up.add_argument("--audio-quality")
    p_up.add_argument("--remux-to")
    p_up.add_argument("--format-type", choices=["video+audio", "video_only", "audio_only"])
    p_up.add_argument("--embed-metadata", type=int, choices=[0, 1])
    p_up.add_argument("--embed-thumbnail", type=int, choices=[0, 1])
    p_up.add_argument("--subtitles", type=int, choices=[0, 1])
    p_up.set_defaults(func=cmd_profile_update)

    p_del = pprof_sub.add_parser("delete", help="Delete a profile")
    p_del.add_argument("name")
    p_del.set_defaults(func=cmd_profile_delete)

    p_set = sub.add_parser("settings", help="Manage global settings")
    pset_sub = p_set.add_subparsers(dest="settings_command", required=True)

    p_ss = pset_sub.add_parser("show", help="Show all settings")
    p_ss.set_defaults(func=cmd_settings_show)

    p_sset = pset_sub.add_parser("set", help="Set a setting")
    p_sset.add_argument("key", choices=["rate-limit", "temp-directory", "retry-count", "socket-timeout"])
    p_sset.add_argument("value")
    p_sset.set_defaults(func=cmd_settings_set)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
