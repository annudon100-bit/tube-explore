# Tube Explore Arr Integrations - Frontend Design Document

Version: 1.0  
Scope: Radarr and Sonarr frontend changes  
Base mockup reference: last `files.html` layout system plus generated Arr/Radarr/Sonarr HTML mockups

## 1. Executive summary

Tube Explore is adding first-class integration support for Radarr and Sonarr. The frontend must support one Tube Explore service connecting to multiple Radarr and Sonarr instances, downloading media through the existing Tube Explore workflow, then handing completed files to the relevant Arr application for import.

The main frontend change is not just adding pages. It is reorganizing the app so Arr integrations are discoverable without overcrowding the sidebar. Radarr and Sonarr working pages move under an `Instances` submenu. Add/edit forms and integration defaults move under `Settings -> Integrations`.

The frontend must support these user flows:

- Manage multiple Radarr and Sonarr instances.
- Configure Docker-aware path mappings for each instance.
- View Radarr missing movies and start a Radarr-linked download.
- View Sonarr missing episodes and start a Sonarr-linked single episode download.
- Inspect a playlist and map playlist entries to Sonarr episodes before downloading.
- Track download status separately from Arr import status.
- Show Radarr/Sonarr imported files, including files moved out of Tube Explore local storage.

## 2. Inputs and references

### 2.1 Existing Tube Explore frontend baseline

The existing frontend design uses a dark, glassy interface with a collapsible left sidebar, card-based summaries, data tables, right-side detail panels, and responsive table-to-card behavior. The latest `files.html` is the visual and structural reference for the new Arr pages.

### 2.2 Current Tube Explore API baseline

The current backend already exposes search, metadata, playlist inspection, video downloads, playlist downloads, task polling, task events, task pause/resume/cancel/retry, files listing, file downloads, storage stats, profiles, settings, health, and readiness. The Arr frontend should reuse these existing capabilities where possible and add Arr-specific endpoints around them.

### 2.3 External API references

- Radarr API documentation: https://radarr.video/docs/api/
- Sonarr API documentation: https://sonarr.tv/docs/api/

The frontend should not call Radarr or Sonarr directly from the browser. All Arr calls go through the Tube Explore backend so API keys remain server-side.

## 3. Design goals

1. Keep the sidebar clean by introducing grouped navigation.
2. Make multi-instance management obvious and first-class.
3. Make Docker path mapping understandable and testable.
4. Keep Radarr and Sonarr workflows visually consistent while respecting their different domain models.
5. Reuse the existing Tube Explore search/download/task UI instead of creating a separate downloader.
6. Separate download status from Arr import status.
7. Prevent dangerous assumptions, especially playlist order matching Sonarr episode order.
8. Provide actionable failure states for path mapping, import failures, and missing instances.

## 4. Navigation and information architecture

### 4.1 Updated sidebar

Top-level navigation:

- Dashboard
- Search
- Downloads
- Playlists
- Files
- Profiles
- Instances
- Settings
- System

`Instances` expands to:

- Overview
- Radarr
- Sonarr

`Settings` expands to:

- General
- Download Profiles
- Integrations
- System

`Settings -> Integrations` expands to:

- Overview
- Radarr
- Sonarr

### 4.2 Sidebar behavior

Expanded sidebar:

- Shows icons and labels.
- Shows submenu labels inline or as nested groups.
- Highlights both the active top-level group and active child page.

Collapsed sidebar:

- Shows top-level icons only.
- Hover or click opens a flyout submenu for `Instances` and `Settings`.
- Tooltips show page names.
- On mobile, bottom navigation should show primary destinations only: Search, Downloads, Files, Instances, Settings.

### 4.3 Empty instance routing

If a user opens an integration working page and no instances exist, show a focused empty state:

- Title: `No Sonarr instances configured` or `No Radarr instances configured`.
- Explanation: `Connect an instance to view missing items and import downloaded files.`
- Primary action: `Add Sonarr Instance` or `Add Radarr Instance`.
- Action route: `/settings/integrations/sonarr/new` or `/settings/integrations/radarr/new`.

Do not show an empty data table with disabled controls.

## 5. Page inventory

