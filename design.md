# Tube Explore UI Coverage Requirements

## 1. Primary Input Coverage

The UI must support entering:

* Search query
* Direct media URL
* Playlist URL

The UI must support these user intents:

* Search media
* Inspect media metadata
* Inspect playlist contents
* Start video download
* Start playlist download

Input validation must cover:

* Search query is required and must not be empty
* Media URL must start with `http://` or `https://`
* Playlist URL must start with `http://` or `https://`
* API validation errors must be shown near the relevant input when possible

---

## 2. Search Coverage

The UI must support:

* Search query input
* Result limit input or selector
* Result limit range: `1–50`
* Search submit action
* Loading state
* Empty result state
* Validation error state
* API failure state

Each search result must be able to show:

* Thumbnail
* Title
* Media ID
* Source URL
* Duration
* Channel name
* Channel URL

Each search result must support actions for:

* Inspect metadata
* Start video download
* Copy/open source URL

Search failure handling must cover:

* Validation error
* Extractor failure
* Network failure
* Unsupported or invalid media source

---

## 3. Media Metadata Coverage

The UI must support metadata lookup by media URL.

Metadata results must be able to show:

* Media ID
* Title
* Source URL
* Duration
* Channel name
* Channel URL
* Thumbnail
* Description
* View count
* Like count
* Best available height
* Available formats

Each available format must be able to show:

* Format ID
* Extension
* Width
* Height
* File size
* Video codec
* Audio codec
* Audio bitrate
* Video bitrate
* Frames per second

Metadata actions must include:

* Start video download using the inspected URL
* Select/copy format ID
* Copy/open media URL
* Copy/open channel URL, when available

Metadata failure handling must cover:

* Invalid URL
* Unsupported URL
* Extractor failure
* Network failure
* Validation error

---

## 4. Playlist Coverage

The UI must support playlist lookup by playlist URL.

Playlist summary must be able to show:

* Playlist URL
* Entry count
* Total duration

Each playlist entry must be able to show:

* Media ID
* Title
* Source URL
* Duration
* Channel name

Playlist actions must include:

* Start playlist download
* Start video download for an individual playlist entry
* Copy/open playlist URL
* Copy/open individual entry URL

Playlist download range input must support:

* Single index, for example `3`
* Index range, for example `1-5`

Playlist failure handling must cover:

* Invalid URL
* Unsupported URL
* Extractor failure
* Network failure
* Validation error

---

## 5. Video Download Coverage

The UI must support starting a video download.

Required field:

* Media video URL

Optional fields:

* Output subdirectory
* Absolute download path override
* Profile ID/name value used by the API field `profileId`
* Conversion preset name
* Audio-only toggle
* Download quality mode
* Download quality value
* Download format
* Embed metadata toggle
* Embed thumbnail toggle
* Download subtitles toggle
* Subtitle languages

Quality mode must support:

* `best`
* `least`
* `at_most`
* `at_least`

When quality mode is `at_most` or `at_least`, the UI must allow a pixel-height quality value.

Download path override validation must account for protected system paths. The UI must not encourage users to select or enter paths under protected system directories such as:

* `/etc`
* `/bin`
* `/usr`
* `/sys`
* `/proc`
* `/dev`
* `/boot`
* `/lib`
* `/root`
* `/var`
* `/run`

After a successful submit, the UI must handle and expose:

* Task ID
* Initial status: `pending`
* Status URL
* Stream URL

Download failure handling must cover:

* Validation error
* Profile or preset not found
* Invalid or unsupported media URL
* Extractor failure
* Network failure
* ffmpeg unavailable
* Temporary directory not writable
* Download directory not writable

---

## 6. Playlist Download Coverage

The UI must support starting a playlist download.

Required field:

* Playlist URL

Optional fields:

* Output subdirectory
* Absolute download path override
* Profile ID/name value used by the API field `profileId`
* Playlist item range
* Conversion preset name
* Audio-only toggle
* Download quality mode
* Download quality value
* Download format
* Embed metadata toggle
* Embed thumbnail toggle
* Download subtitles toggle
* Subtitle languages

Playlist range validation must support:

* `1`
* `1-5`
* `3-10`

After a successful submit, the UI must handle and expose:

* Task ID
* Initial status: `pending`
* Status URL
* Stream URL

Playlist download failure handling must cover:

* Validation error
* Profile or preset not found
* Invalid or unsupported playlist URL
* Extractor failure
* Network failure
* ffmpeg unavailable
* Temporary directory not writable
* Download directory not writable

---

## 7. Task List Coverage

The UI must support listing download tasks.

Task list controls must include:

* Limit
* Offset

Task list validation must support:

* Limit range: `1–200`
* Offset minimum: `0`

Each task must be able to show:

* Task ID
* Task type
* Source URL
* Parameters
* Status
* Progress percent
* Created time
* Updated time
* Completed time
* Error message
* Result files, when present

Task type values must support:

* `video`
* `playlist`

Task status values must support:

* `pending`
* `running`
* `completed`
* `failed`
* `cancelled`

