import os
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime

from tube_explore.config import get_config_dir, get_db_path
from tube_explore.models import (
    SEED_PRESETS,
    SEED_PROFILES,
    ConversionPreset,
    ConversionPresetCreate,
    ConversionPresetUpdate,
    OutboxFile,
    OutboxFileCreate,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    QualityMode,
)


def _connect() -> sqlite3.Connection:
    os.makedirs(get_config_dir(), exist_ok=True)
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_profile(row: sqlite3.Row) -> Profile:
    d = dict(row)
    d["embed_metadata"] = bool(d["embed_metadata"])
    d["embed_thumbnail"] = bool(d["embed_thumbnail"])
    d["subtitles"] = bool(d["subtitles"])
    d["download_quality_mode"] = QualityMode(d["download_quality_mode"])
    d["convert_quality_mode"] = QualityMode(d["convert_quality_mode"])
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    d["updated_at"] = datetime.fromisoformat(d["updated_at"])
    return Profile(**d)


def _row_to_preset(row: sqlite3.Row) -> ConversionPreset:
    d = dict(row)
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    d["updated_at"] = datetime.fromisoformat(d["updated_at"])
    return ConversionPreset(**d)


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                label       TEXT NOT NULL DEFAULT '',

                download_directory      TEXT NOT NULL DEFAULT '',
                download_format         TEXT DEFAULT NULL,
                download_quality_mode   TEXT NOT NULL DEFAULT 'best'
                                        CHECK(download_quality_mode IN ('best','least','at_most','at_least')),
                download_quality_value  INTEGER DEFAULT NULL,

                convert_preset          TEXT DEFAULT NULL,
                convert_format          TEXT DEFAULT NULL,
                convert_quality_mode    TEXT DEFAULT 'best'
                                        CHECK(convert_quality_mode IN ('best','least','at_most','at_least')),
                convert_quality_value   INTEGER DEFAULT NULL,

                filename_template       TEXT NOT NULL DEFAULT '%(title)s [%(id)s].%(ext)s',
                playlist_template       TEXT NOT NULL DEFAULT '%(playlist_title)s/%(playlist_index)02d - %(title)s [%(id)s].%(ext)s',
                embed_metadata          INTEGER NOT NULL DEFAULT 1,
                embed_thumbnail         INTEGER NOT NULL DEFAULT 1,
                subtitles               INTEGER NOT NULL DEFAULT 0,
                subtitle_langs          TEXT DEFAULT NULL,

                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversion_presets (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                name              TEXT NOT NULL UNIQUE,
                label             TEXT NOT NULL DEFAULT '',
                container         TEXT NOT NULL,
                video_codec       TEXT DEFAULT NULL,
                video_bitrate     TEXT DEFAULT NULL,
                video_fps         REAL DEFAULT NULL,
                video_preset      TEXT DEFAULT NULL,
                video_pixfmt      TEXT DEFAULT NULL,
                audio_codec       TEXT DEFAULT NULL,
                audio_bitrate     TEXT DEFAULT NULL,
                audio_samplerate  INTEGER DEFAULT NULL,
                audio_channels    INTEGER DEFAULT NULL,
                max_width         INTEGER DEFAULT NULL,
                max_height        INTEGER DEFAULT NULL,
                output_ext        TEXT NOT NULL,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbox_files (
                id                TEXT PRIMARY KEY,
                file_name         TEXT NOT NULL,
                file_size         INTEGER NOT NULL,
                media_url         TEXT DEFAULT NULL,
                task_id           TEXT DEFAULT NULL,
                quality_mode      TEXT DEFAULT NULL,
                quality_value     INTEGER DEFAULT NULL,
                convert_preset    TEXT DEFAULT NULL,
                status            TEXT NOT NULL DEFAULT 'pending',
                error             TEXT DEFAULT NULL,
                created_at        TEXT NOT NULL,
                updated_at        TEXT DEFAULT NULL
            );
        """)

        # Add convert_preset column if missing (migration for existing DBs)
        with suppress(sqlite3.OperationalError):
            conn.execute("ALTER TABLE profiles ADD COLUMN convert_preset TEXT DEFAULT NULL")

        for key in ("rate_limit", "temp_directory", "retry_count", "socket_timeout"):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, {"rate_limit": "", "temp_directory": "", "retry_count": "3", "socket_timeout": "30"}[key]),
            )

        _seed_profiles(conn)
        _seed_presets(conn)


def _seed_profiles(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    for profile in SEED_PROFILES:
        existing = conn.execute("SELECT id FROM profiles WHERE name = ?", (profile["name"],)).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO profiles
                (name, label,
                 download_directory, download_format, download_quality_mode, download_quality_value,
                 convert_preset, convert_format, convert_quality_mode, convert_quality_value,
                 filename_template, playlist_template,
                 embed_metadata, embed_thumbnail, subtitles, subtitle_langs,
                 created_at, updated_at)
            VALUES (?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?)
        """,
            (
                profile["name"],
                profile.get("label", ""),
                profile.get("download_directory", ""),
                profile.get("download_format"),
                profile.get("download_quality_mode", "best"),
                profile.get("download_quality_value"),
                profile.get("convert_preset"),
                profile.get("convert_format"),
                profile.get("convert_quality_mode", "best"),
                profile.get("convert_quality_value"),
                profile.get("filename_template", "%(title)s [%(id)s].%(ext)s"),
                profile.get("playlist_template", "%(playlist_title)s/%(playlist_index)02d - %(title)s [%(id)s].%(ext)s"),
                int(profile.get("embed_metadata", True)),
                int(profile.get("embed_thumbnail", True)),
                int(profile.get("subtitles", False)),
                profile.get("subtitle_langs"),
                now,
                now,
            ),
        )


