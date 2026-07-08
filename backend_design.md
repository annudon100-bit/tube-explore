# Tube Explore Arr Backend Design

**Version:** 1.0  
**Date:** 2026-07-07  
**Scope:** Backend design for shared Radarr and Sonarr integration, including multi-instance management, missing movie/episode workflows, Sonarr playlist-to-episode mapping, post-download imports, task/file status extensions, and API support for the new frontend mockups.

---

## 1. Executive summary

Tube Explore should support Radarr and Sonarr through a shared **Arr integration backend**. The shared layer manages instances, encrypted API keys, connection tests, Docker path mappings, sync snapshots, import attempts, and integration-aware task/file state. Radarr and Sonarr then plug into this layer through service-specific adapters.

The existing Tube Explore API already provides the core media workflow: search, metadata inspection, playlist inspection, video downloads, playlist downloads, task lifecycle updates, SSE task events, profiles, settings, and completed-file browsing. The Arr backend should reuse those capabilities instead of creating a second downloader.

The key backend rule remains:

```text
Tube Explore downloads files to a Tube Explore-visible staging path.
Radarr or Sonarr imports from the equivalent Arr-visible path.
The two paths must point to the same physical directory, even if containers mount it differently.
```

Radarr maps one missing movie to one imported video file. Sonarr adds two extra complexities:

1. A single missing episode maps to one downloaded file.
2. A playlist download can map many playlist entries to many Sonarr episodes and can partially import.

---

## 2. Design goals

1. Support any number of Radarr and Sonarr instances from one Tube Explore service.
2. Keep Radarr and Sonarr configuration under `Settings -> Integrations` and day-to-day work under `Instances`.
3. Reuse existing Tube Explore search, metadata, playlist, task, profile, SSE, and file APIs.
4. Add a shared backend model for Arr instances and service-specific adapters for Radarr and Sonarr.
5. Support Radarr missing movie download and import.
6. Support Sonarr single missing episode download and import.
7. Support Sonarr playlist inspection, mapping, download, and per-episode import.
8. Persist integration status independently from download status.
9. Provide enough backend state for the Downloads and Files pages to show imported, importing, partially imported, failed, and external/moved states.
10. Handle Docker/container path mapping explicitly and safely.
11. Encrypt Arr API keys and never expose them to the frontend after creation.
12. Make retries idempotent and auditable.

---

## 3. Non-goals for the first implementation

1. Do not register Tube Explore as a native Radarr/Sonarr download client.
2. Do not automatically configure Radarr/Sonarr remote path mappings.
3. Do not add arbitrary new Radarr movies or Sonarr series from Tube Explore in v1.
4. Do not auto-import Sonarr playlist items that are not explicitly mapped or skipped.
5. Do not infer a Sonarr playlist purely from order without user confirmation.
6. Do not support multi-episode files in v1.
7. Do not write directly into Arr library/root folders unless an administrator explicitly configures that as a staging path and accepts the warning.

---

## 4. Source alignment

### 4.1 Tube Explore current API

The current Tube Explore OpenAPI spec provides:

- `GET /api/search`
- `GET /api/metadata`
- `GET /api/playlist`
- `POST /api/download/video`
- `POST /api/download/playlist`
- `GET /api/tasks/{task_id}`
- `GET /api/events`
- task cancel, pause, resume, retry operations
- profiles and global settings
- downloaded-file listing, download, and storage statistics

These APIs already cover the basic search, inspect, download, task-progress, file-result, and file-listing primitives needed by the Arr integration.

### 4.2 Radarr API assumptions

The backend should use Radarr v3 API surfaces for connectivity, status, root folders, missing movies, movie records, manual import, movie import, commands, and queue/status where available. Use `X-Api-Key` for authentication.

### 4.3 Sonarr API assumptions

The backend should use Sonarr v3 API surfaces for connectivity, status, root folders, quality profiles, language profiles when present, series, episodes, missing episodes, manual import, commands, queue/status, and history where available. The Sonarr API docs state that v3 docs apply to both Sonarr v3 and v4, with some behavior varying by version.

### 4.4 Path mapping assumption

The integration does not depend on Radarr/Sonarr remote path mapping entries. Tube Explore stores its own mapping from the Tube Explore container path to the Arr container path. This is required because Tube Explore is acting as the downloader and may not be configured as a native Arr download client.

---

## 5. Backend architecture

### 5.1 High-level module layout

```text
api/
  arr_instances_router
  radarr_router
  sonarr_router
  arr_tasks_router
  arr_settings_router

services/
  ArrInstanceService
  ArrConnectionTestService
  ArrPathMappingService
  ArrStatsService
  ArrSyncService
  ArrDownloadCoordinator
  ArrImportWorker
  RadarrAdapter
  SonarrAdapter
  SonarrPlaylistMappingService
  SearchContextService
  FileRegistryService
  EventPublisher

clients/
  ArrHttpClient
  RadarrClient
  SonarrClient

repositories/
  ArrInstanceRepository
  ArrSyncSnapshotRepository
  ArrTargetRepository
  ArrTaskLinkRepository
  ArrImportAttemptRepository
  SonarrPlaylistMappingRepository
  FileRepository
```