---

## 8. Individual Task Coverage

The UI must support opening/viewing an individual task by task ID.

Individual task view must show:

* Task ID
* Task type
* Source URL
* Parameters
* Status
* Progress percent
* Created time
* Updated time
* Completed time
* Error message
* Result files

Individual task actions must include:

* Cancel task
* Retry failed task
* Delete task
* View task result
* Open/download result files where file IDs are available

Cancel task must be available only for tasks that can be cancelled, such as pending or running tasks.

Retry task must be available for failed tasks and must create a new task with:

* New task ID
* New status URL
* New stream URL

Delete task must be treated as removal from task memory. The UI must handle conflict errors when a task cannot be deleted because of its current state.

Task result coverage must include:

* Task ID
* Task status
* Produced files

Each produced file must be able to show:

* File ID, when available
* File name
* File size
* Absolute file path

---

## 9. Real-Time Task Monitoring Coverage

The UI must support real-time task updates through the task stream endpoint.

The UI must also support non-streaming refresh through normal task polling.

Real-time task updates must account for:

* Initial state sent immediately
* Status changes
* Progress percent changes
* Completion
* Failure
* Cancellation
* Keepalive behavior
* Stream unavailable or task not found

For failed tasks, the UI must clearly show:

* Failed status
* Error message
* Source URL
* Task parameters
* Retry action, where allowed

---

## 10. Downloaded Files Coverage

The UI must support listing completed downloaded files.

Downloaded files list controls must include:

* Limit
* Offset

Validation must support:

* Limit range: `1–200`
* Offset minimum: `0`

Each file must be able to show:

* File ID
* File name
* File size
* Absolute path
* Producing task ID
* Source URL
* Created time

Each file must support:

* Download file by file ID
* Copy file path
* Copy/open source URL, when available
* Open related task, when task ID is available

The UI must handle file download responses as binary downloads.

---

## 11. Download Profile Coverage

The UI must support:

* List profiles
* Create profile
* View profile
* Edit profile
* Delete profile

Profile list controls must include:

* Limit
* Offset

Validation must support:

* Limit range: `1–200`
* Offset minimum: `0`

Profile list items must be able to show:

* Profile ID
* Name
* Label
* Download directory
* Download format
* Download quality mode
* Download quality value
* Conversion preset
* Convert format
* Convert quality mode
* Convert quality value
* Filename template
* Playlist template
* Embed metadata setting
* Embed thumbnail setting
* Subtitle setting
* Subtitle languages
* Created time
* Updated time

Profile create must support:

* Name
* Label
* Download directory
* Download format
* Download quality mode
* Download quality value
* Conversion preset
* Convert format
* Convert quality mode
* Convert quality value
* Filename template
* Playlist template
* Embed metadata toggle
* Embed thumbnail toggle
* Subtitles toggle
* Subtitle languages

Profile edit must support patch behavior: omitted fields keep their current values.

Profile name validation must cover:

* Required for create
* Minimum length: `1`
* Maximum length: `64`
* Allowed characters: letters, numbers, spaces, underscore, and hyphen
* Must be unique

Profile quality modes must support:

* `best`
* `least`
* `at_most`
* `at_least`

Profile delete must include confirmation.

Profile failure handling must cover:

* Not found
* Duplicate/conflict
* Validation error

---

## 12. Conversion Preset Coverage

The UI must support:

* List conversion presets
* Create conversion preset
* View conversion preset
* Edit conversion preset
* Delete conversion preset

Conversion preset list controls must include:

* Limit
* Offset

Validation must support:

* Limit range: `1–200`
* Offset minimum: `0`

Conversion preset list items must be able to show:

* Preset ID
* Name
* Label
* Container
* Output extension
* Video codec
* Video bitrate
* Video frame rate
* Video encoding preset
* Video pixel format
* Audio codec
* Audio bitrate
* Audio sample rate
* Audio channel count
* Maximum output width
* Maximum output height
* Created time
* Updated time

Conversion preset create must support:

* Name
* Label
* Output container
* Output extension
* Video codec
* Video bitrate
* Video frame rate
* Video encoding preset
* Video pixel format
* Audio codec
* Audio bitrate
* Audio sample rate
* Audio channel count
* Maximum output width
* Maximum output height

Conversion preset edit must support patch behavior: omitted fields keep their current values.

Preset name validation must cover:

* Required for create
* Minimum length: `1`
* Maximum length: `64`
* Allowed characters: letters, numbers, spaces, underscore, and hyphen
* Must be unique

Container options must include:

* `mp4`
* `mkv`
* `webm`
* `mp3`
* `flac`
* `m4a`
* `opus`
* `wav`
* `mov`
* `avi`

Output extension options must include:

* `mp4`
* `mkv`
* `webm`
* `mp3`
* `m4a`
* `flac`
* `opus`
* `wav`
* `mov`
* `avi`

Video codec options must include:

* `h264`
* `hevc`
* `av1`
* `vp9`

Audio codec options must include:

* `aac`
* `mp3`
* `opus`
* `flac`
* `vorbis`

Bitrate inputs must support values matching examples such as:

* `128k`
* `5M`
* `1.5M`

Preset delete must include confirmation.

Preset failure handling must cover:

* Not found
* Duplicate/conflict
* Validation error

The UI must allow selecting conversion presets from:

* Video download flow
* Playlist download flow
* Profile create/edit flow
* Outbox retry conversion flow

---

## 13. Global Settings Coverage

The UI must support viewing and updating global settings.

Settings fields must include:

* Rate limit
* Temporary directory
* Retry count
* Socket timeout

Settings edit must support patch behavior: omitted fields keep their current values.

Settings actions and states must include:

* Save settings
* Saved/success state
* Validation error state
* API error state

---

## 14. Health and Readiness Coverage

The UI must surface service health.

Health details must include:

* Service status
* ffmpeg availability
* ffmpeg version
* yt-dlp availability
* yt-dlp version
* Download directory writability
* Temporary directory writability
* Worker running status

The UI must also support readiness status from the readiness endpoint.

Health warnings must be reflected anywhere relevant, especially:

* Video download with conversion preset
* Playlist download with conversion preset
* Outbox retry conversion
* Failed post-processing explanation
* Download directory selection/path override
* Temporary directory settings

---

## 15. Outbox Coverage

The UI must support listing outbox files.

Outbox list controls must include:

* Limit
* Offset

Validation must support:

* Limit range: `1–200`
* Offset minimum: `0`

Each outbox item must be able to show:

* File ID
* File name
* File size
* Source media URL
* Related task ID
* Quality mode
* Quality value
* Conversion preset attempted
* Processing status
* Error message
* Created time
* Updated time

Outbox status values must support:

* `pending`
* `processing`
* `completed`
* `failed`

Outbox item actions must include:

* Delete outbox file
* Retry conversion using selected conversion preset

Retry conversion must support:

* Conversion preset name
* Optional download directory for the converted file

Outbox delete must include confirmation.

The UI must explain that outbox files are downloads that completed but failed post-processing, commonly because ffmpeg was missing or conversion failed.

On successful outbox processing, the UI must account for the outbox entry being removed and the converted file being moved to the target download directory.

Outbox failure handling must cover:

* File not found
* Bad request
* Validation error
* Conversion failure

---

## 16. Shared Error Coverage

The UI must support these API error categories:

* `400` bad request
* `404` resource not found
* `409` conflict
* `422` validation error
* `500` operation failure
* `503` service unavailable

Error display must support:

* Human-readable error message from `detail`
* Field-level validation details from validation errors
* Retry option where safe
* Clear distinction between validation problems and backend/service failures

Common operation failures must include user-facing handling for:

* Invalid media URL
* Unsupported URL
* Extractor failure
* Network failure
* Missing ffmpeg
* Temp directory not writable
* Download directory not writable
* Duplicate profile name
* Duplicate preset name
* Task state conflict

---

## 17. Shared Input Components

The UX design must account for reusable controls for:

* URL input
* Search input
* Numeric input
* Toggle input
* Quality mode selector
* Conversion preset selector
* Profile selector
* Container selector
* Output extension selector
* Video codec selector
* Audio codec selector
* Bitrate input
* Format string input
* Directory/path input
* Subtitle language input
* Filename template input
* Playlist template input
* Limit/offset pagination controls
* Confirmation action
* Error display
* Loading indicator
* Empty state
* Progress indicator
* Status badge

---

## 18. Shared Status and Feedback Requirements

The UI must support these common states:

* Initial state
* Loading state
* Empty state
* Success state
* Validation error state
* API/server error state
* Service unavailable state
* Long-running task state
* Task progress state
* Failed task state
* Cancelled task state
* Missing ffmpeg warning state
* Directory not writable warning state
* Worker not running warning state

The UI must use visible status indicators for:

* Task status
* Task progress percent
* Outbox processing status
* ffmpeg availability
* yt-dlp availability
* Directory writability
* Worker status
* Successful create/update/delete actions
* Failed API actions

---

## 19. Responsive Design Requirements

The UI must work on:

* Desktop
* Tablet
* Mobile

The design must ensure that the following remain usable on smaller screens:

* Search results
* Metadata format lists
* Playlist entries
* Task list
* Task detail/result view
* Downloaded files list
* Profile create/edit forms
* Conversion preset create/edit forms
* Outbox list
* Settings form
* Health/readiness indicators

Dense tables must have a mobile-friendly alternative layout.

---

## 20. Explicitly Out of Scope Unless Backend Adds APIs

The UX must not design primary flows for:

* User login/logout
* User account management
* Permissions or roles
* Task pause/resume
* Bulk task actions
* Bulk file actions
* Bulk profile actions
* Bulk preset actions
* Storage usage dashboard
* Scheduling downloads
* Browser extension behavior
* Editing or deleting downloaded files from the files list
* Moving downloaded files after completion
* Streaming/previewing media files in the browser

