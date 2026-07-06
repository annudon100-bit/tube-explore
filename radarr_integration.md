# Tube Explore Radarr Integration Design v2

**Status:** Updated after UI mockup review  
**Date:** 2026-07-06  
**Scope:** Backend and UI design for connecting one Tube Explore service to multiple Radarr instances, showing missing movies, launching Radarr-linked downloads, importing completed files into Radarr, and reflecting Radarr import state in Downloads and Files.

## 1. Executive summary

Tube Explore should support any number of Radarr instances. Each instance has its own base URL, API key, default quality/download settings, import mode, and path mapping. The integration model is **download into a Tube Explore staging directory, translate the finished file path into the path visible to the target Radarr container, then ask that Radarr instance to import the file**.

The feature is not a file-upload flow. Radarr expects files to exist on disk where Radarr can see them. Tube Explore remains the downloader; Radarr remains the movie library/import authority.

The updated UI mockups require support for these pages:

1. Radarr Instances overview
2. Add/Edit Radarr Instance
3. Radarr Settings
4. Missing Movies for a selected instance
5. Radarr-context Search
6. Downloads with Radarr import status
7. Files with Radarr-imported/external file state

The design below extends the current Tube Explore API while preserving the existing search, download, task, profile, settings, health, and file capabilities from the latest attached OpenAPI spec.

## 2. Sources and assumptions

### 2.1 Source references

- **[S1] Tube Explore API spec:** attached `openapi(3).json`, OpenAPI 3.1.0, API version 1.0.0.
- **[S2] Radarr API docs:** Radarr OpenAPI documentation at `https://radarr.video/docs/api/`.
- **[S3] Servarr/Radarr remote path mapping guidance:** remote path mapping is used when an external client reports paths differently than Radarr sees them.
- **[S4] Radarr manual import limitation:** Radarr manual import requires the movie to already exist in Radarr.

### 2.2 Current Tube Explore API capabilities used by this design

The current API already supports:

- media search through `GET /api/search`
- metadata inspection through `GET /api/metadata`
- video download creation through `POST /api/download/video`
- playlist download creation through `POST /api/download/playlist`
- task polling through `GET /api/tasks/{task_id}`
- task lifecycle controls through cancel, pause, resume, and retry endpoints
- global task event streaming through `GET /api/events`
- profile CRUD through `/api/profiles`
- settings through `/api/settings`
- health/readiness through `/api/health` and `/api/ready`
- downloaded file listing through `GET /api/files`
- file download through `GET /api/files/{file_id}/download`
- file storage stats through `GET /api/files/stats`

### 2.3 Important current gaps exposed by the mockups

The mockups require a few capabilities not present in the current API spec:

- task list endpoint for the Downloads page
- task deletion/removal endpoint for cleanup actions
- task logs/activity endpoint for details panels
- file delete endpoint for Files page destructive action
- file detail endpoint for Files side panel
- optional file open/reveal action if running in a local desktop environment
- Radarr-specific endpoints and schemas

These are added in this design.

## 3. Product behavior

### 3.1 High-level flow

```text
User configures one or more Radarr instances
-> Tube Explore fetches missing movies from a selected instance
-> User picks a missing movie
-> User searches Tube Explore or pastes a source URL
-> Tube Explore creates a normal video download task with Radarr context
-> Tube Explore downloads to the configured Tube Explore write path
-> Tube Explore maps the local file path to the Radarr-visible import path
-> Tube Explore asks the selected Radarr instance to import the file
-> Downloads and Files pages show download/import state
```

### 3.2 Multiple Radarr instances

A single Tube Explore service can connect to multiple Radarr instances. This supports common setups such as:

- `Main Radarr` for regular movies
- `4K Radarr` for UHD/4K movies
- `Kids Radarr` for a separate library
- separate remote Radarr deployments

Each instance is isolated for:

- API credentials
- base URL
- path mapping
- root folders
- quality profiles
- missing movie sync
- queue/status sync
- import attempts
- default profile/import rules

A Radarr-linked task must always carry a `radarrInstanceId`; movie IDs are not globally unique across instances.

## 4. UI coverage matrix

