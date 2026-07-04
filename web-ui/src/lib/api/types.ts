export type QualityMode = 'best' | 'least' | 'at_most' | 'at_least';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
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
export interface TaskResultResponse { taskId: string; status: TaskStatus; files: DownloadedFile[]; }

export interface FileInfo { id?: string; name: string; size: number; path: string; taskId: string; sourceUrl?: string | null; createdAt: string; }

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

export interface SettingsResponse { rateLimit: string; tempDirectory: string; retryCount: number; socketTimeout: number; }
export interface SettingsUpdateRequest { rateLimit?: string | null; tempDirectory?: string | null; retryCount?: number | null; socketTimeout?: number | null; }

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