def _seed_presets(conn: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    for preset in SEED_PRESETS:
        existing = conn.execute("SELECT id FROM conversion_presets WHERE name = ?", (preset["name"],)).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO conversion_presets
                (name, label, container,
                 video_codec, video_bitrate, video_fps, video_preset, video_pixfmt,
                 audio_codec, audio_bitrate, audio_samplerate, audio_channels,
                 max_width, max_height, output_ext,
                 created_at, updated_at)
            VALUES (?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?)
        """,
            (
                preset["name"],
                preset.get("label", ""),
                preset["container"],
                preset.get("video_codec"),
                preset.get("video_bitrate"),
                preset.get("video_fps"),
                preset.get("video_preset"),
                preset.get("video_pixfmt"),
                preset.get("audio_codec"),
                preset.get("audio_bitrate"),
                preset.get("audio_samplerate"),
                preset.get("audio_channels"),
                preset.get("max_width"),
                preset.get("max_height"),
                preset["output_ext"],
                now,
                now,
            ),
        )


# ── Profile CRUD ──────────────────────────────────────────────


def list_profiles() -> list[Profile]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY name").fetchall()
    return [_row_to_profile(r) for r in rows]


def get_profile(profile_id: int) -> Profile | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _row_to_profile(row) if row else None


def get_profile_by_name(name: str) -> Profile | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE name = ?", (name,)).fetchone()
    return _row_to_profile(row) if row else None


def create_profile(data: ProfileCreate) -> Profile:
    now = datetime.now(UTC).isoformat()
    vals = (
        data.name,
        data.label or "",
        data.download_directory or "",
        data.download_format,
        data.download_quality_mode.value,
        data.download_quality_value,
        data.convert_preset,
        data.convert_format,
        data.convert_quality_mode.value,
        data.convert_quality_value,
        data.filename_template or "%(title)s [%(id)s].%(ext)s",
        data.playlist_template or "%(playlist_title)s/%(playlist_index)02d - %(title)s [%(id)s].%(ext)s",
        int(data.embed_metadata),
        int(data.embed_thumbnail),
        int(data.subtitles),
        data.subtitle_langs,
        now,
        now,
    )
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO profiles (name, label,
                download_directory, download_format, download_quality_mode, download_quality_value,
                convert_preset, convert_format, convert_quality_mode, convert_quality_value,
                filename_template, playlist_template,
                embed_metadata, embed_thumbnail, subtitles, subtitle_langs,
                created_at, updated_at)
            VALUES (?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?)
        """,
            vals,
        )
        profile_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    assert profile_id is not None
    result = get_profile(profile_id)
    assert result is not None
    return result


def update_profile(profile_id: int, data: ProfileUpdate) -> Profile | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []

    for attr in data.model_dump(exclude_none=True):
        db_col = attr
        if attr in ("embed_metadata", "embed_thumbnail", "subtitles"):
            val = int(getattr(data, attr))
        else:
            val = getattr(data, attr)
            if attr in ("download_quality_mode", "convert_quality_mode"):
                val = val.value
        fields.append(f"{db_col} = ?")
        vals.append(val)

    if not fields:
        return get_profile(profile_id)

    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(profile_id)
    with _connect() as conn:
        conn.execute(f"UPDATE profiles SET {', '.join(fields)} WHERE id = ?", vals)
    return get_profile(profile_id)


