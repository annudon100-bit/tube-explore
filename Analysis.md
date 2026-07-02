## Overall verdict

The API covers the expected core workflow:

1. Search media.
2. Inspect metadata.
3. Inspect playlists.
4. Start video or playlist downloads.
5. Poll or stream background task status.
6. Manage download profiles.
7. Manage global settings.
8. Manage conversion presets.
9. Handle failed post-processing through an outbox.
10. Check service health.

That is a sensible scope for a simple downloader backend.

The main completeness gap is this: **downloads can be started and monitored, but there is no clearly specified successful output/result model.** The API tells the client that a task exists, but not where the downloaded file is, how to retrieve it, what files were produced, or what happened after completion.

## Important missing APIs or features

### 1. Download start responses do not return the task ID

Both:

* `POST /api/download/video`
* `POST /api/download/playlist`

claim they “return a task ID for status polling,” but the `202` response schema is empty.

This is a major inconsistency. Add a response schema such as:

```json
{
  "taskId": "string",
  "status": "pending",
  "statusUrl": "/api/tasks/{taskId}",
  "streamUrl": "/api/tasks/{taskId}/stream"
}
```

Without this, the client has no contractually defined way to know which task to poll.

### 2. No successful download result / file retrieval API

There is an outbox for failed post-processing, but no equivalent for completed downloads.

Missing options include one or more of:

* `GET /api/tasks/{task_id}/result`
* `GET /api/downloads`
* `GET /api/downloads/{download_id}`
* `GET /api/files/{file_id}`
* `GET /api/files/{file_id}/download`

`TaskResponse` should also include result details when completed, for example:

```json
{
  "status": "completed",
  "result": {
    "files": [
      {
        "id": "string",
        "name": "string",
        "path": "string",
        "size": 12345,
        "mimeType": "video/mp4"
      }
    ]
  }
}
```

For a local-only app, exposing the full path may be acceptable. For anything remotely accessible, prefer opaque file IDs.

### 3. No cancel, retry, or delete task APIs

A downloader needs basic queue/task control. Missing APIs:

* `POST /api/tasks/{task_id}/cancel`
* `POST /api/tasks/{task_id}/retry`
* `DELETE /api/tasks/{task_id}` or `DELETE /api/tasks` for clearing task history

Without cancel, a user cannot stop a large playlist download. Without retry, failed downloads require creating a new download request manually.

### 4. Task status is too thin

`TaskResponse` only has:

* `id`
* `type`
* `url`
* `params`
* `status`
* `createdAt`
* `error`

For a downloader UI, it should probably also include:

* `progressPercent`
* `currentItem`
* `totalItems`
* `downloadedBytes`
* `totalBytes`
* `speed`
* `etaSeconds`
* `startedAt`
* `updatedAt`
* `completedAt`
* `failedAt`
* `outputFiles`
* `outboxFiles`

Even for a simple system, at least `updatedAt`, `completedAt`, `progress`, and `result` would be valuable.

### 5. SSE stream is incorrectly specified

`GET /api/tasks/{task_id}/stream` is described as an SSE stream, but the response content type is declared as `application/json` with an empty schema.

It should use:

```yaml
text/event-stream:
  schema:
    type: string
```

Ideally, the event payload shape should also be documented, for example:

```json
{
  "event": "task.updated",
  "data": {
    "id": "string",
    "status": "running",
    "progressPercent": 42
  }
}
```

### 6. Missing 404 responses for resource lookups

Resource-specific endpoints only define `200` and `422`. They should define `404` for missing IDs or names.

Affected examples:

* `GET /api/tasks/{task_id}`
* `GET /api/profiles/{profile_id}`
* `PUT /api/profiles/{profile_id}`
* `DELETE /api/profiles/{profile_id}`
* `GET /api/convert-presets/{preset_name}`
* `PUT /api/convert-presets/{preset_name}`
* `DELETE /api/convert-presets/{preset_name}`
* `DELETE /api/outbox/{file_id}`
* `POST /api/outbox/{file_id}/process`

`422` is validation failure, not “resource not found.”

### 7. Missing 409 conflict responses

The spec says profile names and preset names must be unique, but create/update endpoints do not define `409 Conflict`.

Add `409` for:

* duplicate profile name
* duplicate conversion preset name
* renaming a profile/preset to an existing name

### 8. Missing domain error responses

A media downloader will commonly hit non-validation failures. The spec should define common error responses such as:

* `400` invalid URL / unsupported URL / invalid range
* `404` task/profile/preset/file not found
* `409` duplicate name or invalid state transition
* `422` schema validation
* `500` internal processing failure
* `503` dependency unavailable, for example missing `ffmpeg`, extractor failure, network failure, or remote platform unavailable