| Page | Purpose | Backend support required |
|---|---|---|
| Radarr Instances overview | Manage all connected instances, view aggregate stats, status, missing counts, imports, last sync | Instance list, instance stats, sync status, aggregate summary, sync-now action |
| Add/Edit Radarr Instance | Configure URL/API key/path mapping/defaults/test connection | Instance create/update, test connection, path validation, root folder/profile lookup |
| Radarr Settings | Manage instances, defaults, path mappings, import rules, notifications, advanced settings | Settings endpoints, root folder list, quality profile list, sync history, queue, test results |
| Missing Movies | Work queue for a selected Radarr instance | Missing movies endpoint, filters, sort, instance details, open in Radarr, search/paste actions |
| Radarr-context Search | Search source media for one target missing movie | Existing search plus Radarr context, download-for-Radarr endpoint, paste URL action |
| Downloads with Radarr status | Show download state and Radarr import state together | Task list, task integration metadata, import attempts, retry import, side panel details |
| Files with Radarr-imported state | Show local, imported, importing, failed, and external/moved files | Extended files schema, file detail, external/import state, Radarr open action |

## 5. Architecture overview

### 5.1 Components

```text
UI pages
  -> Tube Explore REST API
    -> RadarrInstanceService
    -> RadarrClient
    -> RadarrMissingMovieService
    -> RadarrDownloadCoordinator
    -> existing DownloadService / TaskService
    -> RadarrImportWorker
    -> FileRegistryService
    -> Event/SSE publisher
  -> Radarr API
```

### 5.2 New backend services

#### RadarrClient

Thin HTTP client for one Radarr instance. It handles API key auth, timeouts, redaction, and response normalization.

Required methods:

```ts
getPing(): Promise<void>
getSystemStatus(): Promise<RadarrSystemStatus>
getRootFolders(): Promise<RadarrRootFolder[]>
getQualityProfiles(): Promise<RadarrQualityProfile[]>
getMissingMovies(params): Promise<RadarrMissingMoviePage>
getMovie(movieId: number): Promise<RadarrMovie>
getQueue(): Promise<RadarrQueuePage>
getManualImportCandidates(folder: string, movieId?: number): Promise<RadarrManualImportCandidate[]>
createMovieImport(request): Promise<RadarrImportResult>
createManualImport(request): Promise<RadarrImportResult>
createCommand(request): Promise<RadarrCommandResponse>
```

#### RadarrInstanceService

Owns instance CRUD, encrypted API key storage, testing, and path mapping.

#### RadarrMissingMovieService

Fetches, normalizes, filters, sorts, and caches missing movies for a selected instance.

#### RadarrDownloadCoordinator

Creates Radarr-linked downloads by wrapping the existing video download flow. It controls output directories and prevents arbitrary path overrides.

#### RadarrImportWorker

Runs after a linked download completes. It selects the media file, translates paths, imports to Radarr, records status, and emits events.

#### RadarrSyncWorker

Refreshes instance health, missing counts, root folders, queue state, and recent import stats. This supports the Radarr overview and settings pages.

## 6. Path mapping design

### 6.1 Why path mapping is required

Tube Explore and Radarr may run in different Docker containers with different mount paths for the same host directory.

Example:

```text
Host path:
  /mnt/media/radarr-imports/main

Tube Explore container path:
  /downloads/radarr-main

Radarr container path:
  /data/imports/tube-explore/radarr-main
```

Tube Explore writes a completed file to:

```text
/downloads/radarr-main/27205-Inception-2010/Inception (2010).mp4
```

Radarr must import the same physical file using:

```text
/data/imports/tube-explore/radarr-main/27205-Inception-2010/Inception (2010).mp4
```

### 6.2 Stored path fields

Each Radarr instance stores:

```ts
{
  tubeWritePath: string;       // path visible to Tube Explore
  radarrImportPath: string;    // same physical directory, path visible to Radarr
  hostPathHint?: string;       // optional display-only host path
}
```

### 6.3 Translation algorithm

```ts
function toRadarrPath(localPath: string, instance: RadarrInstance): string {
  const localRoot = normalizeAbsolute(instance.tubeWritePath)
  const radarrRoot = normalizeAbsolute(instance.radarrImportPath)

  if (!isInside(localPath, localRoot)) {
    throw new IntegrationError('LOCAL_PATH_OUTSIDE_INSTANCE_WRITE_PATH')
  }

  const relative = relativePath(localRoot, localPath)
  return joinPosix(radarrRoot, relative)
}
```