| Page | Route | Status | Purpose |
|---|---|---|---|
| Instances overview | `/instances` | New | Entry point for Radarr/Sonarr instance groups. |
| Radarr instances | `/instances/radarr` | Updated/moved | Manage all Radarr instances. |
| Sonarr instances | `/instances/sonarr` | New | Manage all Sonarr instances. |
| Settings integrations | `/settings/integrations` | New | Shared integration configuration hub. |
| Add/edit Radarr instance | `/settings/integrations/radarr/new`, `/settings/integrations/radarr/:id` | Moved/updated | Configure Radarr connection and path mapping. |
| Add/edit Sonarr instance | `/settings/integrations/sonarr/new`, `/settings/integrations/sonarr/:id` | New | Configure Sonarr connection and path mapping. |
| Radarr missing movies | `/instances/radarr/:id/missing` | New | Work queue for missing movies. |
| Sonarr missing episodes | `/instances/sonarr/:id/missing` | New | Work queue for missing episodes. |
| Radarr-context search | `/instances/radarr/:id/movies/:movieId/search` | New | Search and download for a selected movie. |
| Sonarr-context search | `/instances/sonarr/:id/episodes/:episodeId/search` | New | Search and download for a selected episode. |
| Sonarr playlist mapping | `/instances/sonarr/:id/playlist-map` | New | Map playlist entries to episodes before downloading. |
| Downloads | `/downloads` | Updated | Show Radarr/Sonarr import states. |
| Files | `/files` | Updated | Show imported/external file ownership. |

## 6. Shared layout system

All new pages should reuse the same visual foundation as `files.html`:

- Dark radial gradient background.
- Glass-like cards with subtle borders.
- Collapsible sidebar.
- Card summary rows.
- Rounded search/filter controls.
- Dense but readable tables.
- Purple primary actions.
- Green success badges, yellow warning badges, red failure badges, blue informational badges.
- Right-side detail panels for selected rows on desktop.
- Responsive stacked cards on narrow screens.

### 6.1 Shared shell components

- `AppShell`
- `Sidebar`
- `SidebarGroup`
- `SidebarFlyout`
- `PageHeader`
- `Toolbar`
- `SummaryCard`
- `DataTable`
- `EntityListCard`
- `RightDetailPanel`
- `EmptyState`
- `ErrorBanner`
- `ConfirmDialog`
- `ToastRegion`

## 7. Domain terminology

Use user-facing labels that do not expose backend jargon unnecessarily.

| Backend concept | UI label |
|---|---|
| Arr instance | Instance |
| Radarr missing movie | Missing movie |
| Sonarr missing episode | Missing episode |
| Tube write path | Tube Explore write path |
| Arr import path | Radarr import path or Sonarr import path |
| Import mode move | Move - recommended |
| Import mode copy | Copy - keep staging file |
| Integration import failed | Import failed |
| External imported file | Imported to Radarr/Sonarr |

## 8. Data model expected by the frontend

### 8.1 ArrInstanceViewModel

```ts
interface ArrInstanceViewModel {
  id: string;
  kind: 'radarr' | 'sonarr';
  name: string;
  baseUrl: string;
  enabled: boolean;
  status: 'connected' | 'warning' | 'offline' | 'unknown';
  statusMessage?: string;
  version?: string;
  tubeWritePath: string;
  arrImportPath: string;
  hostPathHint?: string;
  importMode: 'move' | 'copy';
  pathMappingStatus: 'verified' | 'warning' | 'failed' | 'unknown';
  lastSyncAt?: string;
  counts: {
    missingMovies?: number;
    monitoredMovies?: number;
    series?: number;
    missingEpisodes?: number;
    monitoredEpisodes?: number;
    queue?: number;
    imports24h?: number;
  };
}
```

### 8.2 MissingMovieViewModel

```ts
interface MissingMovieViewModel {
  instanceId: string;
  movieId: number;
  title: string;
  year?: number;
  tmdbId?: number;
  imdbId?: string;
  posterUrl?: string;
  monitored: boolean;
  qualityProfile?: string;
  rootFolder?: string;
  moviePath?: string;
  currentTaskId?: string;
  currentImportStatus?: ArrImportStatus;
}
```

### 8.3 MissingEpisodeViewModel

