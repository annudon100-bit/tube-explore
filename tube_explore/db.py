import os
import sqlite3
from datetime import UTC, datetime

from tube_explore.config import get_config_dir, get_db_path
from tube_explore.models import (
    SEED_PROFILES,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    QualityMode,
    AudioFormat,
    FormatType,
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
    d["include_playlist_dir"] = bool(d.get("include_playlist_dir", True))
    d["download_quality_mode"] = QualityMode(d["download_quality_mode"])
    if d.get("audio_format"):
        d["audio_format"] = AudioFormat(d["audio_format"])
    if d.get("format_type"):
        d["format_type"] = FormatType(d["format_type"])
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    d["updated_at"] = datetime.fromisoformat(d["updated_at"])
    return Profile(**d)


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

                format_type             TEXT NOT NULL DEFAULT 'video+audio',
                audio_format            TEXT DEFAULT NULL,
                audio_quality           TEXT DEFAULT NULL,
                remux_to                TEXT DEFAULT NULL,

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
        """)

        for key in ("rate_limit", "temp_directory", "retry_count", "socket_timeout"):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, {"rate_limit": "", "temp_directory": "/temp", "retry_count": "3", "socket_timeout": "30"}[key]),
            )

        _migrate_profiles(conn)
        _seed_profiles(conn)


def _migrate_profiles(conn: sqlite3.Connection) -> None:
    existing = [row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()]
    if "include_playlist_dir" not in existing:
        conn.execute("ALTER TABLE profiles ADD COLUMN include_playlist_dir INTEGER NOT NULL DEFAULT 1")


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
                 format_type, audio_format, audio_quality, remux_to,
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
                profile.get("format_type", "video+audio"),
                profile.get("audio_format"),
                profile.get("audio_quality"),
                profile.get("remux_to"),
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
        data.format_type.value,
        data.audio_format.value if data.audio_format else None,
        data.audio_quality,
        data.remux_to,
        int(data.include_playlist_dir),
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
                format_type, audio_format, audio_quality, remux_to,
                include_playlist_dir,
                filename_template, playlist_template,
                embed_metadata, embed_thumbnail, subtitles, subtitle_langs,
                created_at, updated_at)
            VALUES (?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?,
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
            if attr == "download_quality_mode":
                val = val.value
            elif attr == "format_type":
                val = val.value
            elif attr == "audio_format":
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
