import { apiRequest, fileDownloadUrl, qs } from './client';
import type { FileInfo, PageArgs } from './types';

export function listFiles(args: PageArgs = {}) {
  return apiRequest<FileInfo[]>(`/api/files${qs({ limit: args.limit ?? 50, offset: args.offset ?? 0 })}`);
}

export { fileDownloadUrl };