### 5.2 Adapter boundary

The shared backend should not hardcode Radarr or Sonarr endpoint details outside adapters.

```ts
interface ArrAdapter {
  kind: 'radarr' | 'sonarr';

  testConnection(instance): Promise<ArrConnectionTest>;
  getSystemStatus(instance): Promise<ArrSystemStatus>;
  getRootFolders(instance): Promise<ArrRootFolder[]>;
  getQualityProfiles(instance): Promise<ArrQualityProfile[]>;
  getQueueSummary(instance): Promise<ArrQueueSummary>;
  openExternalUrl(instance, target): string;
}
```

Radarr adds movie-specific methods:

```ts
interface RadarrAdapter extends ArrAdapter {
  listMissingMovies(instance, query): Promise<Paged<RadarrMissingMovie>>;
  getMovie(instance, movieId): Promise<RadarrMovie>;
  scanManualImport(instance, arrPath, movieId): Promise<ManualImportCandidate[]>;
  importMovieFile(instance, request): Promise<ArrImportSubmission>;
}
```

Sonarr adds series/episode-specific methods:

```ts
interface SonarrAdapter extends ArrAdapter {
  listSeries(instance, query): Promise<SonarrSeries[]>;
  listEpisodes(instance, seriesId, query): Promise<SonarrEpisode[]>;
  listMissingEpisodes(instance, query): Promise<Paged<SonarrMissingEpisode>>;
  getEpisode(instance, episodeId): Promise<SonarrEpisode>;
  scanManualImport(instance, arrPath, episodeIds): Promise<ManualImportCandidate[]>;
  importEpisodeFile(instance, request): Promise<ArrImportSubmission>;
}
```

---

## 6. Data model

### 6.1 Shared Arr instance

```sql
CREATE TABLE arr_instances (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('radarr', 'sonarr')),
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  api_key_encrypted TEXT NOT NULL,
  tube_write_path TEXT NOT NULL,
  arr_import_path TEXT NOT NULL,
  host_path_hint TEXT NULL,
  default_download_profile_id TEXT NULL,
  default_quality_profile_id TEXT NULL,
  default_language_profile_id TEXT NULL,
  import_mode TEXT NOT NULL DEFAULT 'move'
    CHECK (import_mode IN ('move', 'copy')),
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  last_test_status TEXT NULL,
  last_test_message TEXT NULL,
  last_test_at TIMESTAMP NULL,
  last_sync_status TEXT NULL,
  last_sync_message TEXT NULL,
  last_sync_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX ux_arr_instance_kind_name
  ON arr_instances(kind, lower(name));
```

Notes:

- `default_download_profile_id` references a Tube Explore profile.
- `default_quality_profile_id` is the external Arr quality profile ID, stored as text to avoid service-specific numeric assumptions.
- `default_language_profile_id` applies to Sonarr only where supported.
- Exactly one default instance per kind is optional. Enforce this in service logic or with partial indexes if the database supports them.

### 6.2 Instance health and capability snapshot

```sql
CREATE TABLE arr_instance_capability_snapshots (
  id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  kind TEXT NOT NULL,
  version TEXT NULL,
  can_connect BOOLEAN NOT NULL,
  api_key_valid BOOLEAN NOT NULL,
  root_folders_loaded BOOLEAN NOT NULL,
  quality_profiles_loaded BOOLEAN NOT NULL,
  language_profiles_loaded BOOLEAN NULL,
  tube_write_path_writable BOOLEAN NOT NULL,
  arr_import_path_visible BOOLEAN NULL,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  raw_status_json TEXT NULL,
  created_at TIMESTAMP NOT NULL
);
```

This table powers:

- instance status badges
- testing checklist on add/edit pages
- settings test results
- troubleshooting panels

### 6.3 Sync snapshots

```sql
CREATE TABLE arr_sync_snapshots (
  id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  missing_count INTEGER NULL,
  monitored_count INTEGER NULL,
  total_series_count INTEGER NULL,
  total_movie_count INTEGER NULL,
  queue_count INTEGER NULL,
  root_folder_count INTEGER NULL,
  error_message TEXT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP NULL
);
```

The Instances pages use these snapshots instead of calling Radarr/Sonarr for every table render.

### 6.4 Radarr missing movie cache

```sql
CREATE TABLE radarr_missing_movie_cache (
  id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  movie_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  year INTEGER NULL,
  tmdb_id INTEGER NULL,
  imdb_id TEXT NULL,
  monitored BOOLEAN NULL,
  has_file BOOLEAN NULL,
  movie_path TEXT NULL,
  quality_profile_id TEXT NULL,
  quality_profile_name TEXT NULL,
  root_folder_path TEXT NULL,
  poster_url TEXT NULL,
  overview TEXT NULL,
  raw_json TEXT NULL,
  fetched_at TIMESTAMP NOT NULL,
  UNIQUE(instance_id, movie_id)
);
```

### 6.5 Sonarr missing episode cache