```ts
interface MissingEpisodeViewModel {
  instanceId: string;
  seriesId: number;
  episodeId: number;
  seriesTitle: string;
  seasonNumber: number;
  episodeNumber: number;
  episodeTitle: string;
  airDate?: string;
  tvdbId?: number;
  imdbId?: string;
  posterUrl?: string;
  monitored: boolean;
  qualityProfile?: string;
  rootFolder?: string;
  currentTaskId?: string;
  currentImportStatus?: ArrImportStatus;
}
```

### 8.4 PlaylistMappingViewModel

```ts
interface PlaylistMappingViewModel {
  mappingId: string;
  instanceId: string;
  seriesId: number;
  seriesTitle: string;
  seasonNumber?: number;
  playlistUrl: string;
  entries: PlaylistMappingEntryViewModel[];
  validation: {
    mappedCount: number;
    skippedCount: number;
    conflictCount: number;
    unmappedCount: number;
    canStartDownload: boolean;
  };
}

interface PlaylistMappingEntryViewModel {
  playlistIndex: number;
  sourceTitle: string;
  sourceUrl: string;
  duration?: number;
  thumbnailUrl?: string;
  suggestedEpisodeId?: number;
  selectedEpisodeId?: number;
  selectedEpisodeLabel?: string;
  confidence: 'high' | 'medium' | 'low' | 'manual' | 'none';
  action: 'download' | 'skip';
  warning?: string;
}
```

### 8.5 Download and file integration metadata

```ts
type ArrImportStatus =
  | 'none'
  | 'waiting_for_download'
  | 'mapping_path'
  | 'scanning'
  | 'importing'
  | 'imported'
  | 'partially_imported'
  | 'failed';

interface TaskIntegrationViewModel {
  kind: 'radarr' | 'sonarr';
  instanceId: string;
  instanceName: string;
  targetType: 'movie' | 'episode' | 'episode_playlist';
  targetLabel: string;
  importStatus: ArrImportStatus;
  importedCount?: number;
  failedCount?: number;
  totalCount?: number;
  errorMessage?: string;
}

interface FileIntegrationViewModel {
  kind?: 'radarr' | 'sonarr';
  instanceId?: string;
  instanceName?: string;
  targetLabel?: string;
  storageState: 'local' | 'external_imported' | 'missing';
  externalPath?: string;
  downloadable: boolean;
}
```

## 9. API dependency map

### 9.1 Existing Tube Explore APIs reused

The frontend continues to use existing APIs for:

- Media search.
- Metadata inspection.
- Playlist inspection.
- Video and playlist download creation.
- Task status and task events.
- Task pause/resume/cancel/retry.
- Files listing and storage stats.
- Profiles and global settings.

### 9.2 New frontend-facing APIs required

The exact backend shape may change, but the frontend needs these capabilities:

```text
GET    /api/integrations/arr/instances
POST   /api/integrations/arr/instances
PATCH  /api/integrations/arr/instances/:id
DELETE /api/integrations/arr/instances/:id
POST   /api/integrations/arr/instances/:id/test
POST   /api/integrations/arr/instances/:id/sync

GET    /api/radarr/instances/:id/missing
POST   /api/radarr/instances/:id/movies/:movieId/download-from-url
POST   /api/radarr/instances/:id/movies/:movieId/download-from-search

GET    /api/sonarr/instances/:id/missing
GET    /api/sonarr/instances/:id/series
GET    /api/sonarr/instances/:id/series/:seriesId/episodes
POST   /api/sonarr/instances/:id/episodes/:episodeId/download-from-url
POST   /api/sonarr/instances/:id/episodes/:episodeId/download-from-search
POST   /api/sonarr/instances/:id/playlist/inspect
POST   /api/sonarr/instances/:id/playlist/map
POST   /api/sonarr/instances/:id/playlist/download

GET    /api/arr/tasks/:taskId
POST   /api/arr/tasks/:taskId/import/retry
```

### 9.3 Browser security boundary

The browser must never call Radarr or Sonarr directly. API keys stay encrypted server-side and are never returned to the browser. Instance forms may accept an API key, but edit forms should show it as masked and only send a new key if the user changes it.

## 10. Page specifications

### 10.1 Instances overview

Route: `/instances`

Purpose: Give users a simple entry point into all external service instances.

Main sections:

- Summary cards: total instances, connected, warnings, missing items, imports.
- Integration cards: Radarr, Sonarr.
- Recent activity list.
- Empty state per integration if no instances exist.

Primary actions:

- Open Radarr instances.
- Open Sonarr instances.
- Add Radarr instance.
- Add Sonarr instance.