Rules:

- generated task output must be under `tubeWritePath`
- user-provided `downloadPathOverride` is not accepted for Radarr-linked downloads
- relative segments such as `..` are rejected
- paths are stored normalized
- each import attempt records both local and Radarr-visible paths

### 6.4 Path validation levels

| Level | Validation | Required before save? |
|---|---|---|
| URL/API key | `GET /ping` and system status | Yes |
| Local write path | create/write/delete sentinel file under `tubeWritePath` | Yes |
| Radarr root folders | fetch Radarr root folders | Yes |
| Radarr import path visibility | best-effort manual import/filesystem probe | Warning allowed |
| Full import proof | actual completed file import | Runtime only |

## 7. Data model

### 7.1 `radarr_instances`

```sql
CREATE TABLE radarr_instances (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  api_key_encrypted TEXT NOT NULL,
  tube_write_path TEXT NOT NULL,
  radarr_import_path TEXT NOT NULL,
  host_path_hint TEXT NULL,
  default_profile_id TEXT NULL,
  default_quality_profile_id INTEGER NULL,
  default_root_folder_path TEXT NULL,
  import_mode TEXT NOT NULL DEFAULT 'move',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  last_test_status TEXT NULL,
  last_test_message TEXT NULL,
  last_test_at TIMESTAMP NULL,
  last_sync_status TEXT NULL,
  last_sync_message TEXT NULL,
  last_sync_at TIMESTAMP NULL,
  radarr_version TEXT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
```

Constraints:

- `name` unique
- only one default instance at a time
- `import_mode` is `move` or `copy`
- `tube_write_path` and `radarr_import_path` must be absolute
- API key is never returned in full

### 7.2 `radarr_instance_stats`

Cached per-instance metrics for the overview page.

```sql
CREATE TABLE radarr_instance_stats (
  radarr_instance_id TEXT PRIMARY KEY,
  missing_count INTEGER NOT NULL DEFAULT 0,
  monitored_count INTEGER NOT NULL DEFAULT 0,
  unmonitored_missing_count INTEGER NOT NULL DEFAULT 0,
  root_folder_count INTEGER NOT NULL DEFAULT 0,
  queue_count INTEGER NOT NULL DEFAULT 0,
  imports_24h INTEGER NOT NULL DEFAULT 0,
  last_sync_at TIMESTAMP NULL,
  updated_at TIMESTAMP NOT NULL
);
```

### 7.3 `radarr_missing_movie_cache`

Optional short-lived cache for missing movie pages and search/filter performance.

```sql
CREATE TABLE radarr_missing_movie_cache (
  radarr_instance_id TEXT NOT NULL,
  movie_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  year INTEGER NULL,
  tmdb_id INTEGER NULL,
  imdb_id TEXT NULL,
  monitored BOOLEAN NULL,
  has_file BOOLEAN NULL,
  quality_profile_id INTEGER NULL,
  quality_profile_name TEXT NULL,
  root_folder_path TEXT NULL,
  movie_path TEXT NULL,
  poster_url TEXT NULL,
  overview TEXT NULL,
  cached_at TIMESTAMP NOT NULL,
  PRIMARY KEY (radarr_instance_id, movie_id)
);
```

### 7.4 `radarr_download_links`

Links a Tube Explore task to one Radarr movie in one Radarr instance.

```sql
CREATE TABLE radarr_download_links (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL UNIQUE,
  radarr_instance_id TEXT NOT NULL,
  radarr_movie_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  year INTEGER NULL,
  tmdb_id INTEGER NULL,
  imdb_id TEXT NULL,
  source_url TEXT NOT NULL,
  local_staging_dir TEXT NOT NULL,
  radarr_staging_dir TEXT NOT NULL,
  local_final_file_path TEXT NULL,
  radarr_final_file_path TEXT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
```

### 7.5 `radarr_import_attempts`

