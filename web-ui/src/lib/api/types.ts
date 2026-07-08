export type QualityMode = 'best' | 'least' | 'at_most' | 'at_least';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused';
export type TaskType = 'video' | 'playlist';
export type AudioFormat = 'best' | 'aac' | 'alac' | 'flac' | 'm4a' | 'mp3' | 'opus' | 'vorbis' | 'wav';
export type FormatType = 'video+audio' | 'video-only' | 'audio-only';

export interface ApiErrorPayload { detail?: string | ValidationError[]; }
export interface ValidationError { loc: Array<string | number>; msg: string; type: string; input?: unknown; ctx?: Record<string, unknown>; }
export interface OkResponse { ok: boolean; }

export interface SearchResult {
  id: string;
  title?: string | null;
  url: string;
  duration?: number | null;
  channel?: string | null;
  channelUrl?: string | null;
  thumbnail?: string | null;
}
export interface SearchResponse { query: string; count: number; results: SearchResult[]; }

export interface FormatInfo {
  formatId: string;
  ext?: string | null;
  width?: number | null;
  height?: number | null;
  filesize?: number | null;
  vcodec?: string | null;
  acodec?: string | null;
  abr?: number | null;
  vbr?: number | null;
  fps?: number | null;
}
export interface MetadataResponse {
  id: string;
  title?: string | null;
  url: string;
  duration?: number | null;
  channel?: string | null;
  channelUrl?: string | null;
  thumbnail?: string | null;
  description?: string | null;
  viewCount?: number | null;
  likeCount?: number | null;
  formats: FormatInfo[];
  bestHeight?: number | null;
}
export interface PlaylistEntry { id: string; title?: string | null; url: string; duration?: number | null; channel?: string | null; }
export interface PlaylistResponse { url: string; count: number; totalDuration: number; entries: PlaylistEntry[]; }

export interface DownloadRequestBase {
  url: string;
  outputDir?: string | null;
  downloadPathOverride?: string | null;
  profileId?: string | null;
  audioOnly?: boolean;
  audioFormat?: AudioFormat | null;
  audioQuality?: string | null;
  remuxTo?: string | null;
  downloadQualityMode?: QualityMode | null;
  downloadQualityValue?: number | null;
  downloadFormat?: string | null;
  formatType?: FormatType | null;
  embedMetadata?: boolean | null;
  embedThumbnail?: boolean | null;
  subtitles?: boolean | null;
  subtitleLangs?: string | null;
}
export interface DownloadVideoRequest extends DownloadRequestBase {}
export interface DownloadPlaylistRequest extends DownloadRequestBase {
  range?: string | null;
  playlistDirectory?: string | null;
  includePlaylistDir?: boolean;
}
export interface DownloadTaskCreatedResponse { taskId: string; status: 'pending'; statusUrl: string; }

export interface DownloadedFile { id?: string; name: string; size: number; path: string; }
export type ProgressStep = 'fetching_metadata' | 'preparing' | 'downloading' | 'merging' | 'converting' | 'finalizing';

export interface FileProgress {
  index: number;
  title?: string | null;
  percent: number;
  speed?: string | null;
  eta?: string | null;
  status: string;
  downloadedBytes?: number | null;
  totalBytes?: number | null;
  channel?: string | null;
  duration?: number | null;
  formatInfo?: FormatInfo[] | null;
  thumbnailUrl?: string | null;
}
export interface TaskResponse {
  id: string;
  type: TaskType;
  url: string;
  params: Record<string, unknown>;
  status: TaskStatus;
  progressPercent: number;
  progressStep?: ProgressStep | null;
  fileProgress?: FileProgress[] | null;
  downloadedBytes?: number | null;
  totalBytes?: number | null;
  speed?: string | null;
  eta?: string | null;
  elapsed?: number | null;
  thumbnailPath?: string | null;
  title?: string | null;
  channel?: string | null;
  duration?: number | null;
  formatInfo?: FormatInfo[] | null;
  currentIndex?: number | null;
  totalItems?: number | null;
  createdAt: string;
  updatedAt?: string | null;
  completedAt?: string | null;
  error?: string | null;
  result?: DownloadedFile[] | null;
}
export interface FileInfo {
  id?: string;
  name: string;
  size: number;
  path: string;
  fileType: string;
  format: string;
  detail: string;
  fileExtension: string;
  taskId: string;
  sourceUrl?: string | null;
  createdAt: string;
  thumbnailUrl?: string | null;
}
export interface FilesListResponse { items: FileInfo[]; total: number; }
export interface FileCategory { type: string; label: string; size: number; count: number; }
export interface FileStatsResponse { totalUsed: number; totalCapacity: number; categories: FileCategory[]; }

