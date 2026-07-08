# Sonarr Playlist Download Redesign

**Document purpose:** Developer implementation instructions for replacing the current fragile Sonarr playlist download/import implementation with a durable, item-level workflow.

**Scope:** Backend design, database model, API behavior, worker orchestration, import strategy, error handling, testing, and migration guidance.

---

## 1. Architectural ruling

The current implementation tries to run one long yt-dlp playlist process, detect individual file completion by parsing stdout, and import each finished file in daemon callbacks. That approach is too brittle for this feature.

**Replace it with a persistent parent/child job model:**

```text
Playlist mapping
→ parent Sonarr playlist download job
→ one child item per mapped episode
→ download one item at a time
→ stage one file at a time
→ import one episode at a time
→ update item state durably after every step
```

Do **not** rely on per-file daemon callbacks, shared mutable task metadata, or stdout playlist transition parsing to decide when a mapped episode should be imported.

The existing report shows the current flow uses a single playlist process, a per-file callback, mutable `integration_meta`, `imported_files`, temp/home path rewriting, post-download bulk import fallback, and direct `DownloadedEpisodesScan` calls. Those fixes reduce bugs, but they do not remove the underlying race-prone design.

---

## 2. Why the current implementation keeps breaking

The report describes a system where each playlist video is matched to a Sonarr episode and then imported progressively as yt-dlp reports file completion. It also notes that imports are triggered from a daemon-thread callback and that post-download bulk import acts as a fallback.

This causes several bug classes:

| Problem | Why it is fragile | Required replacement |
|---|---|---|
| One long yt-dlp playlist process | Completion boundaries are inferred from stdout and merge messages. yt-dlp output is not a durable job protocol. | Run one child item download at a time. |
| Per-file callback in daemon thread | Import can be lost on process shutdown and competes with task completion. | Persist item state and run imports from a normal worker. |
| Shared `integration_meta` | Shared mutable metadata caused an `itemId` race once already and can cause new races. | Store per-item state in DB rows. |
| `imported_files` path set | Prevents double import only in memory and only for the current process lifetime. | Use item-level import attempt rows and idempotency. |
| Post-download bulk import fallback | Bulk import lacks precise episode context and can reintroduce wrong mapping. | Retry failed items individually. |
| `dest.replace(tube_write_path, arr_import_path, 1)` | Unsafe if prefix is not normalized or path overlaps unexpectedly. | Use a strict relative path mapping function. |
| `time.sleep(3)` verification | Import can take longer or fail asynchronously. | Poll command status and target episode/file state with timeout. |
| Non-contiguous playlist ranges | Current API range validation is single item or contiguous range, while the report mentions comma ranges such as `1,3,5`. | Do not use a single comma-range playlist job. Use one item per child. |

---

## 3. Target behavior

### 3.1 User flow

```text
1. User inspects playlist against a Sonarr series/season.
2. User confirms mapping: each playlist item is mapped to one Sonarr episode or marked skipped.
3. User clicks Download.
4. Backend snapshots the mapping into a parent job and child item rows.
5. Worker processes child items sequentially:
   a. Skip if Sonarr already has that episode file.
   b. Download the playlist entry as an isolated single-video download.
   c. Stage the completed media file in a one-item import folder.
   d. Ask Sonarr to import that one folder/file.
   e. Verify the expected Sonarr episode now has a file.
6. Parent job finishes as completed, partially_completed, failed, cancelled, or paused.
```

### 3.2 Non-goals for this fix

Do not implement:

```text
- Parallel episode downloads.
- Automatic unmapped episode inference without user confirmation.
- Bulk playlist import as the primary path.
- Writing directly into Sonarr's final series library folder.
- Creating Sonarr remote path mappings automatically.
```

---

## 4. Core invariants

These rules must be enforced in code and tests:

1. **Every downloadable playlist item must have a confirmed `episode_id`.**
2. **Each child item downloads into its own working directory.**
3. **Each child item stages into its own import directory.**
4. **Each import request scans exactly one item folder or one item file.**
5. **The Sonarr-visible path is derived only through strict path mapping.**
6. **Parent task state is derived from child item states, not from stdout.**
7. **A failed import never triggers a bulk import of unrelated files.**
8. **Restarting the process must not lose the playlist job state.**
9. **Retry is per item, not per anonymous file path.**
10. **A playlist download may be successful while imports are partially successful.**