```sql
CREATE TABLE radarr_import_attempts (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  radarr_instance_id TEXT NOT NULL,
  radarr_movie_id INTEGER NOT NULL,
  local_file_path TEXT NULL,
  radarr_file_path TEXT NULL,
  status TEXT NOT NULL,
  import_mode TEXT NOT NULL,
  radarr_command_id TEXT NULL,
  radarr_movie_file_id INTEGER NULL,
  error_code TEXT NULL,
  error_message TEXT NULL,
  started_at TIMESTAMP NULL,
  completed_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
```

Status values:

```text
pending
waiting_for_download
mapping_path
scanning
candidate_selected
importing
imported
failed
cancelled
```

### 7.6 File schema extensions

Extend file records to support the Files with Radarr state page.

```ts
FileInfo {
  storageState?: 'local' | 'external_imported' | 'missing' | 'importing' | 'import_failed'
  externalSystem?: 'radarr'
  externalInstanceId?: string
  externalInstanceName?: string
  externalMovieId?: number
  externalMovieTitle?: string
  externalPath?: string
  localPath?: string
  downloadable?: boolean
  importStatus?: 'none' | 'waiting_for_import' | 'importing' | 'imported' | 'failed'
  importMode?: 'move' | 'copy'
  importedAt?: string
}
```

If import mode is `move`, Radarr may move the file out of Tube Explore's local staging area. The Files page should still display an audit row, but `downloadable` may be false unless the final Radarr path is also visible to Tube Explore.

## 8. API design

### 8.1 Radarr instance APIs

```http
GET    /api/radarr/instances
POST   /api/radarr/instances
GET    /api/radarr/instances/{instanceId}
PATCH  /api/radarr/instances/{instanceId}
DELETE /api/radarr/instances/{instanceId}
POST   /api/radarr/instances/{instanceId}/test
POST   /api/radarr/instances/{instanceId}/sync
POST   /api/radarr/instances/{instanceId}/set-default
```

Instance response:

```ts
RadarrInstanceResponse {
  id: string
  name: string
  baseUrl: string
  apiKeyPreview: string
  tubeWritePath: string
  radarrImportPath: string
  hostPathHint?: string
  defaultProfileId?: string
  defaultQualityProfileId?: number
  defaultRootFolderPath?: string
  importMode: 'move' | 'copy'
  enabled: boolean
  isDefault: boolean
  status: 'connected' | 'warning' | 'error' | 'disabled' | 'unknown'
  healthMessage?: string
  radarrVersion?: string
  lastSyncAt?: string
  lastTestAt?: string
  stats?: RadarrInstanceStats
}
```

Create/update request:

```ts
RadarrInstanceUpsertRequest {
  name: string
  baseUrl: string
  apiKey?: string
  tubeWritePath: string
  radarrImportPath: string
  hostPathHint?: string
  defaultProfileId?: string
  defaultQualityProfileId?: number
  defaultRootFolderPath?: string
  importMode: 'move' | 'copy'
  enabled: boolean
}
```

Test response:

```ts
RadarrInstanceTestResponse {
  ok: boolean
  canConnect: boolean
  apiKeyValid: boolean
  tubeWritePathWritable: boolean
  radarrRootFoldersLoaded: boolean
  radarrImportPathVisible?: boolean
  radarrVersion?: string
  warnings: string[]
  errors: string[]
}
```

### 8.2 Radarr settings/support APIs

```http
GET /api/radarr/summary
GET /api/radarr/instances/{instanceId}/root-folders
GET /api/radarr/instances/{instanceId}/quality-profiles
GET /api/radarr/instances/{instanceId}/queue
GET /api/radarr/instances/{instanceId}/sync-history
GET /api/radarr/instances/{instanceId}/test-results
```

Summary response supports the Radarr Instances overview page:

```ts
RadarrSummaryResponse {
  totalInstances: number
  activeConnections: number
  missingMovies: number
  monitoredMovies: number
  imports24h: number
  lastSyncAt?: string
  instanceStatuses: Record<string, number>
}
```

### 8.3 Missing movies APIs

```http
GET /api/radarr/instances/{instanceId}/missing
```

Query parameters:

```text
limit
offset
search
monitored = all | monitored | unmonitored
qualityProfileId
rootFolderPath
sortBy = title | year | qualityProfile | rootFolder | status
sortOrder = asc | desc
```

Response:

```ts
RadarrMissingMovieListResponse {
  items: RadarrMissingMovie[]
  total: number
  instance: RadarrInstanceBrief
}

RadarrMissingMovie {
  instanceId: string
  movieId: number
  title: string
  year?: number
  tmdbId?: number
  imdbId?: string
  monitored?: boolean
  hasFile?: boolean
  qualityProfileId?: number
  qualityProfileName?: string
  rootFolderPath?: string
  moviePath?: string
  posterUrl?: string
  overview?: string
  radarrUrl?: string
  localWorkflowStatus?: 'not_started' | 'downloading' | 'importing' | 'imported' | 'failed'
  linkedTaskId?: string
}
```

### 8.4 Radarr-linked download APIs

From selected search result:

```http
POST /api/radarr/instances/{instanceId}/movies/{movieId}/download-from-search
```

From pasted URL:

```http
POST /api/radarr/instances/{instanceId}/movies/{movieId}/download-from-url
```

Request:

```ts
RadarrMovieDownloadRequest {
  url: string
  profileId?: string
  downloadQualityMode?: QualityMode
  downloadQualityValue?: number
  downloadFormat?: string
  formatType?: FormatType
  remuxTo?: string
  embedMetadata?: boolean
  embedThumbnail?: boolean
  subtitles?: boolean
  subtitleLangs?: string
}
```

Response reuses the existing task-created pattern:

```ts
DownloadTaskCreatedResponse {
  taskId: string
  status: 'pending'
  statusUrl: string
}
```

Important rule: these endpoints ignore any client-supplied output path and use instance-controlled staging paths.

### 8.5 Import status APIs

```http
GET  /api/radarr/tasks/{taskId}
POST /api/radarr/tasks/{taskId}/import/retry
POST /api/radarr/tasks/{taskId}/import/cancel
```

Response:

```ts
RadarrTaskIntegrationResponse {
  taskId: string
  radarrInstanceId: string
  radarrInstanceName: string
  radarrMovieId: number
  title: string
  year?: number
  downloadStatus: string
  importStatus: string
  importMode: 'move' | 'copy'
  localFilePath?: string
  radarrFilePath?: string
  radarrMovieUrl?: string
  commandId?: string
  errorCode?: string
  errorMessage?: string
  startedAt?: string
  completedAt?: string
}
```

### 8.6 Task API changes

The Downloads with Radarr page requires task list and integration fields.

Add:

```http
GET    /api/tasks
DELETE /api/tasks/{task_id}
GET    /api/tasks/{task_id}/logs
GET    /api/tasks/{task_id}/files
```

`GET /api/tasks` query parameters:

```text
limit
offset
status
search
type
integration = all | none | radarr
sortBy = created_at | title | status | progress
sortOrder = asc | desc
```

Extend `TaskResponse`:

```ts
TaskResponse {
  integration?: {
    type: 'radarr'
    instanceId: string
    instanceName: string
    movieId: number
    movieTitle: string
    movieYear?: number
    importStatus: 'none' | 'waiting_for_download' | 'waiting_for_import' | 'mapping_path' | 'scanning' | 'importing' | 'imported' | 'failed'
    importMode?: 'move' | 'copy'
    importError?: string
    radarrPath?: string
    localPath?: string
  }
}
```

### 8.7 File API changes

The Files with Radarr page requires filtering by source/integration/status and file detail panels.

Extend:

```http
GET    /api/files
GET    /api/files/{file_id}
DELETE /api/files/{file_id}
POST   /api/files/{file_id}/reveal
```

Additional `GET /api/files` query parameters:

```text
source
integration = all | none | radarr
storageState = local | external_imported | importing | import_failed | missing
status
```

`POST /api/files/{file_id}/reveal` is optional and should only be enabled for local deployments that can reveal a folder. For a normal web deployment, return `409` or omit this action.

### 8.8 SSE event changes

Current `GET /api/events` should emit Radarr integration updates in addition to task lifecycle events.

New event types:

```text
radarr_instance_updated
radarr_sync_started
radarr_sync_completed
radarr_sync_failed
radarr_import_created
radarr_import_updated
radarr_import_completed
radarr_import_failed
```

Event payload example:

```json
{
  "type": "radarr_import_updated",
  "taskId": "task_abc",
  "radarrInstanceId": "main-radarr",
  "movieId": 27205,
  "importStatus": "scanning",
  "message": "Scanning Radarr import folder"
}
```

## 9. Page-by-page backend support

### 9.1 Radarr Instances overview

Required features:

- aggregate stats: total instances, active connections, total missing, monitored movies, imports in last 24h, last sync
- instance table with name, URL, status, version, missing count, monitored count, paths, last sync, actions
- search/filter instances
- sync now per instance
- edit instance
- add instance
- setup guide/help panels

Backend endpoints:

```text
GET  /api/radarr/summary
GET  /api/radarr/instances
POST /api/radarr/instances/{id}/sync
POST /api/radarr/instances/{id}/test
```

### 9.2 Add/Edit Radarr Instance

Required features:

- name/base URL/API key
- Tube Explore write path
- Radarr import path
- host path hint
- default quality profile
- import mode
- enable/disable
- test connection checklist
- path mapping explanation

Backend endpoints:

```text
POST  /api/radarr/instances
PATCH /api/radarr/instances/{id}
POST  /api/radarr/instances/{id}/test
GET   /api/radarr/instances/{id}/quality-profiles
GET   /api/radarr/instances/{id}/root-folders
```

### 9.3 Radarr Settings

Required features:

- tabs: instances, defaults, path mappings, import rules, notifications, advanced
- instance cards with path verification and sync status
- instance overview
- root folder list
- quality profiles
- queue
- sync history
- test results
- common issue guidance

Backend endpoints:

```text
GET /api/radarr/instances
GET /api/radarr/instances/{id}
GET /api/radarr/instances/{id}/root-folders
GET /api/radarr/instances/{id}/quality-profiles
GET /api/radarr/instances/{id}/queue
GET /api/radarr/instances/{id}/sync-history
GET /api/radarr/instances/{id}/test-results
```

### 9.4 Missing Movies

Required features:

- selected instance details panel
- connection status/version/root folders/missing counts
- missing movie list
- filters and sort
- actions: Search, Paste URL, Open in Radarr, More
- context-preserving navigation to Radarr search page

Backend endpoints:

```text
GET  /api/radarr/instances/{id}/missing
GET  /api/radarr/instances/{id}
POST /api/radarr/instances/{id}/sync
```

### 9.5 Radarr-context Search

Required features:

- target movie context header
- instance and path mapping status
- search results
- filters: source, quality, file type, upload date
- action: Download for Radarr
- action: Paste URL

Backend endpoints:

```text
GET  /api/search
GET  /api/metadata
POST /api/radarr/instances/{id}/movies/{movieId}/download-from-search
POST /api/radarr/instances/{id}/movies/{movieId}/download-from-url
```

### 9.6 Downloads with Radarr status

Required features:

- task list
- integration column
- download status and Radarr import status separated
- side panel with task details, Radarr details, paths, import mode, retry import, open in Radarr
- statuses: imported, waiting for import, importing, import failed, path not accessible

Backend endpoints:

```text
GET  /api/tasks
GET  /api/tasks/{id}
GET  /api/radarr/tasks/{taskId}
POST /api/radarr/tasks/{taskId}/import/retry
POST /api/tasks/{id}/pause
POST /api/tasks/{id}/resume
POST /api/tasks/{id}/cancel
POST /api/tasks/{id}/retry
GET  /api/events
```

### 9.7 Files with Radarr-imported state

Required features:

- storage stats including imported-to-Radarr and external/not-local files
- file list with integration and status
- right detail panel with Radarr information, local file information, final state
- action: Open in Radarr
- action: Open containing folder only if local
- delete file action, with restrictions for Radarr-managed external files

Backend endpoints:

```text
GET    /api/files
GET    /api/files/{id}
DELETE /api/files/{id}
GET    /api/files/stats
```

## 10. Import workflow details

### 10.1 Trigger

When a Radarr-linked download task transitions to `completed`, enqueue a Radarr import job.

### 10.2 File selection

The worker selects the primary movie file:

- include video files only
- exclude thumbnails, subtitles, temp files, fragments, JSON, metadata sidecars
- reject multiple primary video files for v1
- reject playlist tasks for v1 unless the future movie mapping feature is implemented

### 10.3 Import strategy