def delete_profile(profile_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))


# ── Settings ──────────────────────────────────────────────────


def get_all_settings() -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    return {r["key"]: r["value"] for r in rows}


def get_setting(key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def set_settings(data: dict[str, str]) -> None:
    with _connect() as conn:
        for key, value in data.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


# ── Conversion Preset CRUD ────────────────────────────────────


def list_presets() -> list[ConversionPreset]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM conversion_presets ORDER BY name").fetchall()
    return [_row_to_preset(r) for r in rows]


def get_preset(preset_id: int) -> ConversionPreset | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM conversion_presets WHERE id = ?", (preset_id,)).fetchone()
    return _row_to_preset(row) if row else None


def get_preset_by_name(name: str) -> ConversionPreset | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM conversion_presets WHERE name = ?", (name,)).fetchone()
    return _row_to_preset(row) if row else None


def create_preset(data: ConversionPresetCreate) -> ConversionPreset:
    now = datetime.now(UTC).isoformat()
    vals = (
        data.name,
        data.label or "",
        data.container,
        data.video_codec,
        data.video_bitrate,
        data.video_fps,
        data.video_preset,
        data.video_pixfmt,
        data.audio_codec,
        data.audio_bitrate,
        data.audio_samplerate,
        data.audio_channels,
        data.max_width,
        data.max_height,
        data.output_ext,
        now,
        now,
    )
    conn = _connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO conversion_presets
                (name, label, container,
                 video_codec, video_bitrate, video_fps, video_preset, video_pixfmt,
                 audio_codec, audio_bitrate, audio_samplerate, audio_channels,
                 max_width, max_height, output_ext,
                 created_at, updated_at)
            VALUES (?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?)
        """,
            vals,
        )
        preset_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    assert preset_id is not None
    result = get_preset(preset_id)
    assert result is not None
    return result


def update_preset(preset_id: int, data: ConversionPresetUpdate) -> ConversionPreset | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []

    for attr, val in data.model_dump(exclude_none=True).items():
        fields.append(f"{attr} = ?")
        vals.append(val)

    if not fields:
        return get_preset(preset_id)

    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(preset_id)
    with _connect() as conn:
        conn.execute(f"UPDATE conversion_presets SET {', '.join(fields)} WHERE id = ?", vals)
    return get_preset(preset_id)


def delete_preset(preset_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM conversion_presets WHERE id = ?", (preset_id,))


# ── Outbox Files ────────────────────────────────────────────────


def _row_to_outbox_file(row: sqlite3.Row) -> OutboxFile:
    return OutboxFile(
        id=row["id"],
        file_name=row["file_name"],
        file_size=row["file_size"],
        media_url=row["media_url"],
        task_id=row["task_id"],
        quality_mode=row["quality_mode"],
        quality_value=row["quality_value"],
        convert_preset=row["convert_preset"],
        status=row["status"],
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
    )


def insert_outbox_file(data: OutboxFileCreate) -> OutboxFile:
    now = data.created_at.isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO outbox_files
                (id, file_name, file_size,
                 media_url, task_id,
                 quality_mode, quality_value, convert_preset,
                 status, error,
                 created_at, updated_at)
            VALUES (?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?)
            """,
            (
                data.id,
                data.file_name,
                data.file_size,
                data.media_url,
                data.task_id,
                data.quality_mode,
                data.quality_value,
                data.convert_preset,
                data.status,
                data.error,
                now,
                None,
            ),
        )
        conn.commit()
    result = get_outbox_file(data.id)
    assert result is not None
    return result


def get_outbox_file(file_id: str) -> OutboxFile | None:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM outbox_files WHERE id = ?", (file_id,))
        row = cur.fetchone()
    return _row_to_outbox_file(row) if row else None


def list_outbox_files() -> list[OutboxFile]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM outbox_files ORDER BY created_at DESC")
        return [_row_to_outbox_file(r) for r in cur.fetchall()]


def delete_outbox_file(file_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM outbox_files WHERE id = ?", (file_id,))


def update_outbox_file_status(file_id: str, status: str, error: str | None = None) -> OutboxFile | None:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE outbox_files SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            (status, error, now, file_id),
        )
        conn.commit()
    return get_outbox_file(file_id)