States:

- No integrations configured.
- Radarr configured, Sonarr not configured.
- Sonarr configured, Radarr not configured.
- Mixed healthy/warning/offline instances.

### 10.2 Radarr instances page

Route: `/instances/radarr`

Purpose: Manage multiple Radarr instances and open their missing movie queues.

Table columns:

- Name.
- URL.
- Status.
- Version.
- Missing movies.
- Monitored movies.
- Last sync.
- Path mapping status.
- Actions.

Row actions:

- Open missing movies.
- Sync now.
- Edit.
- Test connection.
- Disable.
- Delete.

Empty state: Button to `/settings/integrations/radarr/new`.

### 10.3 Sonarr instances page

Route: `/instances/sonarr`

Purpose: Manage multiple Sonarr instances and open their missing episode queues.

Table columns:

- Name.
- URL.
- Status.
- Version.
- Series count.
- Missing episodes.
- Queue count.
- Last sync.
- Path mapping status.
- Actions.

Row actions:

- Open missing episodes.
- Sync now.
- Edit.
- Test connection.
- Disable.
- Delete.

Empty state: Button to `/settings/integrations/sonarr/new`.

### 10.4 Settings integrations overview

Route: `/settings/integrations`

Purpose: A central configuration hub for Radarr, Sonarr, and future integrations.

Content:

- Integration cards with instance counts and health.
- Shared path mapping help.
- Link to add/edit Radarr and Sonarr instances.
- Global integration preferences, if any.

This page should not be a working queue. It is for configuration.

### 10.5 Add/Edit instance form

Routes:

- `/settings/integrations/radarr/new`
- `/settings/integrations/radarr/:id`
- `/settings/integrations/sonarr/new`
- `/settings/integrations/sonarr/:id`

Form sections:

1. Connection details.
2. Path mapping.
3. Defaults.
4. Test results.
5. Save/cancel actions.

Required fields:

- Instance name.
- Base URL.
- API key.
- Tube Explore write path.
- Radarr/Sonarr import path.
- Import mode.

Radarr defaults:

- Default download profile.
- Default quality profile display from Radarr.
- Import mode.

Sonarr defaults:

- Default download profile.
- Default quality profile display from Sonarr.
- Default language profile if backend exposes it.
- Import mode.

Path mapping copy:

`Both paths must point to the same physical directory. The Tube Explore path is where this app writes. The Radarr/Sonarr import path is how that same directory appears inside the Arr container.`

Validation states:

- Can connect.
- API key valid.
- Tube Explore write path writable.
- Arr import path visible.
- Root folders loaded.
- Warnings for different path strings are expected in Docker setups.

### 10.6 Radarr missing movies page

Route: `/instances/radarr/:id/missing`

Purpose: Work through missing movies for one Radarr instance.

Header:

- Breadcrumb: `Instances -> Radarr -> Main Radarr -> Missing Movies`.
- Instance selector.
- Status/version/root folders/missing count.
- Sync now.
- Open in Radarr.

Filters:

- Search title.
- Monitored: all/monitored/unmonitored.
- Quality profile.
- Root folder.
- Sort.

Rows:

- Poster.
- Title and IDs.
- Year.
- Quality profile.
- Root folder.
- Status.
- Actions.

Actions:

- Search.
- Paste URL.
- Open in Radarr.
- More.

Right panel:

- Instance details.
- Import path.
- Write path.
- Import mode.
- Default profile.
- Edit instance.

### 10.7 Sonarr missing episodes page

Route: `/instances/sonarr/:id/missing`

Purpose: Work through missing episodes for one Sonarr instance.

Header:

- Breadcrumb: `Instances -> Sonarr -> Main Sonarr -> Missing Episodes`.
- Instance selector.
- Status/version/missing episodes/queue count.
- Sync now.
- Open in Sonarr.

Filters:

- Search series or episode.
- Series.
- Season.
- Monitored.
- Quality profile.
- Air date.
- Group by series/season/flat list.

Rows:

- Series poster.
- Series title.
- Episode code, for example `S01E03`.
- Episode title.
- Air date.
- Quality profile.
- Status.
- Actions.

Actions:

- Search.
- Paste URL.
- Map playlist.
- Open in Sonarr.
- More.

Right panel:

- Instance details.
- Selected series summary.
- Path mapping.
- Quick help.

### 10.8 Radarr-context search page

Route: `/instances/radarr/:id/movies/:movieId/search`

Purpose: Search Tube Explore for a source matching a selected Radarr movie.

Context header:

- Target movie poster.
- Title and year.
- Radarr instance.
- Import path.
- Tube Explore write path.
- Path mapping verified badge.

Search controls:

- Query input seeded from movie title and year.
- Search button.
- Paste URL button.
- Filters by source, quality, file type.

Result action:

- `Download for Radarr`.

Selecting result:

- Starts a Radarr-linked video task.
- Redirects to Downloads or shows a task-created toast with link.

### 10.9 Sonarr episode search context page

Route: `/instances/sonarr/:id/episodes/:episodeId/search`

Purpose: Search Tube Explore for a source matching a selected Sonarr episode.

Context header:

- Series poster.
- Series title.
- Episode code and title.
- Sonarr instance.
- Import path.
- Tube Explore write path.
- Path mapping verified badge.

Search result action:

- `Download for Sonarr`.

Result details should highlight:

- Source.
- Duration.
- Quality.
- Format.
- Estimated size if available.

### 10.10 Sonarr playlist mapping page

Route: `/instances/sonarr/:id/playlist-map`

Purpose: Inspect a playlist and map playlist entries to Sonarr episodes before starting a playlist download.

This is the critical Sonarr-only page.

Sections:

1. Context panel.
   - Instance.
   - Series.
   - Season.
   - Import path status.
2. Playlist input.
   - URL input.
   - Inspect button.
   - Re-inspect button.
3. Mapping toolbar.
   - Auto-map.
   - Clear mapping.
   - Show only unmapped.
   - Show warnings.
4. Mapping table.
   - Playlist index.
   - Playlist item thumbnail/title/duration.
   - Suggested Sonarr episode.
   - Episode dropdown.
   - Confidence badge.
   - Action: download/skip.
   - Warning.
5. Summary panel.
   - Mapped count.
   - Skipped count.
   - Unmapped count.
   - Conflicts.
   - Start playlist download.

Validation:

- Start button disabled until every included playlist item is mapped.
- Duplicate episode mappings require explicit resolution.
- Low-confidence matches must be manually confirmed.
- Skipped rows do not block download.

### 10.11 Downloads page update

Route: `/downloads`

Purpose: Existing downloads page becomes the central place to monitor both downloading and Arr import.

Add columns or badges:

- Integration: Radarr/Sonarr/none.
- Target label: movie or episode.
- Download status.
- Import status.
- Import progress for playlist mappings.

Right detail panel:

- Target metadata.
- Source info.
- Download details.
- Integration details.
- Local path.
- Arr import path.
- Import mode.
- Import logs.
- Retry import.
- Open in Radarr/Sonarr.

State rules:

- A Radarr/Sonarr-linked task is not fully successful until both download and import are successful.
- A playlist task can be `completed` for download and `partially_imported` for Sonarr import.
- Failed imports must not hide successful downloads.

### 10.12 Files page update

Route: `/files`

Purpose: Files page shows local files and external imported Arr files.

New filters:

- Integration: all/local/Radarr/Sonarr.
- Storage state: local/imported external/missing.

New row fields:

- Integration badge.
- Target label.
- Storage state.
- External path.
- Downloadable flag.

Right detail panel:

- For Radarr files: movie ID, instance, Radarr path, import status.
- For Sonarr files: series, season/episode, instance, Sonarr path, import status.
- For moved files: show `Moved to Radarr/Sonarr - no longer locally downloadable`.

Actions:

- Open local file, when local.
- Download local file, when downloadable.
- Open in Radarr/Sonarr, when imported.
- Open containing folder, when available.
- Delete local file, only when local and owned by Tube Explore.

## 11. User flows

### 11.1 Configure Sonarr instance

1. User opens `Settings -> Integrations`.
2. User clicks `Add Sonarr Instance`.
3. User enters URL, API key, Tube Explore write path, Sonarr import path.
4. User clicks `Test Connection`.
5. UI shows connection and path mapping results.
6. User saves.
7. User is redirected to `/instances/sonarr` or the previous empty-state page.

### 11.2 Download a missing Sonarr episode from search