```sql
CREATE TABLE sonarr_missing_episode_cache (
  id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  series_id INTEGER NOT NULL,
  episode_id INTEGER NOT NULL,
  series_title TEXT NOT NULL,
  season_number INTEGER NOT NULL,
  episode_number INTEGER NOT NULL,
  absolute_episode_number INTEGER NULL,
  episode_title TEXT NULL,
  air_date TEXT NULL,
  monitored BOOLEAN NULL,
  has_file BOOLEAN NULL,
  series_path TEXT NULL,
  quality_profile_id TEXT NULL,
  quality_profile_name TEXT NULL,
  root_folder_path TEXT NULL,
  poster_url TEXT NULL,
  overview TEXT NULL,
  raw_json TEXT NULL,
  fetched_at TIMESTAMP NOT NULL,
  UNIQUE(instance_id, episode_id)
);
```

### 6.6 Arr task link

Every Radarr/Sonarr-linked download task gets one shared task link.

```sql
CREATE TABLE arr_task_links (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('radarr', 'sonarr')),
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  target_type TEXT NOT NULL CHECK (
    target_type IN ('movie', 'episode', 'episode_playlist')
  ),
  display_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  local_staging_dir TEXT NOT NULL,
  arr_staging_dir TEXT NOT NULL,
  import_mode TEXT NOT NULL CHECK (import_mode IN ('move', 'copy')),
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX ux_arr_task_link_task ON arr_task_links(task_id);
```

### 6.7 Radarr movie target link

```sql
CREATE TABLE radarr_movie_task_targets (
  id TEXT PRIMARY KEY,
  task_link_id TEXT NOT NULL REFERENCES arr_task_links(id),
  radarr_movie_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  year INTEGER NULL,
  tmdb_id INTEGER NULL,
  imdb_id TEXT NULL,
  quality_profile_id TEXT NULL,
  created_at TIMESTAMP NOT NULL
);
```

### 6.8 Sonarr episode target link

```sql
CREATE TABLE sonarr_episode_task_targets (
  id TEXT PRIMARY KEY,
  task_link_id TEXT NOT NULL REFERENCES arr_task_links(id),
  series_id INTEGER NOT NULL,
  episode_id INTEGER NOT NULL,
  season_number INTEGER NOT NULL,
  episode_number INTEGER NOT NULL,
  absolute_episode_number INTEGER NULL,
  series_title TEXT NOT NULL,
  episode_title TEXT NULL,
  tvdb_id INTEGER NULL,
  imdb_id TEXT NULL,
  quality_profile_id TEXT NULL,
  created_at TIMESTAMP NOT NULL
);
```

### 6.9 Sonarr playlist mapping

```sql
CREATE TABLE sonarr_playlist_mappings (
  id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  series_id INTEGER NOT NULL,
  series_title TEXT NOT NULL,
  season_number INTEGER NULL,
  playlist_url TEXT NOT NULL,
  playlist_title TEXT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'ready', 'download_started', 'completed', 'cancelled')
  ),
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
```

```sql
CREATE TABLE sonarr_playlist_mapping_items (
  id TEXT PRIMARY KEY,
  mapping_id TEXT NOT NULL REFERENCES sonarr_playlist_mappings(id),
  playlist_index INTEGER NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_duration_seconds INTEGER NULL,
  thumbnail_url TEXT NULL,
  episode_id INTEGER NULL,
  season_number INTEGER NULL,
  episode_number INTEGER NULL,
  episode_title TEXT NULL,
  action TEXT NOT NULL CHECK (action IN ('download', 'skip')),
  confidence TEXT NOT NULL CHECK (
    confidence IN ('high', 'medium', 'low', 'manual', 'none')
  ),
  task_file_id TEXT NULL,
  import_status TEXT NULL,
  error_message TEXT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  UNIQUE(mapping_id, playlist_index)
);
```

### 6.10 Import attempts

```sql
CREATE TABLE arr_import_attempts (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  task_link_id TEXT NOT NULL REFERENCES arr_task_links(id),
  kind TEXT NOT NULL CHECK (kind IN ('radarr', 'sonarr')),
  instance_id TEXT NOT NULL REFERENCES arr_instances(id),
  target_type TEXT NOT NULL,
  target_external_id TEXT NOT NULL,
  local_file_path TEXT NULL,
  arr_file_path TEXT NULL,
  status TEXT NOT NULL CHECK (
    status IN (
      'pending',
      'waiting_for_download',
      'mapping_path',
      'scanning',
      'candidate_selected',
      'importing',
      'imported',
      'partially_imported',
      'failed',
      'cancelled'
    )
  ),
  import_mode TEXT NOT NULL CHECK (import_mode IN ('move', 'copy')),
  external_command_id TEXT NULL,
  external_file_id TEXT NULL,
  error_code TEXT NULL,
  error_message TEXT NULL,
  raw_request_json TEXT NULL,
  raw_response_json TEXT NULL,
  started_at TIMESTAMP NULL,
  completed_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
```

### 6.11 File registry extensions

The current Files API returns completed files with path, type, format, task ID, source URL, thumbnail, and created time. Add integration/external-location fields.