---

## 5. Revised data model

Add or replace the current playlist-mapping runtime state with durable job tables.

### 5.1 `sonarr_playlist_download_jobs`

```sql
CREATE TABLE sonarr_playlist_download_jobs (
  id TEXT PRIMARY KEY,
  mapping_id TEXT NOT NULL,
  arr_instance_id TEXT NOT NULL,
  series_id INTEGER NOT NULL,
  series_title TEXT NOT NULL,
  season_number INTEGER NULL,
  playlist_url TEXT NOT NULL,
  status TEXT NOT NULL,
  total_items INTEGER NOT NULL DEFAULT 0,
  queued_items INTEGER NOT NULL DEFAULT 0,
  skipped_items INTEGER NOT NULL DEFAULT 0,
  downloaded_items INTEGER NOT NULL DEFAULT 0,
  imported_items INTEGER NOT NULL DEFAULT 0,
  failed_items INTEGER NOT NULL DEFAULT 0,
  current_item_id TEXT NULL,
  task_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT NULL,
  completed_at TEXT NULL,
  error_code TEXT NULL,
  error_message TEXT NULL
);
```

Allowed `status` values:

```text
queued
running
paused
completed
partially_completed
failed
cancelled
```

### 5.2 `sonarr_playlist_download_items`

```sql
CREATE TABLE sonarr_playlist_download_items (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  mapping_item_id TEXT NOT NULL,
  playlist_index INTEGER NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT NOT NULL,
  episode_id INTEGER NOT NULL,
  series_id INTEGER NOT NULL,
  season_number INTEGER NOT NULL,
  episode_number INTEGER NOT NULL,
  absolute_episode_number INTEGER NULL,
  episode_title TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence TEXT NOT NULL,
  action TEXT NOT NULL,

  download_attempts INTEGER NOT NULL DEFAULT 0,
  import_attempts INTEGER NOT NULL DEFAULT 0,

  work_dir TEXT NULL,
  local_download_path TEXT NULL,
  local_stage_dir TEXT NULL,
  local_stage_file TEXT NULL,
  arr_stage_path TEXT NULL,

  sonarr_command_id INTEGER NULL,
  sonarr_episode_file_id INTEGER NULL,
  sonarr_episode_file_path TEXT NULL,

  error_code TEXT NULL,
  error_message TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT NULL,
  downloaded_at TEXT NULL,
  imported_at TEXT NULL,

  UNIQUE(job_id, mapping_item_id),
  UNIQUE(job_id, episode_id)
);
```

Allowed `status` values:

```text
queued
skipped_existing
downloading
downloaded
staging
import_requested
importing
imported
failed_download
failed_stage
failed_import
cancelled
```

### 5.3 `sonarr_playlist_import_attempts`

```sql
CREATE TABLE sonarr_playlist_import_attempts (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  attempt_number INTEGER NOT NULL,
  local_stage_file TEXT NOT NULL,
  arr_stage_path TEXT NOT NULL,
  import_strategy TEXT NOT NULL,
  sonarr_command_id INTEGER NULL,
  status TEXT NOT NULL,
  error_code TEXT NULL,
  error_message TEXT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NULL
);
```

Allowed `import_strategy` values:

```text
manual_import
DownloadedEpisodesScan
```

---

## 6. API changes

### 6.1 Existing mapping endpoints can stay

Keep these endpoints, but make download create a durable job instead of launching one long playlist process:

```http
POST /api/arr/sonarr/instances/{id}/playlist/inspect
POST /api/arr/sonarr/instances/{id}/playlist/mappings
PATCH /api/arr/sonarr/playlist/mappings/{id}
POST /api/arr/sonarr/playlist/mappings/{id}/auto-map
```

### 6.2 Replace download trigger behavior

```http
POST /api/arr/sonarr/playlist/mappings/{mapping_id}/download
```