1. User opens `Instances -> Sonarr`.
2. User selects an instance.
3. User opens missing episodes.
4. User clicks `Search` on one episode.
5. UI opens Sonarr-context search.
6. User selects a result and clicks `Download for Sonarr`.
7. UI creates a Sonarr-linked download task.
8. User is redirected to Downloads.
9. Downloads page shows download progress and later import progress.
10. Files page shows the final imported/external state.

### 11.3 Download a Sonarr playlist mapped to episodes

1. User opens missing episodes.
2. User selects a series or season and clicks `Map playlist`.
3. User pastes playlist URL.
4. UI inspects playlist.
5. UI auto-suggests episode mappings.
6. User confirms mappings, fixes conflicts, or skips non-episode rows.
7. User starts playlist download.
8. Downloads page shows playlist download and per-episode import progress.
9. If some imports fail, user can retry failed imports from the details panel.

### 11.4 Radarr missing movie flow

1. User opens `Instances -> Radarr`.
2. User opens missing movies for an instance.
3. User clicks `Search` or `Paste URL` for a movie.
4. UI creates a Radarr-linked single video task.
5. Downloads page shows download and import status.
6. Files page shows imported Radarr ownership.

## 12. State management design

### 12.1 Query/data cache

Use a query cache pattern for:

- Instance lists.
- Instance health/test results.
- Missing movies.
- Missing episodes.
- Series and episode lists.
- Profiles/root folders/quality profiles.
- Files and storage stats.

Invalidate:

- Instance list after add/edit/delete/test.
- Missing queues after sync or task import success.
- Downloads after task events.
- Files after import success or local deletion.

### 12.2 Event handling

The existing task event stream should feed Downloads, side panels, and notifications. The frontend needs new event payload handling for Arr import events.

Expected event categories:

- Task created.
- Task updated.
- Task completed.
- Import created.
- Import updated.
- Import completed.
- Import failed.
- Import partially completed.

Event handling must be resilient. If the SSE connection drops, pages fall back to periodic refetch.

## 13. Validation and error handling

### 13.1 Instance form validation

Validate locally before API call:

- Name is required.
- Base URL is required and starts with `http://` or `https://`.
- API key is required on create.
- Tube Explore write path is required.
- Arr import path is required.
- Import mode is required.

Do not validate that the two paths are string-equal. In Docker, they often differ.

### 13.2 Path mapping failure states

Show a clear explanation with both paths:

- Tube Explore path: `/downloads/sonarr-main`.
- Sonarr path: `/data/imports/tube-explore/sonarr-main`.
- Error: `Sonarr cannot see the import path`.
- Actions: `Edit path mapping`, `Test again`, `View setup guide`.

### 13.3 Playlist mapping validation

Blocking errors:

- Included row has no selected episode.
- Duplicate episode selected for multiple playlist items.
- Selected episode already has a file unless user explicitly confirms replacement.
- Instance path mapping is failed.

Warnings:

- Low confidence match.
- Duration differs significantly.
- Title does not contain episode title or number.
- Playlist has extra items not likely to be episodes.

## 14. Accessibility requirements

- All icon-only buttons must have `aria-label` or `title`.
- Badge colors must be paired with text, not color-only meaning.
- Tables must use proper header cells.
- Keyboard users must be able to open sidebar flyouts.
- Forms must have visible labels and helper text.
- Error messages must be near fields and summarized at top.
- Focus should move to the first invalid field after failed validation.
- Modals and side panels must trap focus while open and restore focus on close.
- Progress bars need textual status and `aria-valuenow` where applicable.

## 15. Responsive behavior

Desktop:

- Full sidebar.
- Tables with right detail panels.
- Summary cards in rows.
- Playlist mapping table visible with multiple columns.

Tablet:

- Collapsed sidebar by default.
- Tables may hide less-important columns.
- Right panel becomes a slide-over.

Mobile:

- Bottom navigation.
- Instance and queue rows become cards.
- Filters collapse into a drawer.
- Playlist mapping becomes a vertical list of mapping cards.
- Side panels become full-screen sheets.

## 16. Component breakdown

### 16.1 Navigation components

- `SidebarShell`
- `SidebarItem`
- `SidebarSubmenu`
- `MobileBottomNav`
- `Breadcrumbs`

### 16.2 Integration components

