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

### 12. Add enums for status and type fields ✅

### 13. Clarify outbox lifecycle ✅

### 14. Fix delete profile response schema ✅

---

## P2 — Validation and safety improvements

### 15. Add URL validation ✅

Use `format: uri` for all media URL fields:

* search result URL
* metadata URL
* playlist URL
* download video URL
* download playlist URL
* channel URL
* thumbnail URL

---

### 16. Add string constraints ✅

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

### 17. Add enums for conversion fields where practical ✅

Consider enums for:

* `container` ✅
* `videoCodec` ✅
* `audioCodec` ✅
* `outputExt` ✅
* `videoPreset` — skipped, too open-ended

---

### 18. Add common error schema ✅

Create a reusable error schema, for example:

* `ErrorResponse` ✅
* or `ProblemDetail`

Use it for:

* `400` ✅
* `404` ✅
* `409` ✅
* `422` ✅
* `500` ✅
* `503`

No longer rely only on FastAPI-style `HTTPValidationError`. Added exception handlers for `RequestValidationError` and `HTTPException` to return `ErrorResponse` format consistently. Added `_400`, `_422`, `_500` response doc dicts and annotated search/metadata/playlist/outbox endpoints with missing error responses.

---

### 19. Add operational failure responses ✅

Add documented responses for:

* invalid media URL ✅ — documented in `_500` on search/metadata/playlist/dowload endpoints
* unsupported URL ✅ — same
* extractor failure ✅ — same
* network failure ✅ — same
* ffmpeg missing ✅ — documented as `_503` on download endpoints, `_400` on process_outbox_file
* temp directory not writable ✅ — documented as `_503` on download endpoints
* download directory not writable ✅ — documented as `_503` on download endpoints
* conversion preset unavailable ✅ — documented as `_404` on download/process endpoints
* profile unavailable ✅ — documented as `_404` on download endpoints

---

### 20. Harden `downloadPathOverride` ✅

Either remove it or restrict it.

If kept, document and enforce:

* allowed base directories ✅ — path validated against protected system directories blocklist
* no path traversal ✅ — uses `os.path.realpath()` to resolve symlinks
* no protected system paths ✅ — blocks /etc, /bin, /usr, /sys, /proc, /dev, /boot, /lib, /root, /var, /run, /opt, /snap
* no unsafe overwrite ✅ — yt-dlp uses `--no-overwrites`
* absolute path behavior ✅ — documented in schema description, validated on use

---

## P3 — Nice-to-have improvements

### 21. Expand health check ✅

### 22. Add readiness endpoint ✅

### 23. Add download history/list API ✅

### 24. Add file download/open API ✅

Optional for local-only UI, but useful if the frontend is browser-based.

---

### 25. Add pagination to list endpoints ✅

Add pagination to:

* `GET /api/tasks` ✅ — added `limit` (1-200, default 50) and `offset` (0+) query params
* `GET /api/profiles` ✅ — same
* `GET /api/outbox` ✅ — same
* `GET /api/convert-presets` ✅ — same
* `GET /api/files` ✅ — same

---

## Suggested implementation order

1. Fix download response schemas. ✅
2. Add task result/progress fields. ✅
3. Fix SSE content type. ✅
4. Add 404/409/error schemas. ✅
5. Add cancel/retry/delete task APIs. ✅
6. Resolve `PUT` vs `PATCH`. ✅
7. Resolve profile ID/name and format/downloadFormat inconsistencies. ✅
8. Clarify outbox lifecycle. ✅
9. Add validation constraints and enums. ✅
10. Add health/readiness and file/history APIs. ✅
11. Add URL validation. ✅
12. Add string constraints. ✅
13. Add conversion field enums. ✅
14. Add common error schema. ✅
15. Add operational failure responses. ✅
16. Harden downloadPathOverride. ✅
17. Add pagination to list endpoints. ✅