Preferred sequence:

```text
1. Translate local file path to Radarr-visible path.
2. Query Radarr import candidates for the folder/file.
3. Select candidate matching the target movie ID.
4. Submit movie/manual import with importMode = move or copy.
5. Record command/result identifiers when Radarr returns them.
6. Refresh movie/file state if needed.
```

Fallback:

```text
If candidate scanning fails but the file path is known, submit direct movie import if supported by the Radarr instance/version.
```

### 10.4 Import status semantics

| Download status | Import status | User-facing status |
|---|---|---|
| running | waiting_for_download | Downloading |
| completed | waiting_for_import | Waiting for Radarr import |
| completed | scanning/importing | Importing to Radarr |
| completed | imported | Imported |
| completed | failed | Import failed |
| failed/cancelled | none/cancelled | Download failed/cancelled |

For Radarr tasks, the Downloads page should show both the base task status and the import status. A Radarr task is not fully successful until import status is `imported`.

## 11. Error handling

### 11.1 Error codes

```text
RADARR_CONNECTION_FAILED
RADARR_AUTH_FAILED
RADARR_INSTANCE_DISABLED
RADARR_MOVIE_NOT_FOUND
RADARR_MOVIE_ALREADY_HAS_FILE
RADARR_PATH_MAPPING_INVALID
LOCAL_WRITE_PATH_NOT_WRITABLE
LOCAL_PATH_OUTSIDE_INSTANCE_WRITE_PATH
RADARR_IMPORT_PATH_NOT_VISIBLE
RADARR_IMPORT_NO_CANDIDATES
RADARR_IMPORT_AMBIGUOUS_CANDIDATES
RADARR_IMPORT_REJECTED
RADARR_IMPORT_COMMAND_FAILED
RADARR_UNSUPPORTED_RESPONSE
```

### 11.2 User-facing recovery actions

| Error | UI action |
|---|---|
| Auth failed | Edit API key, test connection |
| Local path not writable | Edit Tube Explore write path |
| Radarr path not visible | Edit Radarr import path/path mapping |
| No import candidates | Open Radarr, retry import, show paths |
| Ambiguous candidates | Open task details, choose candidate in future release |
| Movie already has file | Mark imported or skip import |
| Import rejected | Show Radarr error and retry |

## 12. Security and privacy

- Store API keys encrypted at rest.
- Return only `apiKeyPreview`, never full API keys.
- Redact API keys from logs, task params, traces, SSE events, and error messages.
- Only allow `http` and `https` base URLs.
- Apply request timeouts and bounded response sizes to Radarr calls.
- Do not follow redirects to a different host.
- Prevent SSRF-sensitive destinations where applicable for server-side deployments.
- Reject path traversal in generated output paths.
- Validate that Radarr-linked task outputs remain inside the configured instance write path.
- Treat file delete operations carefully when a file has been moved/imported to Radarr.

## 13. Notifications and eventing

The settings mockup includes a Notifications tab. V1 should support internal UI/SSE notifications only:

- instance connection warning
- sync failed
- import succeeded
- import failed
- path mapping warning

External notifications are a future extension.

## 14. Defaults and import rules

### 14.1 Defaults

Per instance:

- default Tube Explore profile
- default Radarr quality profile ID
- default root folder path
- default import mode
- enabled/disabled state

Global Radarr defaults may provide fallback values for new instances.

### 14.2 Import rules

V1 rules:

- Radarr imports are single movie only.
- Playlist downloads are not eligible for Radarr movie import.
- Imported file must be a video file.
- Import path must be mapped.
- Download output directory is controlled by RadarrDownloadCoordinator.

Future rules:

- minimum quality threshold
- max file size
- prefer remux target
- optional copy instead of move by source/profile
- manual candidate selection

## 15. Open-in-Radarr URL construction

Store or derive a Radarr web URL for:

- instance root: `{baseUrl}`
- movie details: `{baseUrl}/movie/{title-slug-or-radarr-route}` if reliably derivable

Because Radarr UI routing may vary, backend should prefer values returned by Radarr where available. Otherwise, open the base instance URL or movie search URL as a safe fallback.

## 16. Migration plan

### 16.1 Database migrations