Response:

```json
{
  "jobId": "sonarr_playlist_job_123",
  "taskId": "task_abc",
  "status": "queued",
  "statusUrl": "/api/arr/sonarr/playlist/downloads/sonarr_playlist_job_123"
}
```

### 6.3 New status endpoints

```http
GET /api/arr/sonarr/playlist/downloads/{job_id}
GET /api/arr/sonarr/playlist/downloads/{job_id}/items
GET /api/arr/sonarr/playlist/downloads/{job_id}/items/{item_id}
```

Job response shape:

```json
{
  "id": "job_123",
  "mappingId": "mapping_123",
  "taskId": "task_abc",
  "instanceId": "sonarr_main",
  "seriesId": 100,
  "seriesTitle": "The Expanse",
  "seasonNumber": 1,
  "playlistUrl": "https://example.com/playlist",
  "status": "running",
  "summary": {
    "total": 10,
    "queued": 4,
    "skipped": 1,
    "downloaded": 5,
    "imported": 4,
    "failed": 1
  },
  "currentItemId": "item_006",
  "error": null
}
```

### 6.4 Control endpoints

```http
POST /api/arr/sonarr/playlist/downloads/{job_id}/pause
POST /api/arr/sonarr/playlist/downloads/{job_id}/resume
POST /api/arr/sonarr/playlist/downloads/{job_id}/cancel
POST /api/arr/sonarr/playlist/downloads/{job_id}/retry-failed
POST /api/arr/sonarr/playlist/downloads/{job_id}/items/{item_id}/retry
```

---

## 7. Worker design

### 7.1 Worker responsibility

Create a new worker module:

```text
arr/sonarr_playlist_worker.py
```

Main class:

```python
class SonarrPlaylistDownloadWorker:
    def enqueue_from_mapping(self, mapping_id: str) -> SonarrPlaylistDownloadJob: ...
    def run_job(self, job_id: str) -> None: ...
    def run_item(self, job_id: str, item_id: str) -> None: ...
    def pause_job(self, job_id: str) -> None: ...
    def resume_job(self, job_id: str) -> None: ...
    def cancel_job(self, job_id: str) -> None: ...
    def retry_item(self, item_id: str) -> None: ...
```

### 7.2 Job creation algorithm

```python
def enqueue_from_mapping(mapping_id: str):
    mapping = db.get_mapping(mapping_id)
    items = db.get_mapping_items(mapping_id)
    instance = db.get_arr_instance(mapping.arr_instance_id)

    assert instance.kind == "sonarr"
    assert instance.enabled

    sonarr_episodes = sonarr.get_series_episodes(mapping.series_id)
    has_file_by_episode = {ep["id"]: ep.get("hasFile", False) for ep in sonarr_episodes}

    downloadable = []
    skipped = []

    for item in items:
        if item.action != "download":
            skipped.append((item, "skipped_by_user"))
            continue
        if not item.episode_id:
            raise ValidationError("All included playlist entries must be mapped before download")
        if has_file_by_episode.get(item.episode_id):
            skipped.append((item, "skipped_existing"))
            continue
        downloadable.append(item)

    with db.transaction():
        job = db.create_sonarr_playlist_download_job(...)
        for item in downloadable:
            db.create_sonarr_playlist_download_item(status="queued", ...)
        for item, reason in skipped:
            db.create_sonarr_playlist_download_item(status="skipped_existing" or "cancelled", ...)

    task = create_parent_task(job)
    queue_worker(job.id)
    return job
```

### 7.3 Job execution algorithm

```python
def run_job(job_id: str):
    mark_job_running(job_id)

    while True:
        if job_is_cancelled(job_id):
            cancel_current_child(job_id)
            mark_job_cancelled(job_id)
            return

        if job_is_paused(job_id):
            pause_current_child(job_id)
            return

        item = db.next_queued_or_retryable_item(job_id)
        if not item:
            finalize_job_from_items(job_id)
            return

        run_item(job_id, item.id)
        recompute_job_summary(job_id)
```

### 7.4 Item execution algorithm