```ts
FileInfo {
  storageState?: 'local' | 'external_imported' | 'missing';
  downloadable?: boolean;
  integration?: {
    kind: 'radarr' | 'sonarr';
    instanceId: string;
    instanceName: string;
    targetType: 'movie' | 'episode' | 'episode_playlist';
    importStatus: string;
    importedAt?: string;
    externalPath?: string;
    externalUrl?: string;
    movie?: {
      movieId: number;
      title: string;
      year?: number;
    };
    episode?: {
      seriesId: number;
      episodeId: number;
      seriesTitle: string;
      seasonNumber: number;
      episodeNumber: number;
      episodeTitle?: string;
    };
  };
}
```

---

## 7. Public backend API design

Use `/api/arr` for shared resources and `/api/arr/radarr` or `/api/arr/sonarr` for service-specific workflows.

### 7.1 Shared instance APIs

```http
GET /api/arr/instances?kind=radarr|sonarr|all
POST /api/arr/instances
GET /api/arr/instances/{instanceId}
PATCH /api/arr/instances/{instanceId}
DELETE /api/arr/instances/{instanceId}
POST /api/arr/instances/{instanceId}/test
POST /api/arr/instances/{instanceId}/sync
GET /api/arr/instances/{instanceId}/capabilities
GET /api/arr/instances/{instanceId}/root-folders
GET /api/arr/instances/{instanceId}/quality-profiles
GET /api/arr/instances/{instanceId}/queue
GET /api/arr/instances/{instanceId}/sync-history
```

Create instance request:

```json
{
  "kind": "sonarr",
  "name": "Main Sonarr",
  "baseUrl": "http://sonarr-main:8989",
  "apiKey": "secret",
  "tubeWritePath": "/downloads/sonarr-main",
  "arrImportPath": "/data/imports/tube-explore/sonarr-main",
  "hostPathHint": "/mnt/media/sonarr-imports/main",
  "defaultDownloadProfileId": "hd-1080p",
  "defaultQualityProfileId": "1",
  "defaultLanguageProfileId": "1",
  "importMode": "move",
  "enabled": true,
  "isDefault": true
}
```

Instance response must never include the API key:

```json
{
  "id": "inst_sonarr_main",
  "kind": "sonarr",
  "name": "Main Sonarr",
  "baseUrl": "http://sonarr-main:8989",
  "apiKeyConfigured": true,
  "tubeWritePath": "/downloads/sonarr-main",
  "arrImportPath": "/data/imports/tube-explore/sonarr-main",
  "importMode": "move",
  "enabled": true,
  "lastTestStatus": "ok",
  "lastSyncAt": "2026-07-07T09:00:00Z"
}
```

### 7.2 Shared overview APIs

These support `index.html` and the shared `Instances` sidebar item.

```http
GET /api/arr/overview
```

Response:

```json
{
  "instances": {
    "total": 5,
    "radarr": 3,
    "sonarr": 2,
    "connected": 4,
    "warning": 1
  },
  "radarr": {
    "missingMovies": 247,
    "monitoredMovies": 1245,
    "imports24h": 12
  },
  "sonarr": {
    "missingEpisodes": 384,
    "series": 86,
    "imports24h": 31
  },
  "lastSyncAt": "2026-07-07T09:00:00Z"
}
```

### 7.3 Radarr APIs

```http
GET /api/arr/radarr/instances
GET /api/arr/radarr/instances/{instanceId}/missing
GET /api/arr/radarr/instances/{instanceId}/movies/{movieId}
POST /api/arr/radarr/instances/{instanceId}/movies/{movieId}/download-from-url
POST /api/arr/radarr/instances/{instanceId}/movies/{movieId}/download-from-search
POST /api/arr/radarr/tasks/{taskId}/import/retry
GET /api/arr/radarr/tasks/{taskId}
```

Missing movie query parameters:

```text
limit, offset, search, monitoredOnly, qualityProfileId, rootFolder, sortBy, sortOrder
```

### 7.4 Sonarr APIs

```http
GET /api/arr/sonarr/instances
GET /api/arr/sonarr/instances/{instanceId}/series
GET /api/arr/sonarr/instances/{instanceId}/series/{seriesId}
GET /api/arr/sonarr/instances/{instanceId}/series/{seriesId}/episodes
GET /api/arr/sonarr/instances/{instanceId}/missing-episodes
GET /api/arr/sonarr/instances/{instanceId}/episodes/{episodeId}
POST /api/arr/sonarr/instances/{instanceId}/episodes/{episodeId}/download-from-url
POST /api/arr/sonarr/instances/{instanceId}/episodes/{episodeId}/download-from-search
POST /api/arr/sonarr/tasks/{taskId}/import/retry
GET /api/arr/sonarr/tasks/{taskId}
```

Missing episode query parameters:

```text
limit, offset, search, seriesId, seasonNumber, monitoredOnly, qualityProfileId,
rootFolder, airDateFrom, airDateTo, groupBy, sortBy, sortOrder
```

### 7.5 Sonarr playlist mapping APIs

```http
POST /api/arr/sonarr/instances/{instanceId}/playlist/inspect
POST /api/arr/sonarr/instances/{instanceId}/playlist/mappings
GET /api/arr/sonarr/playlist/mappings/{mappingId}
PATCH /api/arr/sonarr/playlist/mappings/{mappingId}
POST /api/arr/sonarr/playlist/mappings/{mappingId}/auto-map
POST /api/arr/sonarr/playlist/mappings/{mappingId}/download
DELETE /api/arr/sonarr/playlist/mappings/{mappingId}
```

