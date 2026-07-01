Here is the API completion task list, prioritized for implementation. Source: uploaded OpenAPI spec. 

## P0 — Must fix before API is considered complete

### 1. Add explicit download task creation response ✅

### 2. Add completed download result model ✅

### 3. Add task control APIs ✅

### 4. Expand `TaskResponse` ✅

At minimum, add:

* `progressPercent` ✅
* `updatedAt` ✅
* `completedAt` ✅
* `result` ✅

### 5. Fix SSE response content type ✅

### 6. Add missing `404 Not Found` responses ✅

### 7. Add `409 Conflict` responses ✅

### 8. Fix partial update semantics ✅

## P1 — Important consistency fixes

### 9. Resolve profile identifier inconsistency ✅

### 10. Resolve `format` vs `downloadFormat` ✅

### 11. Enforce quality mode rules ✅

### 12. Add enums for status and type fields

### 13. Clarify outbox lifecycle ← current

### 14. Fix delete profile response schema ✅

---

## P2 — Validation and safety improvements

### 15. Add URL validation

Use `format: uri` for all media URL fields:

* search result URL
* metadata URL
* playlist URL
* download video URL
* download playlist URL
* channel URL
* thumbnail URL

---

### 16. Add string constraints

Add validation for:

* search query `minLength`
* profile name pattern / length
* preset name pattern / length
* file ID pattern
* playlist range pattern
* output extension pattern
* bitrate pattern

Example playlist range pattern:

```regex
^\d+(-\d+)?$
```

---

### 17. Add enums for conversion fields where practical

Consider enums for:

* `container`
* `videoCodec`
* `audioCodec`
* `outputExt`
* `videoPreset`

Only do this if the backend has a known supported set.

---

### 18. Add common error schema

Create a reusable error schema, for example:

* `ErrorResponse`
* or `ProblemDetail`

Use it for:

* `400`
* `404`
* `409`
* `422`
* `500`
* `503`

Do not rely only on FastAPI-style `HTTPValidationError`.

---

### 19. Add operational failure responses

Add documented responses for:

* invalid media URL
* unsupported URL
* extractor failure
* network failure
* ffmpeg missing
* temp directory not writable
* download directory not writable
* conversion preset unavailable
* profile unavailable

---

### 20. Harden `downloadPathOverride`

Either remove it or restrict it.

If kept, document and enforce:

* allowed base directories
* no path traversal
* no protected system paths
* no unsafe overwrite
* absolute path behavior

---

## P3 — Nice-to-have improvements

### 21. Expand health check

Extend `/api/health` to include:

* `hasFfmpeg`
* `ffmpegVersion`
* `hasYtDlp`
* `ytDlpVersion`
* `downloadDirectoryWritable`
* `tempDirectoryWritable`
* `workerRunning`

---

### 22. Add readiness endpoint

Add:

* `GET /api/ready`

Use it for dependency readiness, not just process health.

---

### 23. Add download history/list API

Add one of:

* `GET /api/downloads`
* `GET /api/files`
* `GET /api/library`

Useful fields:

* file ID
* title
* source URL
* created time
* size
* format
* task ID
* local path or download URL

---

### 24. Add file download/open API

Add:

* `GET /api/files/{file_id}/download`

Optional for local-only UI, but useful if the frontend is browser-based.

---

### 25. Add pagination to list endpoints

Add pagination to:

* `GET /api/tasks`
* `GET /api/profiles`
* `GET /api/outbox`
* `GET /api/convert-presets`
* future `GET /api/downloads`

At minimum:

* `limit`
* `offset` or `cursor`

---

## Suggested implementation order

1. Fix download response schemas. ✅
2. Add task result/progress fields. ✅
3. Fix SSE content type. ✅
4. Add 404/409/error schemas. ✅
5. Add cancel/retry/delete task APIs. ✅
6. Resolve `PUT` vs `PATCH`. ✅
7. Resolve profile ID/name and format/downloadFormat inconsistencies. ✅
8. Clarify outbox lifecycle. ← next
9. Add validation constraints and enums. (quality-mode validation ✅, enums ← next)
10. Add health/readiness and file/history APIs.