```python
def run_item(job_id: str, item_id: str):
    item = db.get_item_for_update(item_id)

    if sonarr.get_episode(item.episode_id).get("hasFile"):
        db.update_item(item_id, status="skipped_existing")
        return

    db.update_item(item_id, status="downloading", download_attempts=item.download_attempts + 1)

    try:
        result_file = download_one_playlist_item(job_id, item)
        db.update_item(item_id, status="downloaded", local_download_path=result_file.path)
    except Exception as exc:
        db.update_item(item_id, status="failed_download", error_message=str(exc))
        return

    try:
        staged = stage_one_episode_file(job_id, item_id, result_file)
        db.update_item(item_id, status="staging", local_stage_file=staged.local_path, arr_stage_path=staged.arr_path)
    except Exception as exc:
        db.update_item(item_id, status="failed_stage", error_message=str(exc))
        return

    try:
        import_result = import_one_episode(job_id, item_id, staged)
        db.update_item(item_id, status="imported", sonarr_episode_file_id=import_result.episode_file_id)
    except Exception as exc:
        db.update_item(item_id, status="failed_import", error_message=str(exc))
        return
```

---

## 8. Download strategy

### 8.1 Do not download the whole playlist in one process

Replace this behavior:

```text
one yt-dlp playlist process + file_complete_callback + index_to_episode
```

with this:

```text
one parent job + N isolated child downloads
```

### 8.2 Preferred child download input

Use the playlist entry's direct `video_url` from the playlist inspection result.

Call the existing video download path internally:

```python
result = ytdlp.download_video(
    url=item.source_url,
    output_dir=item_work_dir,
    profile=selected_profile,
    download_format=..., 
    remux_to=..., 
    progress_callback=child_progress_callback,
)
```

Use `--no-playlist` for direct video URLs to avoid accidental playlist expansion.

### 8.3 Fallback child download input

If the inspected playlist entry lacks a direct video URL, call yt-dlp with the original playlist URL and a single `--playlist-items <index>` value.

Do not use a comma-separated range. Process exactly one playlist index per child item.

### 8.4 Output naming

Use a Sonarr-friendly filename for staging, regardless of the original title:

```text
{Series Title} - S{season:02d}E{episode:02d} - {Episode Title} [tube-{playlist_index}].{ext}
```

Examples:

```text
The Expanse - S01E01 - Dulcinea [tube-001].mkv
Farzi - S01E03 - CCFART [tube-003].mp4
```

This improves Sonarr parsing and keeps each item identifiable in logs.

---

## 9. Staging and path mapping

### 9.1 Required staging layout

Do not stage into Sonarr's library/final series folder.

Use:

```text
<tube_write_path>/_tube-explore/sonarr-playlists/<job_id>/<item_id>/
```

Example in Tube Explore container:

```text
/downloads/sonarr/_tube-explore/sonarr-playlists/job_123/item_005/The Expanse - S01E05 - Back to the Butcher [tube-005].mkv
```

Mapped Sonarr-visible path:

```text
/not/same/path/_tube-explore/sonarr-playlists/job_123/item_005/The Expanse - S01E05 - Back to the Butcher [tube-005].mkv
```

### 9.2 Strict mapping function

Replace any string `replace()` path mapping with this function:

```python
def map_tube_path_to_arr_path(local_path: str, tube_write_path: str, arr_import_path: str) -> str:
    local = Path(local_path).resolve(strict=False)
    tube_root = Path(tube_write_path).resolve(strict=False)

    try:
        relative = local.relative_to(tube_root)
    except ValueError:
        raise PathMappingError(
            f"Path {local_path} is outside configured Tube Explore write path {tube_write_path}"
        )

    # Preserve POSIX-style paths for Sonarr containers.
    return posixpath.join(arr_import_path.rstrip("/"), *relative.parts)
```

Rules:

```text
- Reject paths outside tube_write_path.
- Normalize slashes.
- Do not rely on prefix string replacement.
- Do not accept '..' traversal.
- Store both local and Sonarr-visible paths on the item row.
```

---

## 10. Sonarr import strategy

