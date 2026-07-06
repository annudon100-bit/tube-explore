import { apiRequest, fileDownloadUrl, qs } from './client';
import type { FileInfo, FilesListResponse, FileStatsResponse, PageArgs } from './types';

export interface FileListArgs extends PageArgs {
  search?: string;
  fileType?: string;
  sortBy?: 'name' | 'size' | 'created_at';
  sortOrder?: 'asc' | 'desc';
}

export function listFiles(args: FileListArgs = {}) {
  return apiRequest<FilesListResponse>(`/api/files${qs({
    limit: args.limit ?? 50,
    offset: args.offset ?? 0,
    search: args.search,
    fileType: args.fileType,
    sortBy: args.sortBy,
    sortOrder: args.sortOrder,
  })}`);
}

export function getFileStats() {
  return apiRequest<FileStatsResponse>('/api/files/stats');
}

export { fileDownloadUrl };