Right now, many operational failures are not modeled.

## Inconsistencies and confusing parts

### 1. `PUT` is being used for partial update

The descriptions for profiles, settings, and conversion presets say “only provided fields are changed.” That is `PATCH` semantics, not normal `PUT`.

Either:

* change these endpoints to `PATCH`, or
* keep `PUT` but define it as full replacement.

Affected endpoints:

* `PUT /api/profiles/{profile_id}`
* `PUT /api/settings`
* `PUT /api/convert-presets/{preset_name}`

### 2. Profile lookup uses ID, but downloads reference profile by name

Profile CRUD uses:

* `/api/profiles/{profile_id}`

But download requests use:

```json
"profile": "string"
```

described as the name of an existing profile.

That can work, but it should be deliberate. Safer options:

* use `profileId` consistently, or
* support both `profileId` and `profileName`, with clear precedence.

### 3. Duplicate/overlapping request fields

Download requests include both:

* `format`
* `downloadFormat`

Profiles include:

* `convertPreset`
* `convertFormat`
* `downloadFormat`

This is confusing. The spec should define exactly what each one means and which one wins when multiple are provided.

For example:

1. Explicit request override wins.
2. Profile value is next.
3. Global setting/default is last.

Without a precedence rule, frontend and backend behavior may drift.

### 4. Quality mode has conditional rules not enforced by schema

`QualityMode` supports:

* `best`
* `least`
* `at_most`
* `at_least`

Descriptions say `at_most` and `at_least` require a pixel height value, but the schemas do not enforce that `downloadQualityValue` or `convertQualityValue` is required for those modes.

This should be enforced either with OpenAPI `oneOf` variants or clearly documented as a runtime validation rule.

### 5. String fields should be constrained

Several fields are plain strings but should have validation hints:

* URL fields should use `format: uri`.
* Search query should have `minLength`.
* `range` should have a pattern, for example `^\d+(-\d+)?$`.
* `container`, `audioCodec`, `videoCodec`, and `outputExt` should probably use enums.
* `task.status` and `outbox.status` should use enums.
* `task.type` should use an enum such as `video` / `playlist`.

### 6. Outbox semantics are a bit unclear

The outbox is described as files that completed download but failed post-processing. Then `/api/outbox/{file_id}/process` says that on success, “the converted file replaces the original in the outbox.”

If processing succeeds, should the file still be in the outbox? Usually no. It should either:

* move to completed downloads, or
* stay in outbox with `status: completed`, but then the outbox is no longer only failed post-processing files.

This needs clarification.

### 7. Delete profile returns an empty schema despite description

`DELETE /api/profiles/{profile_id}` says it returns `{"ok": true}`, but its `200` response schema is `{}`.

It should reference `OkResponse`, like the outbox and conversion preset delete endpoints do.

### 8. Health check is too minimal

`/api/health` only reports:

* `status`
* `hasFfmpeg`

For this app, it would be useful to also include:

* yt-dlp availability/version
* ffmpeg version
* download directory writable
* temp directory writable
* database/storage availability, if applicable
* worker/queue status

For a simple local app, this is not a blocker, but it would improve diagnosability.

## Security and safety gaps

For a local-only tool, these may be acceptable. For anything exposed beyond localhost, they are important.

### 1. No authentication or security scheme

There is no `securitySchemes` section. If this is strictly local, document that clearly. If remote use is possible, add authentication.

### 2. Dangerous path override

`downloadPathOverride` allows an absolute output path. That is risky.

At minimum, document and enforce:

* allowed base directories
* path traversal prevention
* no writing outside configured download roots
* no overwriting protected files unless explicitly allowed

### 3. Arbitrary URL fetching

The API accepts arbitrary media URLs. If exposed remotely, this can become an SSRF-style risk. Consider URL allowlists, extractor restrictions, or local-only binding.

## Recommended minimum fixes before calling it complete

I would not treat this as complete until these are fixed:

1. Add a real `DownloadTaskCreatedResponse` for both download endpoints.
2. Add completed-download result/file information.
3. Fix the SSE content type to `text/event-stream`.
4. Add 404 and 409 responses where appropriate.
5. Add task cancel and retry endpoints.
6. Add progress/result fields to `TaskResponse`.
7. Change partial-update `PUT`s to `PATCH`, or redefine them as full replacements.
8. Resolve `format` vs `downloadFormat` and profile-name vs profile-ID ambiguity.
9. Add enums for task status, task type, outbox status, codecs/containers where practical.
10. Clarify outbox lifecycle after successful processing.

With those changes, the API would look complete and coherent for a simple downloader system.