Inspect request:

```json
{
  "seriesId": 12,
  "seasonNumber": 1,
  "playlistUrl": "https://example.com/playlist"
}
```

Mapping item request shape:

```json
{
  "items": [
    {
      "playlistIndex": 1,
      "episodeId": 101,
      "action": "download"
    },
    {
      "playlistIndex": 2,
      "action": "skip"
    }
  ]
}
```

Download mapping response reuses existing task creation semantics:

```json
{
  "taskId": "task_abc",
  "status": "pending",
  "statusUrl": "/api/tasks/task_abc"
}
```

### 7.6 Search context APIs

The frontend can keep using the existing `GET /api/search`, but the backend needs context-bound download endpoints.

```http
POST /api/arr/search-contexts
GET /api/arr/search-contexts/{contextId}
POST /api/arr/search-contexts/{contextId}/download-result
POST /api/arr/search-contexts/{contextId}/download-url
```

Context types:

```text
radarr_movie
sonarr_episode
sonarr_playlist_mapping
```

This prevents the frontend from passing arbitrary Arr targets with each download request.

### 7.7 Task and file API extensions

Extend `GET /api/tasks/{task_id}` and `/api/events` payloads with optional integration data. Existing clients should continue to work if they ignore the new fields.

```json
{
  "id": "task_abc",
  "type": "video",
  "status": "completed",
  "progressPercent": 100,
  "integration": {
    "kind": "sonarr",
    "instanceId": "inst_sonarr_main",
    "instanceName": "Main Sonarr",
    "targetType": "episode",
    "displayTitle": "The Expanse S01E01 - Dulcinea",
    "downloadStatus": "completed",
    "importStatus": "imported",
    "importedCount": 1,
    "failedCount": 0
  }
}
```

Extend `GET /api/files` filters:

```text
integrationKind=radarr|sonarr|none|all
storageState=local|external_imported|missing|all
importStatus=imported|importing|failed|all
```

---

## 8. Path mapping design

### 8.1 Fields

Each Arr instance has:

```text
tubeWritePath   - path visible to the Tube Explore process/container
arrImportPath   - same physical path as visible to Radarr/Sonarr
hostPathHint    - optional administrator note for the host path
```

### 8.2 Mapping function

```ts
function toArrPath(localPath: string, instance: ArrInstance): string {
  const localRoot = normalizeAbsolute(instance.tubeWritePath);
  const arrRoot = normalizeAbsolute(instance.arrImportPath);
  const local = normalizeAbsolute(localPath);

  if (local !== localRoot && !local.startsWith(localRoot + '/')) {
    throw new PathMappingError('File is outside configured Tube Explore write path');
  }

  const relative = local.slice(localRoot.length).replace(/^\/+/g, '');
  return joinPosix(arrRoot, relative);
}
```

### 8.3 Validation behavior

`POST /api/arr/instances/{id}/test` must validate:

1. Base URL format.
2. API key presence.
3. External API connection.
4. External system status/version.
5. Root folders can be listed.
6. Quality profiles can be listed.
7. Language profiles can be listed for Sonarr if supported.
8. Tube Explore can write a sentinel file under `tubeWritePath`.
9. Tube Explore can delete the sentinel file.
10. Best-effort Arr visibility check for `arrImportPath`.
11. Warning if `arrImportPath` appears to be under an Arr root/library folder.
12. Warning if `tubeWritePath` and `arrImportPath` are identical but services are likely containerized with different paths.

### 8.4 Error messaging

Path errors must include both paths:

```json
{
  "detail": "Sonarr cannot access the import path",
  "localPath": "/downloads/sonarr-main/The Expanse/S01E01.mp4",
  "arrPath": "/data/imports/tube-explore/sonarr-main/The Expanse/S01E01.mp4",
  "hint": "Check that both paths point to the same host directory and that Sonarr has read access."
}
```

---

## 9. Download coordination

### 9.1 Radarr movie download

```text
1. Validate instance kind is radarr and enabled.
2. Fetch Radarr movie by movieId or use fresh cache row.
3. Create local staging directory:
   tubeWritePath/radarr/{instanceId}/{movieId}-{safeTitleYear}/
4. Create arr staging directory with path mapping.
5. Create arr_task_link and radarr_movie_task_targets.
6. Call existing video download service with controlled output path.
7. Return taskId.
8. Import worker handles completion.
```

Radarr v1 does not support playlist downloads.

### 9.2 Sonarr single episode download

```text
1. Validate instance kind is sonarr and enabled.
2. Fetch Sonarr episode and series metadata.
3. Create local staging directory:
   tubeWritePath/sonarr/{instanceId}/{seriesId}/Season {season}/SxxEyy/
4. Create arr staging directory with path mapping.
5. Create arr_task_link and sonarr_episode_task_targets.
6. Call existing video download service with controlled output path.
7. Return taskId.
8. Import worker handles completion.
```

### 9.3 Sonarr playlist download