- `IntegrationBadge`
- `InstanceStatusBadge`
- `PathMappingStatusBadge`
- `ImportStatusBadge`
- `InstanceSelector`
- `InstanceSummaryCard`
- `InstanceTestResultPanel`

### 16.3 Queue components

- `MissingMovieTable`
- `MissingEpisodeTable`
- `MissingQueueFilters`
- `MoviePosterCell`
- `EpisodeCell`
- `QueueRowActions`

### 16.4 Search context components

- `SearchContextHeader`
- `TargetMovieCard`
- `TargetEpisodeCard`
- `SearchResultList`
- `DownloadForArrButton`
- `PasteUrlForArrDialog`

### 16.5 Playlist mapping components

- `PlaylistInspector`
- `PlaylistMappingTable`
- `EpisodeSelect`
- `ConfidenceBadge`
- `MappingSummaryPanel`
- `MappingConflictBanner`

### 16.6 Downloads/files components

- `DownloadIntegrationCell`
- `ImportProgressCell`
- `TaskDetailPanel`
- `FileIntegrationCell`
- `ExternalFileNotice`

## 17. Implementation plan

### Phase 1 - Navigation and shell

- Add `Instances` sidebar group.
- Move Radarr out of top-level sidebar.
- Add `Settings -> Integrations` submenu.
- Implement empty instance redirects.

### Phase 2 - Instance management UI

- Implement shared instance list pages.
- Implement Add/Edit instance form for Radarr and Sonarr.
- Implement connection test result panel.
- Implement path mapping help and validation states.

### Phase 3 - Missing queues

- Implement Radarr missing movies page.
- Implement Sonarr missing episodes page.
- Add filters, grouping, search, sort, pagination.

### Phase 4 - Context search

- Implement Radarr-context search.
- Implement Sonarr episode-context search.
- Implement paste URL flow.

### Phase 5 - Sonarr playlist mapping

- Implement playlist inspect.
- Implement auto-map and manual mapping UI.
- Implement validation and conflict handling.
- Implement start playlist download.

### Phase 6 - Downloads and Files updates

- Add Arr integration states to Downloads.
- Add side panel import details and retry actions.
- Add Arr imported/external states to Files.

### Phase 7 - Polish and hardening

- Responsive behavior.
- Accessibility pass.
- Empty/error/loading states.
- Visual QA against mockups.

## 18. Acceptance criteria

The frontend change is acceptable when:

1. Sidebar no longer has separate top-level Radarr/Sonarr entries.
2. `Instances` submenu supports Radarr and Sonarr.
3. `Settings -> Integrations` supports Radarr and Sonarr settings.
4. No-instance states route users to the correct add-instance form.
5. Users can view and manage multiple Radarr instances.
6. Users can view and manage multiple Sonarr instances.
7. Users can configure path mappings with clear Docker guidance.
8. Users can test an instance and see detailed results.
9. Users can view Radarr missing movies and start a Radarr-linked download.
10. Users can view Sonarr missing episodes and start a Sonarr-linked episode download.
11. Users can inspect a playlist and map entries to episodes before download.
12. Playlist download cannot start until all included rows are mapped or skipped.
13. Downloads page separates download status from import status.
14. Files page distinguishes local files from files moved/imported to Radarr/Sonarr.
15. All states are usable on desktop, tablet, and mobile.
16. Icon-only controls are accessible.
17. All generated pages reuse the same visual system as `files.html`.

## 19. Open questions

1. Should instance sync run automatically on a timer, or only on page load/manual sync in v1?
2. Should the frontend expose Sonarr language profiles in v1, or only after backend confirms availability?
3. Should playlist auto-map use title similarity only, or should backend provide a confidence algorithm?
4. Should users be allowed to import over existing Sonarr episodes from the UI?
5. Should imported external files appear in Files by default, or only when `Integration` filter is active?
6. Should the dashboard summarize Radarr/Sonarr health, or keep that only under Instances?

## 20. Final recommendation

Proceed with a unified Arr frontend architecture. Radarr and Sonarr should share navigation, instance management, settings, path mapping, status badges, task import states, and files integration states. Sonarr gets additional episode and playlist-mapping pages because its domain is series-based and one playlist can correspond to many episode files.

The frontend should treat Tube Explore as the download engine and Radarr/Sonarr as import destinations. Every Arr-linked download should show both the normal Tube Explore task lifecycle and the downstream import lifecycle.