Sonarr's v3 API documentation applies to Sonarr v3 and v4, with some functionality varying by version. Implement the adapter defensively and capability-test the available import paths.

### 10.1 Preferred strategy: manual import when available

If the Sonarr version/API supports explicit manual import with selected episode IDs, use it because it is more deterministic than file-name-only scanning.

Adapter shape:

```python
class SonarrImportAdapter:
    def get_manual_import_candidates(self, path: str, series_id: int) -> list[dict]: ...
    def execute_manual_import(self, candidate, episode_id: int, import_mode: str) -> ImportResult: ...
```

Selection rules:

```text
- Candidate path must equal the staged file path or be inside the staged item folder.
- Candidate must resolve to the expected series.
- Candidate must include the expected episode_id, or be explicitly overrideable to it.
- Reject candidates that map to multiple episodes unless that behavior is explicitly supported later.
```

### 10.2 Fallback strategy: `DownloadedEpisodesScan`

If explicit manual import is not available, use Sonarr's command endpoint with `DownloadedEpisodesScan`, but only against the one-item staging folder.

```python
command = sonarr.create_command(
    name="DownloadedEpisodesScan",
    path=item.arr_stage_dir_or_file
)
```

Important:

```text
- Scan one item folder, not the whole playlist folder.
- Filename must include series title and SxxEyy.
- After command, verify the exact target episode_id now hasFile.
- If target episode still lacks a file, mark failed_import.
```

### 10.3 Verification

Replace fixed `sleep(3)` with polling:

```python
def wait_for_episode_import(episode_id, command_id=None, timeout_seconds=120):
    deadline = now() + timeout_seconds
    while now() < deadline:
        if command_id:
            cmd = sonarr.get_command(command_id)
            if cmd.status in ("failed", "aborted"):
                raise ImportFailed(cmd.message)

        episode = sonarr.get_episode(episode_id)
        if episode.get("hasFile"):
            return episode.get("episodeFile")

        time.sleep(2)

    raise ImportTimeout("Timed out waiting for Sonarr to import episode")
```

---

## 11. Task and SSE event model

### 11.1 Parent task

Create one parent task for the UI:

```python
TaskInfo(
    id=task_id,
    type="playlist",
    status="running",
    integration="sonarr",
    integration_meta={
        "targetType": "episode_playlist",
        "jobId": job_id,
        "instanceId": instance.id,
        "seriesId": series_id,
        "seriesTitle": series_title,
        "seasonNumber": season_number,
        "importStatus": "importing",
        "importedEpisodes": 0,
        "failedEpisodes": 0,
        "totalEpisodes": total,
    }
)
```

### 11.2 Item progress

Expose item progress through `fileProgress` or a new integration status endpoint. Recommended shape:

```json
{
  "index": 5,
  "title": "S01E05 - Back to the Butcher",
  "percent": 71.4,
  "status": "downloading",
  "episodeId": 12345,
  "seasonNumber": 1,
  "episodeNumber": 5,
  "importStatus": "queued"
}
```

### 11.3 SSE events

Emit the following event types:

```text
sonarr_playlist_job_created
sonarr_playlist_job_updated
sonarr_playlist_item_downloading
sonarr_playlist_item_downloaded
sonarr_playlist_item_importing
sonarr_playlist_item_imported
sonarr_playlist_item_failed
sonarr_playlist_job_completed
sonarr_playlist_job_partially_completed
sonarr_playlist_job_failed
```

Do not overload generic `task_updated` alone; keep it for high-level task progress but send integration-specific events for per-episode state.

---

## 12. Pause, resume, cancel, retry

### 12.1 Pause

When pausing a parent job:

```text
- Mark job status = paused.
- If one child download is active, pause/cancel that child through existing yt-dlp task controls.
- Preserve partial files if existing runner supports resume.
- Do not start the next child item.
```

### 12.2 Resume

When resuming:

```text
- Mark job status = queued or running.
- Resume the current failed/paused item if resumable.
- Otherwise continue with the next queued item.
```

### 12.3 Cancel

When cancelling:

```text
- Mark job status = cancelled.
- Cancel current child process.
- Mark queued items = cancelled.
- Do not delete already imported files.
- Delete unimported staging/work files only if safe and inside job-specific folders.
```

### 12.4 Retry failed

Retry only failed child items:

```text
- failed_download -> rerun download and import.
- failed_stage -> restage from existing local_download_path if present; otherwise rerun download.
- failed_import -> retry import from local_stage_file if still present; otherwise restage or redownload.
```

---

## 13. File/module implementation instructions

### 13.1 `arr/routes.py`

Change the playlist download endpoint:

```text
DO:
- Validate mapping readiness.
- Call SonarrPlaylistDownloadWorker.enqueue_from_mapping(mapping_id).
- Return jobId + taskId.

DO NOT:
- Build comma-separated playlist ranges.
- Launch ytdlp.download_playlist directly for the whole mapping.
- Wire per-file callbacks for Sonarr playlist imports.
```

### 13.2 `api.py`

Keep generic task orchestration, but remove Sonarr playlist import-specific callback behavior from `_run_in_background`.

```text
DO:
- Allow child item workers to create/update task progress.
- Keep pause/resume/cancel controls reusable.

DO NOT:
- Import Sonarr playlist files from `_on_file_complete`.
- Run post-download bulk import for Sonarr playlist jobs.
```

### 13.3 `ytdlp.py`

Keep temp/home path normalization because it is useful, but stop using stdout playlist transitions as import triggers.

```text
DO:
- Support single video URL downloads with --no-playlist.
- Support single playlist item download with --playlist-items N.
- Return final media file paths deterministically.

DO NOT:
- Treat playlist transition lines as durable completion events for imports.
```

### 13.4 `arr/path_mapper.py`

Replace `to_arr_path` with strict relative mapping.

```text
DO:
- Map from tube_write_path to arr_import_path using relative paths.
- Reject paths outside tube_write_path.
- Preserve POSIX path output for Arr containers.

DO NOT:
- Use plain string replace.
- Derive staging folders from Sonarr library paths.
```

### 13.5 New `arr/sonarr_playlist_worker.py`

Add parent/child orchestration here. This should be the only place that knows how to run Sonarr playlist jobs.

### 13.6 New `arr/sonarr_importer.py`

Add Sonarr import logic here:

```python
class SonarrEpisodeImporter:
    def stage_file_for_episode(self, item, downloaded_file): ...
    def import_episode(self, item): ...
    def verify_episode_imported(self, episode_id, command_id=None): ...
```

### 13.7 `arr/db.py`

Add DB helpers:

```python
create_sonarr_playlist_download_job(...)
create_sonarr_playlist_download_item(...)
get_next_playlist_download_item(job_id)
update_playlist_download_item_status(...)
recompute_playlist_download_job_summary(job_id)
mark_playlist_download_job_complete(job_id)
create_sonarr_import_attempt(...)
update_sonarr_import_attempt(...)
```

---

## 14. Migration plan

### 14.1 Database migration

Add new job/item/attempt tables without deleting existing mapping tables.

### 14.2 Runtime migration

Existing draft/ready mappings remain valid.

For existing `download_started` mappings:

```text
- Do not attempt automatic conversion.
- Let currently running tasks finish or fail.
- New downloads must use the new job system.
```

### 14.3 Cleanup old code

After new workflow passes tests:

```text
- Remove Sonarr playlist use of `index_to_episode` from integration_meta.
- Remove `imported_files` as the double-import guard for playlist imports.
- Remove post-download bulk import for Sonarr playlists.
- Keep generic single-video Radarr/Sonarr import code if it still works.
```

---

## 15. Test plan

### 15.1 Unit tests

Path mapping:

```text
- maps child path under tube_write_path to arr_import_path
- rejects outside path
- handles trailing slashes
- handles spaces and Unicode titles
- preserves POSIX separators
```

Job creation:

```text
- unmapped item blocks job creation
- skipped item is not downloaded
- already-has-file episode becomes skipped_existing
- duplicate episode mapping rejected
- non-contiguous playlist mapping creates child rows, not comma range
```

Item worker:

```text
- download success -> staging -> import -> imported
- download failure -> failed_download
- stage failure -> failed_stage
- import timeout -> failed_import
- Sonarr already has file before item starts -> skipped_existing
```

State summary:

```text
- all imported -> completed
- imported + skipped_existing -> completed
- imported + failed -> partially_completed
- all failed -> failed
- cancelled mid-job -> cancelled
```

### 15.2 Integration tests with fake Sonarr

Create a fake Sonarr server that supports:

```text
GET /api/v3/episode/{id}
GET /api/v3/series/{id}
POST /api/v3/command
GET /api/v3/command/{id}
```

Scenarios:

```text
- command accepted and episode becomes hasFile
- command accepted but episode never hasFile -> timeout
- command fails -> failed_import
- wrong episode gets file -> failed_import/manual intervention
```

### 15.3 yt-dlp runner tests

Use a fake runner where possible. Do not make tests depend on live YouTube.

Scenarios:

```text
- direct entry URL returns one media file
- playlist URL with single item index returns one media file
- runner returns multiple media files -> reject item as ambiguous
- temp path result is normalized before staging
```

### 15.4 End-to-end local test

Docker-style path mapping:

```yaml
services:
  tube-explore:
    volumes:
      - ./downloads/sonarr:/downloads/sonarr
  fake-sonarr-or-sonarr:
    volumes:
      - ./downloads/sonarr:/not/same/path
```

Test:

```text
1. Create mapping with 3 playlist items.
2. Mark one episode as already having a file.
3. Download two items sequentially.
4. Import each item individually.
5. Confirm job status completed, imported=2, skipped=1.
```

---

## 16. Acceptance criteria

The redesign is complete when:

```text
1. Sonarr playlist download no longer uses one long playlist process for import orchestration.
2. Each mapped episode has a durable child item row.
3. Process restart does not lose job/item/import state.
4. Non-contiguous playlist selections work without comma range hacks.
5. Each child download produces at most one primary media file.
6. Each staged import folder contains exactly one episode file.
7. Path mapping is strict and rejects paths outside tube_write_path.
8. Imports are verified by checking the expected Sonarr episode_id.
9. Partial success is represented accurately in API and UI.
10. Retry failed items works without reimporting already imported items.
11. Pause/resume/cancel operate on the parent job and current child item.
12. No bulk import fallback runs for Sonarr playlist jobs.
13. Tests cover path mapping, item state transitions, import failures, restart recovery, and skipped existing episodes.
```

---

## 17. Developer checklist

Implement in this order:

```text
[ ] Add database migration for job/item/import attempt tables.
[ ] Add DB helper methods and tests.
[ ] Add strict path mapper and tests.
[ ] Add SonarrEpisodeImporter with fake-Sonarr tests.
[ ] Add SonarrPlaylistDownloadWorker with fake download runner tests.
[ ] Change playlist mapping download endpoint to enqueue a job.
[ ] Add job/item status/control endpoints.
[ ] Update SSE events for per-item state.
[ ] Remove Sonarr playlist import from `_on_file_complete` path.
[ ] Remove Sonarr playlist post-download bulk import fallback.
[ ] Update frontend to read job/item status endpoints.
[ ] Run end-to-end Docker path mapping test.
```

---

## 18. What not to do

```text
Do not fix this by adding more locks around integration_meta.
Do not fix this by adding more regexes for yt-dlp stdout.
Do not run multiple daemon import callbacks for playlist files.
Do not scan a folder containing multiple mapped episode files.
Do not call DownloadedEpisodesScan before the file is staged and fsync/close is complete.
Do not use Sonarr library root as the Tube Explore staging root.
Do not mark the parent task completed until import states are finalized.
```

---

## 19. Reference notes

- The current report describes the desired mapping/download/import workflow and shows that the implementation currently relies on per-file callbacks, mutable task metadata, path mapping, `DownloadedEpisodesScan`, and fallback bulk import.
- Sonarr API docs state that the v3 API docs apply to v3 and v4, with some functionality varying by application version.
- Servarr Docker guidance recommends consistent path layouts and separate download/import and library folders; bad path mapping and permissions are common import-failure causes.