export interface ProfileBase {
  name?: string | null;
  label?: string | null;
  downloadDirectory?: string | null;
  downloadFormat?: string | null;
  downloadQualityMode?: QualityMode | null;
  downloadQualityValue?: number | null;
  formatType?: FormatType | null;
  audioFormat?: AudioFormat | null;
  audioQuality?: string | null;
  remuxTo?: string | null;
  includePlaylistDir?: boolean;
  filenameTemplate?: string | null;
  playlistTemplate?: string | null;
  embedMetadata?: boolean | null;
  embedThumbnail?: boolean | null;
  subtitles?: boolean | null;
  subtitleLangs?: string | null;
}
export interface ProfileCreateRequest extends ProfileBase { name: string; }
export interface ProfileUpdateRequest extends ProfileBase {}
export interface ProfileResponse extends Required<Pick<ProfileCreateRequest, 'name'>> {
  id: number;
  label: string;
  downloadDirectory: string;
  downloadFormat?: string | null;
  downloadQualityMode: QualityMode;
  downloadQualityValue?: number | null;
  formatType: FormatType;
  audioFormat?: AudioFormat | null;
  audioQuality?: string | null;
  remuxTo?: string | null;
  includePlaylistDir: boolean;
  filenameTemplate: string;
  playlistTemplate: string;
  embedMetadata: boolean;
  embedThumbnail: boolean;
  subtitles: boolean;
  subtitleLangs?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SettingsResponse { rateLimit: string; tempDirectory: string; retryCount: number; socketTimeout: number; maxParallelDownloads: number; }
export interface SettingsUpdateRequest { rateLimit?: string | null; tempDirectory?: string | null; retryCount?: number | null; socketTimeout?: number | null; maxParallelDownloads?: number | null; }

export interface HealthResponse {
  status: string;
  hasFfmpeg: boolean;
  ffmpegVersion?: string | null;
  hasYtdlp: boolean;
  ytdlpVersion?: string | null;
  downloadDirectoryWritable: boolean;
  tempDirectoryWritable: boolean;
  workerRunning: boolean;
  sseConnected: boolean;
}

export interface PageArgs { limit?: number; offset?: number; }

// ── Radarr ──────────────────────────────────────────────────────

export type RadarrInstanceStatus = 'unknown' | 'connected' | 'warning' | 'error';
export type RadarrImportStatus = 'none' | 'waiting_for_import' | 'importing' | 'imported' | 'failed';
export type RadarrStorageState = 'local' | 'external_imported' | 'missing' | 'importing' | 'import_failed';

export interface RadarrInstanceResponse {
  id: string;
  name: string;
  baseUrl: string;
  apiKeyPreview: string;
  tubeWritePath: string;
  radarrImportPath: string;
  hostPathHint?: string | null;
  defaultProfileId?: string | null;
  defaultQualityProfileId?: number | null;
  defaultRootFolderPath?: string | null;
  importMode: string;
  enabled: boolean;
  isDefault: boolean;
  status: RadarrInstanceStatus;
  healthMessage?: string | null;
  radarrVersion?: string | null;
  lastSyncAt?: string | null;
  lastTestAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface RadarrInstanceUpsertRequest {
  name: string;
  baseUrl: string;
  apiKey?: string | null;
  tubeWritePath: string;
  radarrImportPath: string;
  hostPathHint?: string | null;
  defaultProfileId?: string | null;
  defaultQualityProfileId?: number | null;
  defaultRootFolderPath?: string | null;
  importMode?: string;
  enabled?: boolean;
}

export interface RadarrInstanceTestRequest {
  baseUrl?: string | null;
  apiKey?: string | null;
  tubeWritePath?: string | null;
}

export interface RadarrInstanceTestResponse {
  ok: boolean;
  canConnect: boolean;
  apiKeyValid: boolean;
  tubeWritePathWritable: boolean;
  radarrRootFoldersLoaded: boolean;
  radarrImportPathVisible?: boolean | null;
  radarrVersion?: string | null;
  warnings: string[];
  errors: string[];
}

export interface RadarrSummaryResponse {
  totalInstances: number;
  activeConnections: number;
  missingMovies: number;
  monitoredMovies: number;
  imports24h: number;
  lastSyncAt?: string | null;
  instanceStatuses: Record<string, number>;
}

export interface RadarrMissingMovie {
  instanceId: string;
  movieId: number;
  title: string;
  year?: number | null;
  tmdbId?: number | null;
  imdbId?: string | null;
  monitored?: boolean | null;
  hasFile?: boolean | null;
  qualityProfileId?: number | null;
  qualityProfileName?: string | null;
  rootFolderPath?: string | null;
  moviePath?: string | null;
  posterUrl?: string | null;
  overview?: string | null;
  radarrUrl?: string | null;
  localWorkflowStatus?: string | null;
  linkedTaskId?: string | null;
}

export interface RadarrMissingMovieListResponse {
  items: RadarrMissingMovie[];
  total: number;
  instance?: Record<string, unknown> | null;
}

export interface RadarrMovieDownloadRequest {
  url: string;
  instanceId?: string | null;
  movieId?: number | null;
  movieTitle?: string | null;
  movieYear?: number | null;
  profileId?: string | null;
  downloadQualityMode?: string | null;
  downloadQualityValue?: number | null;
  downloadFormat?: string | null;
  formatType?: string | null;
  remuxTo?: string | null;
  embedMetadata?: boolean | null;
  embedThumbnail?: boolean | null;
  subtitles?: boolean | null;
  subtitleLangs?: string | null;
}

export interface RadarrTaskIntegrationResponse {
  taskId: string;
  radarrInstanceId: string;
  radarrInstanceName: string;
  radarrMovieId: number;
  title: string;
  year?: number | null;
  downloadStatus: string;
  importStatus: string;
  importMode: string;
  localFilePath?: string | null;
  radarrFilePath?: string | null;
  radarrMovieUrl?: string | null;
  commandId?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface RadarrRootFolder {
  id: number;
  path: string;
  accessible: boolean;
  freeSpace?: number | null;
}

export interface RadarrQualityProfile {
  id: number;
  name: string;
}

export interface RadarrQueueItem {
  movieId: number;
  movieTitle: string;
  status: string;
  size?: number | null;
  progress?: number | null;
}

export interface TaskIntegration {
  type: string;
  instanceId: string;
  instanceName: string;
  movieId: number;
  movieTitle: string;
  movieYear?: number | null;
  importStatus: RadarrImportStatus;
  importMode?: string | null;
  importError?: string | null;
  radarrPath?: string | null;
  localPath?: string | null;
}

// ── Arr (unified Radarr + Sonarr) ────────────────────────────────

export type ArrKind = 'radarr' | 'sonarr';

export interface ArrInstanceResponse {
  id: string;
  kind: ArrKind;
  name: string;
  baseUrl: string;
  apiKeyPreview: string;
  tubeWritePath: string;
  arrImportPath: string;
  hostPathHint?: string | null;
  defaultProfileId?: string | null;
  defaultQualityProfileId?: number | null;
  defaultRootFolderPath?: string | null;
  importMode: string;
  enabled: boolean;
  isDefault: boolean;
  status: string;
  healthMessage?: string | null;
  arrVersion?: string | null;
  lastSyncAt?: string | null;
  lastTestAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ArrInstanceUpsertRequest {
  kind: ArrKind;
  name: string;
  baseUrl: string;
  apiKey?: string | null;
  tubeWritePath: string;
  arrImportPath: string;
  hostPathHint?: string | null;
  defaultProfileId?: string | null;
  defaultQualityProfileId?: number | null;
  defaultRootFolderPath?: string | null;
  importMode?: string;
  enabled?: boolean;
}

export interface ArrInstanceTestRequest {
  baseUrl?: string | null;
  apiKey?: string | null;
  tubeWritePath?: string | null;
}

export interface ArrInstanceTestResponse {
  ok: boolean;
  canConnect: boolean;
  apiKeyValid: boolean;
  tubeWritePathWritable: boolean;
  rootFoldersLoaded: boolean;
  arrVersion?: string | null;
  warnings: string[];
  errors: string[];
}

export interface ArrSummaryResponse {
  totalInstances: number;
  activeConnections: number;
  missingItems: number;
  monitoredItems: number;
  imports24h: number;
  lastSyncAt?: string | null;
  instanceStatuses: Record<string, number>;
}

export interface ArrMissingItem {
  instanceId: string;
  itemId: number;
  kind: ArrKind;
  title: string;
  seriesTitle?: string | null;
  seasonNumber?: number | null;
  episodeNumber?: number | null;
  seriesId?: number | null;
  year?: number | null;
  tmdbId?: number | null;
  imdbId?: string | null;
  monitored?: boolean | null;
  hasFile?: boolean | null;
  qualityProfileId?: number | null;
  qualityProfileName?: string | null;
  rootFolderPath?: string | null;
  itemPath?: string | null;
  posterUrl?: string | null;
  overview?: string | null;
  airDate?: string | null;
  arrUrl?: string | null;
  localWorkflowStatus?: string | null;
  linkedTaskId?: string | null;
}

export interface ArrMissingItemListResponse {
  items: ArrMissingItem[];
  total: number;
  instance?: Record<string, unknown> | null;
}

export interface ArrDownloadRequest {
  kind?: ArrKind | null;
  url: string;
  instanceId?: string | null;
  itemId?: number | null;
  itemTitle?: string | null;
  itemYear?: number | null;
  profileId?: string | null;
  downloadQualityMode?: string | null;
  downloadQualityValue?: number | null;
  downloadFormat?: string | null;
  formatType?: string | null;
  remuxTo?: string | null;
  embedMetadata?: boolean | null;
  embedThumbnail?: boolean | null;
  subtitles?: boolean | null;
  subtitleLangs?: string | null;
}

export interface ArrTaskIntegrationResponse {
  taskId: string;
  arrInstanceId: string;
  arrInstanceName: string;
  arrItemId: number;
  kind: ArrKind;
  title: string;
  year?: number | null;
  downloadStatus: string;
  importStatus: string;
  importMode: string;
  localFilePath?: string | null;
  arrFilePath?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
}

// ── Sonarr-specific ──────────────────────────────────────────────

export interface SonarrSeries {
  id: number;
  title: string;
  year?: number | null;
  tvdbId?: number | null;
  imdbId?: string | null;
  images?: Array<{ coverType: string; url: string }> | null;
  overview?: string | null;
  monitored: boolean;
  seasonCount: number;
  status?: string | null;
  network?: string | null;
  path?: string | null;
  qualityProfileId?: number | null;
  rootFolderPath?: string | null;
}

export interface SonarrEpisode {
  id: number;
  seriesId?: number | null;
  episodeNumber?: number | null;
  seasonNumber?: number | null;
  title?: string | null;
  overview?: string | null;
  airDate?: string | null;
  monitored: boolean;
  hasFile: boolean;
  seriesTitle?: string | null;
  images?: Array<{ coverType: string; url: string }> | null;
}

export interface SonarrEpisodeFile {
  id: number;
  seriesId: number;
  seasonNumber: number;
  relativePath?: string | null;
  path?: string | null;
  size: number;
  dateAdded?: string | null;
  quality?: { quality: { name: string }; revision: Record<string, unknown> } | null;
  mediaInfo?: Record<string, unknown> | null;
}

export interface SonarrRootFolder {
  id: number;
  path: string;
  accessible: boolean;
  freeSpace?: number | null;
}

export interface SonarrQualityProfile {
  id: number;
  name: string;
}

export interface SonarrQueueItem {
  seriesId: number;
  seriesTitle: string;
  episodeId: number;
  status: string;
  size?: number | null;
  progress?: number | null;
}