```text
1. Inspect playlist using existing playlist inspection.
2. Create a draft mapping with all playlist entries.
3. Auto-map entries using series title, season, episode title, episode number, duration, and order as weak signals.
4. Require user confirmation for every entry: download with episodeId or skip.
5. Create a playlist download task using existing playlist download service.
6. Store mappingId in arr_task_links.
7. On file completion, match each downloaded file to a mapping item by playlist index.
8. Import each mapped file to Sonarr.
9. Persist full, partial, or failed import state.
```

### 9.4 Controlled output path

The existing download APIs expose user-configurable directory fields. Arr-linked downloads must not trust arbitrary user path overrides. The coordinator should set output paths internally and only allow quality/format/profile options that do not break import.

---

## 10. Import worker design

### 10.1 Worker inputs

The worker consumes:

- task completed event
- manual retry request
- scheduled recovery scan

### 10.2 Shared import states

```text
waiting_for_download
mapping_path
scanning
candidate_selected
importing
imported
partially_imported
failed
cancelled
```

### 10.3 Radarr import flow

```text
1. Locate task result files.
2. Pick primary video file.
3. Ensure file is under local_staging_dir.
4. Map to arr_file_path.
5. Ask Radarr manual import or movie import API to scan/import.
6. Select candidate matching movieId where available.
7. Submit import using configured importMode.
8. Mark imported or failed.
9. If moved, mark local file storageState = external_imported.
```

### 10.4 Sonarr single episode import flow

```text
1. Locate task result files.
2. Pick primary video file.
3. Ensure file is under local_staging_dir.
4. Ensure filename/staged path contains SxxEyy where possible.
5. Map to arr_file_path.
6. Ask Sonarr manual import API to scan/import.
7. Select candidate matching episodeId.
8. Submit import using configured importMode.
9. Mark imported or failed.
```

### 10.5 Sonarr playlist import flow

```text
1. Locate playlist task result files.
2. Match files to mapping items by playlist index first, then source URL fallback.
3. For each item with action = download:
   a. Ensure file exists.
   b. Map local file path to Arr path.
   c. Import against mapped episodeId.
   d. Persist per-item import status.
4. If all imports succeed, task integration status = imported.
5. If some succeed and some fail, status = partially_imported.
6. If all fail, status = failed.
```

### 10.6 Retry behavior

Retry import should not re-download unless the download task has no usable files.

```text
Retry import:
  Reuse existing task result files.
  Recompute path mapping from current instance settings.
  Create a new arr_import_attempt row.
  Preserve previous attempt history.

Retry download:
  Use existing task retry semantics.
  Create or reuse Arr task link depending on whether the existing task ID is retained.
```

---

## 11. Sonarr playlist mapping design

### 11.1 Auto-map signals

Use a confidence-scored heuristic:

1. Exact episode number patterns in playlist title: `S01E03`, `1x03`, `Episode 3`.
2. Episode title fuzzy match.
3. Playlist order compared to season episode order.
4. Duration similarity.
5. Air-date or release-date signals if available.

Confidence rules:

```text
high    - exact SxxEyy or strong title + order match
medium  - title or number likely but not exact
low     - order-only or weak title match
manual  - user-selected
none    - no suggestion
```

### 11.2 Validation before download

A mapping can start only when:

1. Every non-skipped playlist entry has an episode ID.
2. No two entries map to the same episode unless user explicitly confirms replacement.
3. The selected episodes belong to the selected series.
4. The instance is enabled and path mapping test is not failed.
5. The playlist has at least one downloadable entry.

### 11.3 Mapping result states

```text
draft
ready
download_started
completed
cancelled
```

Mapping item states:

```text
pending_download
downloading
downloaded
importing
imported
failed
skipped
```

---

## 12. Events and real-time updates

The existing global SSE stream should be extended with Arr events.

### 12.1 New event types

```text
arr_instance_test_started
arr_instance_test_updated
arr_instance_test_completed
arr_sync_started
arr_sync_completed
arr_sync_failed
arr_import_created
arr_import_updated
arr_import_completed
arr_import_failed
sonarr_playlist_mapping_updated
```

### 12.2 Example payload

```json
{
  "type": "arr_import_updated",
  "taskId": "task_abc",
  "kind": "sonarr",
  "instanceId": "inst_sonarr_main",
  "targetType": "episode_playlist",
  "importStatus": "partially_imported",
  "importedCount": 10,
  "failedCount": 2,
  "message": "Imported 10 of 12 mapped episodes"
}
```

### 12.3 Event compatibility

Do not change existing task event names or required fields. Add optional `integration` blocks so older clients continue to render existing task states.

---

## 13. API support by frontend page

### 13.1 `index.html` - Instances overview

Needs:

- `GET /api/arr/overview`
- `GET /api/arr/instances?kind=all`
- `POST /api/arr/instances/{id}/sync`

### 13.2 `radarr_instances.html`

Needs:

- `GET /api/arr/instances?kind=radarr`
- `GET /api/arr/radarr/instances/{id}/missing`
- `POST /api/arr/instances/{id}/sync`
- `POST /api/arr/instances/{id}/test`

### 13.3 `sonarr_instances.html`

Needs:

- `GET /api/arr/instances?kind=sonarr`
- `GET /api/arr/sonarr/instances/{id}/missing-episodes`
- `POST /api/arr/instances/{id}/sync`
- `POST /api/arr/instances/{id}/test`

### 13.4 `sonarr_instance_form.html`

Needs:

- `POST /api/arr/instances`
- `PATCH /api/arr/instances/{id}`
- `POST /api/arr/instances/{id}/test`
- `GET /api/profiles`
- `GET /api/arr/instances/{id}/root-folders`
- `GET /api/arr/instances/{id}/quality-profiles`

### 13.5 `settings_integrations.html`

Needs:

- `GET /api/arr/instances?kind=all`
- `GET /api/arr/overview`
- `PATCH /api/arr/instances/{id}`
- `POST /api/arr/instances/{id}/test`
- `GET /api/arr/instances/{id}/sync-history`

### 13.6 `sonarr_missing_episodes.html`

Needs:

- `GET /api/arr/sonarr/instances/{id}/missing-episodes`
- `GET /api/arr/sonarr/instances/{id}/series`
- `GET /api/arr/instances/{id}/quality-profiles`
- `POST /api/arr/search-contexts`
- `POST /api/arr/sonarr/instances/{id}/episodes/{episodeId}/download-from-url`

### 13.7 `sonarr_episode_search_context.html`

Needs:

- `GET /api/arr/search-contexts/{contextId}`
- `GET /api/search`
- `GET /api/metadata`
- `POST /api/arr/search-contexts/{contextId}/download-result`
- `POST /api/arr/search-contexts/{contextId}/download-url`

### 13.8 `sonarr_playlist_mapping.html`

Needs:

- `POST /api/arr/sonarr/instances/{id}/playlist/inspect`
- `POST /api/arr/sonarr/instances/{id}/playlist/mappings`
- `GET /api/arr/sonarr/playlist/mappings/{mappingId}`
- `PATCH /api/arr/sonarr/playlist/mappings/{mappingId}`
- `POST /api/arr/sonarr/playlist/mappings/{mappingId}/auto-map`
- `POST /api/arr/sonarr/playlist/mappings/{mappingId}/download`

### 13.9 `downloads_arr.html`

Needs:

- Existing task list/status APIs plus integration fields.
- `POST /api/arr/radarr/tasks/{taskId}/import/retry`
- `POST /api/arr/sonarr/tasks/{taskId}/import/retry`
- `GET /api/events`

### 13.10 `files_arr.html`

Needs:

- Existing `GET /api/files` plus `integrationKind`, `storageState`, and `importStatus` filters.
- `GET /api/files/{file_id}/download`, but disabled when `downloadable=false`.
- External open URLs generated from integration metadata.

---

## 14. Security design

### 14.1 API key handling

- Store API keys encrypted at rest.
- Never return API keys after create/update.
- Redact keys from logs, exceptions, task params, SSE payloads, and telemetry.
- Allow replacement by sending a new key; allow retaining existing key by omitting it in patch.

### 14.2 Network protections

- Permit only `http` and `https` base URLs.
- Enforce request timeout.
- Limit response size for external API responses.
- Do not follow redirects to a different host.
- Reject localhost/link-local/private-network restrictions only if the deployment threat model requires SSRF protection. For local self-hosted media apps, private addresses are expected, so this should be configurable.

### 14.3 Path protections

- All configured paths must be absolute.
- Generated output paths must stay under `tubeWritePath`.
- Reject path traversal in titles and user-controlled path segments.
- Sanitize filenames and directories.
- Do not let frontend pass arbitrary import paths during download.
- Warn when staging path overlaps Arr library root folder.

---

## 15. Reliability and concurrency

### 15.1 Worker concurrency

Use separate concurrency controls:

```text
download workers
import workers
external API sync workers
```

Do not let slow Arr imports block download progress events.

### 15.2 Idempotency

Use idempotency keys for context-bound downloads:

```text
kind + instanceId + targetId + sourceUrl + profileId
```

If a request is repeated while a task is active, return the existing task unless the caller explicitly requests a new task.

### 15.3 Recovery scans

On service restart:

1. Find Arr task links where download is completed but import is pending/running.
2. Re-create import attempts in `waiting_for_download`, `mapping_path`, or `scanning` as needed.
3. Do not retry failed imports automatically more than the configured retry count.

### 15.4 Partial import handling

For Sonarr playlist tasks, import state must be computed from mapping items:

```text
all imported      -> imported
some imported     -> partially_imported
none imported     -> failed
some still active -> importing
```

---

## 16. Error taxonomy

Use stable error codes for frontend display and retry guidance.

```text
ARR_CONNECTION_FAILED
ARR_AUTH_FAILED
ARR_VERSION_UNSUPPORTED
ARR_ROOT_FOLDERS_UNAVAILABLE
ARR_QUALITY_PROFILES_UNAVAILABLE
TUBE_WRITE_PATH_NOT_WRITABLE
ARR_IMPORT_PATH_NOT_VISIBLE
PATH_MAPPING_FAILED
TARGET_NOT_FOUND
TARGET_ALREADY_HAS_FILE
PLAYLIST_MAPPING_INCOMPLETE
PLAYLIST_MAPPING_DUPLICATE_EPISODE
DOWNLOAD_RESULT_MISSING
NO_PRIMARY_MEDIA_FILE
IMPORT_CANDIDATE_NOT_FOUND
IMPORT_REJECTED_BY_ARR
IMPORT_PERMISSION_DENIED
IMPORT_PARTIAL_FAILURE
```