1. Add `radarr_instances`.
2. Add `radarr_instance_stats`.
3. Add `radarr_missing_movie_cache`.
4. Add `radarr_download_links`.
5. Add `radarr_import_attempts`.
6. Extend task/file persistence with optional integration fields or create views joining the new Radarr tables.

### 16.2 API migration

1. Add Radarr endpoints under `/api/radarr`.
2. Add `GET /api/tasks` task list endpoint.
3. Add optional integration block to `TaskResponse`.
4. Add file detail/delete endpoints.
5. Extend `FileInfo` with external/import state fields.
6. Extend `/api/events` payloads with Radarr events.

### 16.3 UI migration

1. Add Radarr sidebar item.
2. Add Radarr Instances page.
3. Add Add/Edit Instance page.
4. Add Radarr Settings page.
5. Add Missing Movies page.
6. Add Radarr-context Search mode.
7. Update Downloads page.
8. Update Files page.

## 17. Testing plan

### 17.1 Unit tests

- path translation with different container paths
- path traversal rejection
- API key redaction
- instance validation result mapping
- missing movie normalization
- primary media file selection
- import status transitions
- task/file schema serialization

### 17.2 Integration tests with mocked Radarr

- connection success/failure
- API key rejected
- missing movies list
- root folders and quality profiles loaded
- download-from-search creates task with path controlled by instance
- completed task triggers import worker
- import success updates task and file state
- import failure shows retryable status

### 17.3 Docker path mapping tests

Use two containers with different mount paths pointing to the same host directory:

```text
Tube Explore sees: /downloads/radarr-main
Radarr sees:       /data/imports/tube-explore/radarr-main
```

Tests:

- Tube Explore can write file.
- Radarr can see path through translated path.
- Import failure clearly reports both paths.
- Corrected path mapping allows retry import.

### 17.4 UI tests

- multiple instances render and filter correctly
- add/edit instance validates required fields
- test connection checklist renders all states
- missing movies list filters and actions work
- Radarr search context preserves target movie context
- downloads page shows imported/importing/failed states
- files page shows external/imported and delete constraints

## 18. Acceptance criteria

The feature is complete when:

1. A user can add, edit, disable, delete, and test multiple Radarr instances.
2. Each instance stores a Tube Explore write path and Radarr-visible import path.
3. API keys are encrypted and never returned.
4. The overview page shows aggregate and per-instance status.
5. Settings page shows root folders, quality profiles, sync history, test results, and path mapping state.
6. Missing movies load for the selected instance.
7. A missing movie can be sent to Radarr-context Search.
8. A missing movie can be downloaded from a pasted URL.
9. Radarr-linked downloads use existing task lifecycle and SSE events.
10. Completed Radarr-linked downloads enqueue import automatically.
11. Import success and failure are persisted.
12. Downloads page shows download and import status distinctly.
13. Files page shows imported/external Radarr files correctly.
14. Retry import works after correcting path mapping.
15. Playlist-to-Radarr movie import is blocked in v1.
16. All Radarr errors are user-actionable and redact secrets.

## 19. Implementation phases

### Phase 1 - Foundation

- data tables
- encrypted API key storage
- RadarrClient
- instance CRUD
- connection/path test

### Phase 2 - Instance overview and settings APIs

- summary stats
- root folders
- quality profiles
- sync history
- queue
- test results

### Phase 3 - Missing movies

- missing movie fetch/cache
- filter/sort/search
- selected instance context

### Phase 4 - Radarr-linked download creation

- download-from-search
- download-from-url
- controlled staging path
- task integration metadata

### Phase 5 - Import worker

- primary file selection
- path mapping
- manual/movie import
- retry import
- import state persistence
- events

### Phase 6 - Existing page updates

- Downloads page integration state
- Files page external/imported state
- task list and file detail endpoints

### Phase 7 - Hardening

- Docker path mapping tests
- error handling
- security redaction
- UI E2E

## 20. Final design decision

Proceed with the Radarr integration as a **multi-instance, path-mapped, post-download import workflow**.

The updated design supports all generated pages and makes the required backend changes explicit. The largest required correction to the earlier design is adding full multi-instance management, instance-level sync/status caching, Radarr settings tabs, task list support, file detail/delete support, and Files/Downloads schema extensions for imported/external Radarr state.