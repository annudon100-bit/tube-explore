export type QualityMode = 'best' | 'least' | 'at_most' | 'at_least';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type TaskType = 'video' | 'playlist';
export type OutboxStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type Container = 'mp4' | 'mkv' | 'webm' | 'mp3' | 'flac' | 'm4a' | 'opus' | 'wav' | 'mov' | 'avi';
export type OutputExt = Container;
export type VideoCodec = 'h264' | 'hevc' | 'av1' | 'vp9';
export type AudioCodec = 'aac' | 'mp3' | 'opus' | 'flac' | 'vorbis';

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
  convertPreset?: string | null;
  audioOnly?: boolean;
  downloadQualityMode?: QualityMode | null;
  downloadQualityValue?: number | null;
  downloadFormat?: string | null;
  embedMetadata?: boolean | null;
  embedThumbnail?: boolean | null;
  subtitles?: boolean | null;
  subtitleLangs?: string | null;
}
export interface DownloadVideoRequest extends DownloadRequestBase {}
export interface DownloadPlaylistRequest extends DownloadRequestBase { range?: string | null; }
export interface DownloadTaskCreatedResponse { taskId: string; status: 'pending'; statusUrl: string; streamUrl: string; }

export interface DownloadedFile { id?: string; name: string; size: number; path: string; }
export interface TaskResponse {
  id: string;
  type: TaskType;
  url: string;
  params: Record<string, unknown>;
  status: TaskStatus;
  progressPercent: number;
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
  convertPreset?: string | null;
  convertFormat?: string | null;
  convertQualityMode?: QualityMode | null;
  convertQualityValue?: number | null;
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
  convertPreset?: string | null;
  convertFormat?: string | null;
  convertQualityMode: QualityMode;
  convertQualityValue?: number | null;
  filenameTemplate: string;
  playlistTemplate: string;
  embedMetadata: boolean;
  embedThumbnail: boolean;
  subtitles: boolean;
  subtitleLangs?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConversionPresetBase {
  name?: string | null;
  label?: string | null;
  container?: Container | null;
  videoCodec?: VideoCodec | null;
  videoBitrate?: string | null;
  videoFps?: number | null;
  videoPreset?: string | null;
  videoPixfmt?: string | null;
  audioCodec?: AudioCodec | null;
  audioBitrate?: string | null;
  audioSamplerate?: number | null;
  audioChannels?: number | null;
  maxWidth?: number | null;
  maxHeight?: number | null;
  outputExt?: OutputExt | null;
}
export interface ConversionPresetCreateRequest extends ConversionPresetBase { name: string; container: Container; outputExt: OutputExt; }
export interface ConversionPresetUpdateRequest extends ConversionPresetBase {}
export interface ConversionPresetResponse extends ConversionPresetCreateRequest {
  id: number;
  label: string;
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
}

export interface OutboxEntry {
  id: string;
  name: string;
  size: number;
  mediaUrl?: string | null;
  taskId?: string | null;
  qualityMode?: string | null;
  qualityValue?: number | null;
  convertPreset?: string | null;
  status: OutboxStatus;
  error?: string | null;
  createdAt: string;
  updatedAt?: string | null;
}
export interface OutboxProcessRequest { preset: string; downloadDirectory?: string | null; }

export interface PageArgs { limit?: number; offset?: number; }