Each error response should include:

```json
{
  "detail": "Human-readable message",
  "code": "PATH_MAPPING_FAILED",
  "retryable": true,
  "action": "edit_path_mapping",
  "context": {}
}
```

---

## 17. Testing strategy

### 17.1 Unit tests

- Path normalization and mapping.
- Filename sanitization.
- Instance validation.
- API key redaction.
- Radarr/Sonarr response normalization.
- Sonarr auto-map scoring.
- Import state aggregation.
- File registry state after move/copy imports.

### 17.2 Contract tests

Mock Radarr and Sonarr adapters for:

- status success/failure
- invalid API key
- root folders unavailable
- missing movies/episodes pagination
- manual import candidate found/not found
- import accepted/rejected
- Sonarr playlist partial import

### 17.3 Integration tests

- Add Radarr and Sonarr instances.
- Fetch missing movie/episode lists.
- Start Radarr-linked video task.
- Start Sonarr-linked single episode task.
- Inspect and map Sonarr playlist.
- Start Sonarr playlist task.
- Simulate import success and partial failure.
- Verify Downloads and Files API responses expose correct integration state.

### 17.4 Security tests

- API key never appears in response/log/event.
- Path traversal title cannot escape staging directory.
- Retrying import after path mapping edit uses the new mapping.
- Download path override cannot bypass Arr coordinator.

---

## 18. Migration plan

### Phase 1 - Shared Arr foundation

- Create `arr_instances`, capability snapshots, sync snapshots.
- Add shared instance CRUD APIs.
- Implement encrypted API key storage.
- Implement connection/path tests.

### Phase 2 - Move Radarr to shared model

- Migrate existing Radarr instance table, if present, into `arr_instances` with `kind='radarr'`.
- Preserve Radarr-specific task links.
- Update Radarr APIs to `/api/arr/radarr/...` while keeping old endpoints as temporary aliases if already shipped.

### Phase 3 - Sonarr single episode support

- Add Sonarr adapter.
- Add missing episodes API.
- Add single episode search/paste URL download.
- Add Sonarr single episode import worker.

### Phase 4 - Sonarr playlist mapping

- Add playlist mapping tables and APIs.
- Implement playlist inspection and auto-map.
- Implement playlist download and per-episode import.
- Add partial import status.

### Phase 5 - Downloads and Files API extensions

- Add task `integration` block.
- Add file integration/external-location fields.
- Add filters for integration and storage state.

### Phase 6 - Hardening

- Recovery scans.
- Retry policies.
- Redaction tests.
- Path-mapping diagnostics.
- Documentation and setup guidance.

---

## 19. Acceptance criteria

1. A user can add multiple Radarr and Sonarr instances.
2. The backend encrypts API keys and never returns them.
3. The backend validates URL/API key/root folders/profiles/write path/path mapping.
4. The instances overview can summarize all Arr instances.
5. The Radarr instances page can show Radarr instance counts, status, missing movies, and sync actions.
6. The Sonarr instances page can show Sonarr instance counts, status, missing episodes, and sync actions.
7. The Sonarr missing episodes page can filter/group/search missing episodes.
8. A Sonarr episode can be downloaded from a selected search result.
9. A Sonarr episode can be downloaded from a pasted URL.
10. A Sonarr playlist can be inspected before download.
11. Playlist entries can be mapped or skipped before download.
12. A mapped Sonarr playlist can download and import per episode.
13. Radarr movie imports continue to work under the shared Arr model.
14. Downloads API exposes download and import state separately.
15. Files API exposes local, moved/imported, and failed import states.
16. Import retries do not require redownloading when files still exist.
17. Path mapping failures show both Tube Explore and Arr-visible paths.
18. Existing non-Arr download flows continue to work unchanged.

---

## 20. Open decisions

1. Whether to keep temporary compatibility endpoints for previous Radarr-only APIs.
2. Whether to allow import mode `copy` globally or per task.
3. Whether to support Sonarr anime absolute episode numbers in v1 or v1.1.
4. Whether to allow multi-episode files in a later release.
5. Whether to expose Arr remote path mapping CRUD as an advanced troubleshooting feature.
6. Whether to support adding new Radarr movies or Sonarr series directly from Tube Explore in a future release.

---

## 21. References

- Tube Explore OpenAPI spec uploaded in this conversation: `openapi(3).json`.
- Radarr API documentation: https://radarr.video/docs/api/
- Sonarr API documentation: https://sonarr.tv/docs/api/
- Servarr Wiki: https://wiki.servarr.com/
- Servarr/Radarr Docker path guidance: https://wiki.servarr.com/radarr/system
- TRaSH remote path mapping guidance: https://trash-guides.info/Sonarr/Tips/Sonarr-remote-path-mapping/

