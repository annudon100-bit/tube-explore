import os
import sqlite3
from datetime import UTC, datetime
from typing import Any

from tube_explore.arr.models import (
    ArrInstance,
    ArrInstanceCreate,
    ArrInstanceStats,
    ArrInstanceUpdate,
    ArrKind,
    ArrMissingItemCache,
)


def _connect() -> sqlite3.Connection:
    from tube_explore.config import get_config_dir, get_db_path
    os.makedirs(get_config_dir(), exist_ok=True)
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row_to_arr_instance(row: sqlite3.Row) -> ArrInstance:
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    d["is_default"] = bool(d["is_default"])
    for ts_field in ("last_test_at", "last_sync_at", "created_at", "updated_at"):
        if d.get(ts_field):
            d[ts_field] = datetime.fromisoformat(d[ts_field])
    return ArrInstance(**d)


def _row_to_arr_stats(row: sqlite3.Row) -> ArrInstanceStats:
    d = dict(row)
    if d.get("last_sync_at"):
        d["last_sync_at"] = datetime.fromisoformat(d["last_sync_at"])
    d["updated_at"] = datetime.fromisoformat(d["updated_at"])
    return ArrInstanceStats(**d)


# ── Table creation ──────────────────────────────────────────────


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS arr_instances (
            id                          TEXT PRIMARY KEY,
            name                        TEXT NOT NULL UNIQUE,
            base_url                    TEXT NOT NULL,
            api_key_encrypted           TEXT NOT NULL,
            kind                        TEXT NOT NULL DEFAULT 'radarr'
                                        CHECK(kind IN ('radarr', 'sonarr')),
            tube_write_path             TEXT NOT NULL,
            arr_import_path             TEXT NOT NULL,
            host_path_hint              TEXT NULL,
            default_profile_id          TEXT NULL,
            default_quality_profile_id  INTEGER NULL,
            default_root_folder_path    TEXT NULL,
            import_mode                 TEXT NOT NULL DEFAULT 'move',
            enabled                     INTEGER NOT NULL DEFAULT 1,
            is_default                  INTEGER NOT NULL DEFAULT 0,
            last_test_status            TEXT NULL,
            last_test_message           TEXT NULL,
            last_test_at                TEXT NULL,
            last_sync_status            TEXT NULL,
            last_sync_message           TEXT NULL,
            last_sync_at                TEXT NULL,
            arr_version                 TEXT NULL,
            created_at                  TEXT NOT NULL,
            updated_at                  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS arr_instance_stats (
            arr_instance_id             TEXT PRIMARY KEY,
            missing_count               INTEGER NOT NULL DEFAULT 0,
            monitored_count             INTEGER NOT NULL DEFAULT 0,
            unmonitored_missing_count   INTEGER NOT NULL DEFAULT 0,
            root_folder_count           INTEGER NOT NULL DEFAULT 0,
            queue_count                 INTEGER NOT NULL DEFAULT 0,
            imports_24h                 INTEGER NOT NULL DEFAULT 0,
            last_sync_at                TEXT NULL,
            updated_at                  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS arr_missing_item_cache (
            arr_instance_id     TEXT NOT NULL,
            item_id             INTEGER NOT NULL,
            kind                TEXT NOT NULL DEFAULT 'radarr',
            title               TEXT NOT NULL,
            year                INTEGER NULL,
            tmdb_id             INTEGER NULL,
            imdb_id             TEXT NULL,
            tvdb_id             INTEGER NULL,
            monitored           INTEGER NULL,
            has_file            INTEGER NULL,
            quality_profile_id  INTEGER NULL,
            quality_profile_name TEXT NULL,
            root_folder_path    TEXT NULL,
            item_path           TEXT NULL,
            poster_url          TEXT NULL,
            overview            TEXT NULL,
            season_number       INTEGER NULL,
            episode_number      INTEGER NULL,
            series_id           INTEGER NULL,
            series_title        TEXT NULL,
            cached_at           TEXT NOT NULL,
            PRIMARY KEY (arr_instance_id, item_id, kind)
        );

        CREATE TABLE IF NOT EXISTS arr_download_links (
            id                      TEXT PRIMARY KEY,
            task_id                 TEXT NOT NULL UNIQUE,
            arr_instance_id         TEXT NOT NULL,
            arr_item_id             INTEGER NOT NULL,
            kind                    TEXT NOT NULL DEFAULT 'radarr',
            title                   TEXT NOT NULL,
            year                    INTEGER NULL,
            tmdb_id                 INTEGER NULL,
            imdb_id                 TEXT NULL,
            tvdb_id                 INTEGER NULL,
            source_url              TEXT NOT NULL,
            local_staging_dir       TEXT NOT NULL,
            arr_staging_dir         TEXT NOT NULL,
            local_final_file_path   TEXT NULL,
            arr_final_file_path     TEXT NULL,
            created_at              TEXT NOT NULL,
            updated_at              TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS arr_import_attempts (
            id                      TEXT PRIMARY KEY,
            task_id                 TEXT NOT NULL,
            arr_instance_id         TEXT NOT NULL,
            arr_item_id             INTEGER NOT NULL,
            kind                    TEXT NOT NULL DEFAULT 'radarr',
            local_file_path         TEXT NULL,
            arr_file_path           TEXT NULL,
            status                  TEXT NOT NULL,
            import_mode             TEXT NOT NULL,
            arr_command_id          TEXT NULL,
            arr_item_file_id        INTEGER NULL,
            error_code              TEXT NULL,
            error_message           TEXT NULL,
            started_at              TEXT NULL,
            completed_at            TEXT NULL,
            created_at              TEXT NOT NULL,
            updated_at              TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sonarr_playlist_mappings (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE,
            arr_instance_id TEXT NOT NULL,
            series_id       INTEGER NOT NULL,
            series_title    TEXT NOT NULL DEFAULT '',
            season_number   INTEGER NULL,
            playlist_url    TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'draft',
            auto_download   INTEGER NOT NULL DEFAULT 0,
            quality_profile_id INTEGER NULL,
            root_folder_path   TEXT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sonarr_playlist_mapping_items (
            id              TEXT PRIMARY KEY,
            mapping_id      TEXT NOT NULL,
            playlist_index  INTEGER NOT NULL DEFAULT 0,
            video_title     TEXT NOT NULL DEFAULT '',
            video_url       TEXT NOT NULL DEFAULT '',
            video_duration  INTEGER NULL,
            episode_id      INTEGER NULL,
            season_number   INTEGER NULL,
            episode_number  INTEGER NULL,
            episode_title   TEXT NOT NULL DEFAULT '',
            confidence      TEXT NOT NULL DEFAULT 'none',
            action          TEXT NOT NULL DEFAULT 'download',
            download_task_id TEXT NULL,
            status          TEXT NOT NULL DEFAULT 'pending_download',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sonarr_playlist_download_jobs (
            id              TEXT PRIMARY KEY,
            mapping_id      TEXT NOT NULL,
            arr_instance_id TEXT NOT NULL,
            series_id       INTEGER NOT NULL,
            series_title    TEXT NOT NULL,
            season_number   INTEGER NULL,
            playlist_url    TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'queued',
            total_items     INTEGER NOT NULL DEFAULT 0,
            queued_items    INTEGER NOT NULL DEFAULT 0,
            skipped_items   INTEGER NOT NULL DEFAULT 0,
            downloaded_items INTEGER NOT NULL DEFAULT 0,
            imported_items  INTEGER NOT NULL DEFAULT 0,
            failed_items    INTEGER NOT NULL DEFAULT 0,
            current_item_id TEXT NULL,
            task_id         TEXT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            started_at      TEXT NULL,
            completed_at    TEXT NULL,
            error_code      TEXT NULL,
            error_message   TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS sonarr_playlist_download_items (
            id                  TEXT PRIMARY KEY,
            job_id              TEXT NOT NULL,
            mapping_item_id     TEXT NOT NULL,
            playlist_index      INTEGER NOT NULL,
            source_url          TEXT NOT NULL,
            source_title        TEXT NOT NULL,
            episode_id          INTEGER NOT NULL,
            series_id           INTEGER NOT NULL,
            season_number       INTEGER NOT NULL,
            episode_number      INTEGER NOT NULL,
            absolute_episode_number INTEGER NULL,
            episode_title       TEXT NOT NULL,
            status              TEXT NOT NULL,
            confidence          TEXT NOT NULL,
            action              TEXT NOT NULL,
            download_attempts   INTEGER NOT NULL DEFAULT 0,
            import_attempts     INTEGER NOT NULL DEFAULT 0,
            work_dir            TEXT NULL,
            local_download_path TEXT NULL,
            local_stage_dir     TEXT NULL,
            local_stage_file    TEXT NULL,
            arr_stage_path      TEXT NULL,
            sonarr_command_id   INTEGER NULL,
            sonarr_episode_file_id INTEGER NULL,
            sonarr_episode_file_path TEXT NULL,
            error_code          TEXT NULL,
            error_message       TEXT NULL,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            started_at          TEXT NULL,
            downloaded_at       TEXT NULL,
            imported_at         TEXT NULL,
            UNIQUE(job_id, mapping_item_id),
            UNIQUE(job_id, episode_id)
        );

        CREATE TABLE IF NOT EXISTS sonarr_playlist_import_attempts (
            id              TEXT PRIMARY KEY,
            item_id         TEXT NOT NULL,
            job_id          TEXT NOT NULL,
            attempt_number  INTEGER NOT NULL,
            local_stage_file TEXT NOT NULL,
            arr_stage_path  TEXT NOT NULL,
            import_strategy TEXT NOT NULL,
            sonarr_command_id INTEGER NULL,
            status          TEXT NOT NULL,
            error_code      TEXT NULL,
            error_message   TEXT NULL,
            started_at      TEXT NOT NULL,
            completed_at    TEXT NULL
        );
    """)
    _migrate_playlist_mapping_tables(conn)


# ── Migration helpers ───────────────────────────────────────────


def _migrate_playlist_mapping_tables(conn: sqlite3.Connection) -> None:
    # Old tables are empty (no CRUD was ever implemented), so drop & recreate
    conn.execute("DROP TABLE IF EXISTS sonarr_playlist_mappings")
    conn.execute("DROP TABLE IF EXISTS sonarr_playlist_mapping_items")
    conn.executescript("""
        CREATE TABLE sonarr_playlist_mappings (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE,
            arr_instance_id TEXT NOT NULL,
            series_id       INTEGER NOT NULL,
            series_title    TEXT NOT NULL DEFAULT '',
            season_number   INTEGER NULL,
            playlist_url    TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'draft',
            auto_download   INTEGER NOT NULL DEFAULT 0,
            quality_profile_id INTEGER NULL,
            root_folder_path   TEXT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE sonarr_playlist_mapping_items (
            id              TEXT PRIMARY KEY,
            mapping_id      TEXT NOT NULL,
            playlist_index  INTEGER NOT NULL DEFAULT 0,
            video_title     TEXT NOT NULL DEFAULT '',
            video_url       TEXT NOT NULL DEFAULT '',
            video_duration  INTEGER NULL,
            episode_id      INTEGER NULL,
            season_number   INTEGER NULL,
            episode_number  INTEGER NULL,
            episode_title   TEXT NOT NULL DEFAULT '',
            confidence      TEXT NOT NULL DEFAULT 'none',
            action          TEXT NOT NULL DEFAULT 'download',
            download_task_id TEXT NULL,
            status          TEXT NOT NULL DEFAULT 'pending_download',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
    """)


def migrate_from_radarr_tables(conn: sqlite3.Connection) -> None:
    """Migrate existing radarr_* table data into the unified arr_* tables."""
    rows = conn.execute("SELECT * FROM radarr_instances").fetchall()
    for row in rows:
        d = dict(row)
        existing = conn.execute(
            "SELECT id FROM arr_instances WHERE id = ?", (d["id"],)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT OR IGNORE INTO arr_instances
            (id, name, base_url, api_key_encrypted, kind,
             tube_write_path, arr_import_path, host_path_hint,
             default_profile_id, default_quality_profile_id, default_root_folder_path,
             import_mode, enabled, is_default,
             last_test_status, last_test_message, last_test_at,
             last_sync_status, last_sync_message, last_sync_at,
             arr_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'radarr',
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?)""",
            (
                d["id"], d["name"], d["base_url"], d["api_key_encrypted"],
                d.get("tube_write_path", ""), d.get("radarr_import_path", ""),
                d.get("host_path_hint"),
                d.get("default_profile_id"), d.get("default_quality_profile_id"),
                d.get("default_root_folder_path"),
                d.get("import_mode", "move"), d.get("enabled", 1), d.get("is_default", 0),
                d.get("last_test_status"), d.get("last_test_message"),
                d.get("last_test_at"),
                d.get("last_sync_status"), d.get("last_sync_message"),
                d.get("last_sync_at"),
                d.get("radarr_version"), d.get("created_at"), d.get("updated_at"),
            ),
        )

    stats_rows = conn.execute("SELECT * FROM radarr_instance_stats").fetchall()
    for row in stats_rows:
        d = dict(row)
        conn.execute(
            """INSERT OR IGNORE INTO arr_instance_stats
            (arr_instance_id, missing_count, monitored_count, unmonitored_missing_count,
             root_folder_count, queue_count, imports_24h, last_sync_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d["radarr_instance_id"], d["missing_count"], d["monitored_count"],
                d["unmonitored_missing_count"], d["root_folder_count"],
                d["queue_count"], d["imports_24h"], d.get("last_sync_at"),
                d["updated_at"],
            ),
        )


# ── Arr Instance CRUD ────────────────────────────────────────────


def list_arr_instances(kind: ArrKind | None = None) -> list[ArrInstance]:
    with _connect() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM arr_instances WHERE kind = ? ORDER BY name", (kind,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM arr_instances ORDER BY name").fetchall()
    return [_row_to_arr_instance(r) for r in rows]


def get_arr_instance(instance_id: str) -> ArrInstance | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM arr_instances WHERE id = ?", (instance_id,)
        ).fetchone()
    return _row_to_arr_instance(row) if row else None


def get_arr_instance_by_name(name: str) -> ArrInstance | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM arr_instances WHERE name = ?", (name,)
        ).fetchone()
    return _row_to_arr_instance(row) if row else None


def create_arr_instance(data: ArrInstanceCreate) -> ArrInstance:
    import uuid
    now = datetime.now(UTC).isoformat()
    instance_id = str(uuid.uuid4())

    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM arr_instances WHERE name = ?", (data.name,)
        ).fetchone()
        if existing:
            raise ValueError(f"Instance '{data.name}' already exists")

        is_default = data.is_default
        if is_default:
            conn.execute("UPDATE arr_instances SET is_default = 0")

        conn.execute(
            """INSERT INTO arr_instances
            (id, name, base_url, api_key_encrypted, kind,
             tube_write_path, arr_import_path, host_path_hint,
             default_profile_id, default_quality_profile_id, default_root_folder_path,
             import_mode, enabled, is_default,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?)""",
            (
                instance_id, data.name, data.base_url, data.api_key, data.kind,
                data.tube_write_path, data.arr_import_path, data.host_path_hint,
                data.default_profile_id, data.default_quality_profile_id,
                data.default_root_folder_path,
                data.import_mode, int(data.enabled), int(is_default),
                now, now,
            ),
        )

    result = get_arr_instance(instance_id)
    assert result is not None
    return result


def update_arr_instance(instance_id: str, data: ArrInstanceUpdate) -> ArrInstance | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list[Any] = []

    FIELD_MAP = {
        "api_key": "api_key_encrypted",
    }

    for attr in data.model_dump(exclude_none=True):
        db_col = FIELD_MAP.get(attr, attr)
        val = getattr(data, attr)
        if isinstance(val, bool):
            val = int(val)
        fields.append(f"{db_col} = ?")
        vals.append(val)

    if not fields:
        return get_arr_instance(instance_id)

    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(instance_id)

    with _connect() as conn:
        if data.is_default:
            conn.execute("UPDATE arr_instances SET is_default = 0")
        conn.execute(
            f"UPDATE arr_instances SET {', '.join(fields)} WHERE id = ?", vals
        )

    return get_arr_instance(instance_id)


def delete_arr_instance(instance_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM arr_instance_stats WHERE arr_instance_id = ?",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM arr_missing_item_cache WHERE arr_instance_id = ?",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM arr_download_links WHERE arr_instance_id = ?",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM arr_import_attempts WHERE arr_instance_id = ?",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_mappings WHERE arr_instance_id = ?",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_import_attempts WHERE job_id IN (SELECT id FROM sonarr_playlist_download_jobs WHERE arr_instance_id = ?)",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_download_items WHERE job_id IN (SELECT id FROM sonarr_playlist_download_jobs WHERE arr_instance_id = ?)",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_download_jobs WHERE arr_instance_id = ?",
            (instance_id,),
        )
        conn.execute(
            "DELETE FROM arr_instances WHERE id = ?", (instance_id,)
        )


def set_arr_instance_test_result(
    instance_id: str,
    status: str,
    message: str | None,
    version: str | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE arr_instances
            SET last_test_status = ?, last_test_message = ?, last_test_at = ?,
                arr_version = COALESCE(?, arr_version), updated_at = ?
            WHERE id = ?""",
            (status, message, now, version, now, instance_id),
        )


def set_arr_instance_sync_result(
    instance_id: str, status: str, message: str | None = None
) -> None:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE arr_instances
            SET last_sync_status = ?, last_sync_message = ?, last_sync_at = ?,
                updated_at = ?
            WHERE id = ?""",
            (status, message, now, now, instance_id),
        )


def upsert_arr_instance_stats(instance_id: str, stats: dict[str, Any]) -> None:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO arr_instance_stats
            (arr_instance_id, missing_count, monitored_count, unmonitored_missing_count,
             root_folder_count, queue_count, imports_24h, last_sync_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                instance_id,
                stats.get("missing_count", 0),
                stats.get("monitored_count", 0),
                stats.get("unmonitored_missing_count", 0),
                stats.get("root_folder_count", 0),
                stats.get("queue_count", 0),
                stats.get("imports_24h", 0),
                stats.get("last_sync_at"),
                now,
            ),
        )


def get_arr_instance_stats(instance_id: str) -> ArrInstanceStats | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM arr_instance_stats WHERE arr_instance_id = ?",
            (instance_id,),
        ).fetchone()
    return _row_to_arr_stats(row) if row else None


# ── Sonarr Playlist Mapping CRUD ────────────────────────────────


def _row_to_playlist_mapping(row: sqlite3.Row) -> dict:
    return dict(row)


def _row_to_playlist_mapping_item(row: sqlite3.Row) -> dict:
    return dict(row)


def create_playlist_mapping(
    name: str,
    arr_instance_id: str,
    series_id: int,
    series_title: str,
    season_number: int | None,
    playlist_url: str,
    quality_profile_id: int | None = None,
    root_folder_path: str | None = None,
    auto_download: bool = False,
) -> dict:
    import uuid
    now = datetime.now(UTC).isoformat()
    mapping_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sonarr_playlist_mappings
            (id, name, arr_instance_id, series_id, series_title, season_number,
             playlist_url, status, auto_download, quality_profile_id, root_folder_path,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)""",
            (mapping_id, name, arr_instance_id, series_id, series_title, season_number,
             playlist_url, int(auto_download), quality_profile_id, root_folder_path,
             now, now),
        )
    mapping = get_playlist_mapping(mapping_id)
    assert mapping is not None
    return mapping


def get_playlist_mapping(mapping_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sonarr_playlist_mappings WHERE id = ?", (mapping_id,)
        ).fetchone()
        if not row:
            return None
        mapping = _row_to_playlist_mapping(row)
        mapping["items"] = get_playlist_mapping_items(mapping_id)
    return mapping


def list_playlist_mappings(arr_instance_id: str | None = None) -> list[dict]:
    with _connect() as conn:
        if arr_instance_id:
            rows = conn.execute(
                "SELECT * FROM sonarr_playlist_mappings WHERE arr_instance_id = ? ORDER BY created_at DESC",
                (arr_instance_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sonarr_playlist_mappings ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_playlist_mapping(r) for r in rows]


def update_playlist_mapping(mapping_id: str, **kwargs) -> dict | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []
    for key, val in kwargs.items():
        if key == "auto_download":
            val = int(val)
        fields.append(f"{key} = ?")
        vals.append(val)
    if not fields:
        return get_playlist_mapping(mapping_id)
    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(mapping_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE sonarr_playlist_mappings SET {', '.join(fields)} WHERE id = ?",
            vals,
        )
    return get_playlist_mapping(mapping_id)


def delete_playlist_mapping(mapping_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM sonarr_playlist_mapping_items WHERE mapping_id = ?",
            (mapping_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_mappings WHERE id = ?", (mapping_id,)
        )


# ── Playlist Mapping Items CRUD ─────────────────────────────────


def create_playlist_mapping_items(
    mapping_id: str,
    items: list[dict],
) -> list[dict]:
    import uuid
    now = datetime.now(UTC).isoformat()
    created = []
    with _connect() as conn:
        for item in items:
            item_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO sonarr_playlist_mapping_items
                (id, mapping_id, playlist_index, video_title, video_url, video_duration,
                 episode_id, season_number, episode_number, episode_title,
                 confidence, action, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_download', ?, ?)""",
                (
                    item_id, mapping_id,
                    item.get("playlist_index", 0),
                    item.get("video_title", ""),
                    item.get("video_url", ""),
                    item.get("video_duration"),
                    item.get("episode_id"),
                    item.get("season_number"),
                    item.get("episode_number"),
                    item.get("episode_title", ""),
                    item.get("confidence", "none"),
                    item.get("action", "download"),
                    now, now,
                ),
            )
            created.append(item_id)
    return get_playlist_mapping_items(mapping_id)


def get_playlist_mapping_items(mapping_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sonarr_playlist_mapping_items WHERE mapping_id = ? ORDER BY playlist_index",
            (mapping_id,),
        ).fetchall()
    return [_row_to_playlist_mapping_item(r) for r in rows]


def update_playlist_mapping_item(item_id: str, **kwargs) -> dict | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []
    for key, val in kwargs.items():
        fields.append(f"{key} = ?")
        vals.append(val)
    if not fields:
        return None
    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(item_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE sonarr_playlist_mapping_items SET {', '.join(fields)} WHERE id = ?",
            vals,
        )
        row = conn.execute(
            "SELECT * FROM sonarr_playlist_mapping_items WHERE id = ?", (item_id,)
        ).fetchone()
    return _row_to_playlist_mapping_item(row) if row else None


def update_playlist_mapping_items_for_mapping(
    mapping_id: str,
    items: list[dict],
) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        for item in items:
            item_id = item.get("id")
            if item_id:
                fields: list[str] = []
                vals: list = []
                for key in ("playlist_index", "video_title", "video_url", "video_duration",
                            "episode_id", "season_number", "episode_number", "episode_title",
                            "confidence", "action", "status", "download_task_id"):
                    if key in item:
                        fields.append(f"{key} = ?")
                        vals.append(item[key])
                if fields:
                    fields.append("updated_at = ?")
                    vals.append(now)
                    vals.append(item_id)
                    conn.execute(
                        f"UPDATE sonarr_playlist_mapping_items SET {', '.join(fields)} WHERE id = ?",
                        vals,
                    )
    return get_playlist_mapping_items(mapping_id)


# ── Sonarr Playlist Download Job CRUD ────────────────────────────


def _row_to_download_job(row: sqlite3.Row) -> dict:
    return dict(row)


def _row_to_download_item(row: sqlite3.Row) -> dict:
    return dict(row)


def _row_to_import_attempt(row: sqlite3.Row) -> dict:
    return dict(row)


def create_sonarr_playlist_download_job(
    mapping_id: str,
    arr_instance_id: str,
    series_id: int,
    series_title: str,
    season_number: int | None,
    playlist_url: str,
    total_items: int,
    queued_items: int,
    skipped_items: int,
) -> dict:
    import uuid
    now = datetime.now(UTC).isoformat()
    job_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sonarr_playlist_download_jobs
            (id, mapping_id, arr_instance_id, series_id, series_title, season_number,
             playlist_url, status, total_items, queued_items, skipped_items,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?)""",
            (job_id, mapping_id, arr_instance_id, series_id, series_title, season_number,
             playlist_url, total_items, queued_items, skipped_items, now, now),
        )
    return get_sonarr_playlist_download_job(job_id)


def get_sonarr_playlist_download_job(job_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sonarr_playlist_download_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _row_to_download_job(row) if row else None


def list_sonarr_playlist_download_jobs(arr_instance_id: str | None = None) -> list[dict]:
    with _connect() as conn:
        if arr_instance_id:
            rows = conn.execute(
                "SELECT * FROM sonarr_playlist_download_jobs WHERE arr_instance_id = ? ORDER BY created_at DESC",
                (arr_instance_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sonarr_playlist_download_jobs ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_download_job(r) for r in rows]


def update_sonarr_playlist_download_job(job_id: str, **kwargs) -> dict | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []
    for key, val in kwargs.items():
        fields.append(f"{key} = ?")
        vals.append(val)
    if not fields:
        return get_sonarr_playlist_download_job(job_id)
    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(job_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE sonarr_playlist_download_jobs SET {', '.join(fields)} WHERE id = ?",
            vals,
        )
    return get_sonarr_playlist_download_job(job_id)


def delete_sonarr_playlist_download_job(job_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM sonarr_playlist_import_attempts WHERE job_id = ?",
            (job_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_download_items WHERE job_id = ?",
            (job_id,),
        )
        conn.execute(
            "DELETE FROM sonarr_playlist_download_jobs WHERE id = ?", (job_id,)
        )


# ── Sonarr Playlist Download Items CRUD ──────────────────────────


def create_sonarr_playlist_download_items(
    job_id: str,
    items: list[dict],
) -> list[dict]:
    import uuid
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        for item in items:
            item_id = str(uuid.uuid4())
            conn.execute(
                """INSERT OR IGNORE INTO sonarr_playlist_download_items
                (id, job_id, mapping_item_id, playlist_index, source_url, source_title,
                 episode_id, series_id, season_number, episode_number,
                 absolute_episode_number, episode_title,
                 status, confidence, action,
                 download_attempts, import_attempts,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
                (
                    item_id, job_id,
                    item["mapping_item_id"],
                    item["playlist_index"],
                    item["source_url"],
                    item["source_title"],
                    item["episode_id"],
                    item["series_id"],
                    item["season_number"],
                    item["episode_number"],
                    item.get("absolute_episode_number"),
                    item["episode_title"],
                    item["status"],
                    item["confidence"],
                    item["action"],
                    now, now,
                ),
            )
    return get_sonarr_playlist_download_items(job_id)


def get_sonarr_playlist_download_items(job_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sonarr_playlist_download_items WHERE job_id = ? ORDER BY playlist_index",
            (job_id,),
        ).fetchall()
    return [_row_to_download_item(r) for r in rows]


def get_sonarr_playlist_download_item(item_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sonarr_playlist_download_items WHERE id = ?", (item_id,)
        ).fetchone()
    return _row_to_download_item(row) if row else None


def update_sonarr_playlist_download_item(item_id: str, **kwargs) -> dict | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []
    for key, val in kwargs.items():
        fields.append(f"{key} = ?")
        vals.append(val)
    if not fields:
        return get_sonarr_playlist_download_item(item_id)
    fields.append("updated_at = ?")
    vals.append(now)
    vals.append(item_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE sonarr_playlist_download_items SET {', '.join(fields)} WHERE id = ?",
            vals,
        )
    return get_sonarr_playlist_download_item(item_id)


def get_arr_instance_for_job(job_id: str):
    """Get the ArrInstance associated with a sonarr download job."""
    job = get_sonarr_playlist_download_job(job_id)
    if not job:
        return None
    return get_arr_instance(job["arr_instance_id"])


def get_next_queued_sonarr_playlist_item(job_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """SELECT * FROM sonarr_playlist_download_items
            WHERE job_id = ? AND status = 'queued'
            ORDER BY playlist_index LIMIT 1""",
            (job_id,),
        ).fetchone()
    return _row_to_download_item(row) if row else None


def count_sonarr_playlist_items_by_status(job_id: str) -> dict[str, int]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT status, COUNT(*) as cnt FROM sonarr_playlist_download_items
            WHERE job_id = ? GROUP BY status""",
            (job_id,),
        ).fetchall()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = r["cnt"]
    return counts


def recompute_sonarr_playlist_job_summary(job_id: str) -> dict | None:
    counts = count_sonarr_playlist_items_by_status(job_id)
    update_sonarr_playlist_download_job(
        job_id,
        total_items=sum(counts.values()),
        queued_items=counts.get("queued", 0),
        skipped_items=counts.get("skipped_existing", 0) + counts.get("skipped_by_user", 0),
        downloaded_items=counts.get("downloaded", 0),
        imported_items=counts.get("imported", 0),
        failed_items=counts.get("failed_download", 0) + counts.get("failed_stage", 0) + counts.get("failed_import", 0),
    )
    return get_sonarr_playlist_download_job(job_id)


# ── Sonarr Playlist Import Attempts CRUD ─────────────────────────


def create_sonarr_playlist_import_attempt(
    item_id: str,
    job_id: str,
    attempt_number: int,
    local_stage_file: str,
    arr_stage_path: str,
    import_strategy: str,
) -> dict:
    import uuid
    now = datetime.now(UTC).isoformat()
    attempt_id = str(uuid.uuid4())
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sonarr_playlist_import_attempts
            (id, item_id, job_id, attempt_number, local_stage_file, arr_stage_path,
             import_strategy, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'started', ?)""",
            (attempt_id, item_id, job_id, attempt_number, local_stage_file,
             arr_stage_path, import_strategy, now),
        )
    return get_sonarr_playlist_import_attempt(attempt_id)


def get_sonarr_playlist_import_attempt(attempt_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sonarr_playlist_import_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
    return _row_to_import_attempt(row) if row else None


def get_sonarr_playlist_import_attempts_for_item(item_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sonarr_playlist_import_attempts WHERE item_id = ? ORDER BY attempt_number",
            (item_id,),
        ).fetchall()
    return [_row_to_import_attempt(r) for r in rows]


def update_sonarr_playlist_import_attempt(attempt_id: str, **kwargs) -> dict | None:
    now = datetime.now(UTC).isoformat()
    fields: list[str] = []
    vals: list = []
    for key, val in kwargs.items():
        fields.append(f"{key} = ?")
        vals.append(val)
    if not fields:
        return get_sonarr_playlist_import_attempt(attempt_id)
    if "completed_at" in kwargs or "status" in kwargs:
        if "completed_at" not in kwargs:
            fields.append("completed_at = ?")
            vals.append(now)
    with _connect() as conn:
        conn.execute(
            f"UPDATE sonarr_playlist_import_attempts SET {', '.join(fields)} WHERE id = ?",
            vals + [attempt_id],
        )
    return get_sonarr_playlist_import_attempt(attempt_id)
