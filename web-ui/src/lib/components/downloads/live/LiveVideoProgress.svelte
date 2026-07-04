<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import DownloadOptionsForm from '../DownloadOptionsForm.svelte';
  import MiniPartsBar from './MiniPartsBar.svelte';
  import StatsGrid from './StatsGrid.svelte';
  import ProgressBar from '$lib/components/shared/ProgressBar.svelte';
  import { startVideoDownload } from '$lib/api/downloads';
  import { pauseTask, resumeTask } from '$lib/api/tasks';
  import { showToast } from '$lib/state/toast-state';
  import { tasks } from '$lib/state/event-stream';
  import { duration, clampPercent } from '$lib/utils/format';
  import { API_BASE_URL } from '$lib/config/env';
  import type { DownloadVideoRequest, ProfileResponse, TaskResponse, ProgressStep } from '$lib/api/types';

  export let url = '';
  export let profiles: ProfileResponse[] = [];
  export let onClose: () => void = () => {};
  export let onCreated: (taskId: string) => void = () => {};

  let form: Partial<DownloadVideoRequest> = { url, embedMetadata: true, embedThumbnail: true };
  let busy = false;
  let error: string | null = null;
  let taskId: string | null = null;

  let currentTask: TaskResponse | null = null;

  function submit() {
    error = null;
    busy = true;
    startVideoDownload(form as DownloadVideoRequest)
      .then(result => {
        taskId = result.taskId;
        showToast(`Download queued: ${result.taskId}`);
        onCreated(result.taskId);
      })
      .catch(e => {
        error = e instanceof Error ? e.message : 'Failed to start download';
        busy = false;
      });
  }

  $: if (taskId) {
    const updated = $tasks.find(t => t.id === taskId);
    if (updated) {
      currentTask = updated;
      if (updated.status === 'completed' || updated.status === 'failed' || updated.status === 'cancelled') {
        busy = false;
      }
    }
  }

  $: pct = clampPercent(currentTask?.progressPercent);
  $: step = (currentTask?.progressStep as ProgressStep | undefined) ?? null;
  $: thumbnailUrl = currentTask?.thumbnailPath ? `${API_BASE_URL}${currentTask.thumbnailPath}` : null;
  $: isLive = taskId && currentTask && currentTask.status !== 'pending';
  $: isPaused = currentTask?.status === 'paused';

  function cancel() {
    if (taskId) {
      import('$lib/api/tasks').then(({ cancelTask }) => {
        cancelTask(taskId!).catch(() => {});
      });
    }
  }

  async function doPause() {
    if (!taskId) return;
    try { await pauseTask(taskId); showToast('Download paused'); } catch (e) { showToast(e instanceof Error ? e.message : 'Unable to pause'); }
  }

  async function doResume() {
    if (!taskId) return;
    try { await resumeTask(taskId); showToast('Download resumed'); } catch (e) { showToast(e instanceof Error ? e.message : 'Unable to resume'); }
  }

  function closeAndCleanup() {
    onClose();
  }
</script>

<ModalFrame title={isLive ? 'Downloading…' : 'New video download'} onClose={closeAndCleanup}>
  <ErrorMessage message={error} />

  {#if !isLive}
    <DownloadOptionsForm value={form} {profiles} onChange={(v) => form = v} />
    <div class="dialog-actions">
      <button class="btn" on:click={closeAndCleanup}>Cancel</button>
      <button class="btn primary" disabled={busy || !form.url} on:click={submit}>
        {busy ? 'Starting…' : 'Start download'}
      </button>
    </div>
  {:else}
    <div class="live-layout">
      {#if thumbnailUrl}
        <img class="thumb" src={thumbnailUrl} alt="" />
      {:else}
        <div class="thumb placeholder"></div>
      {/if}

      <div class="meta-area">
        <h3 class="video-title">{currentTask?.title || 'Untitled'}</h3>
        {#if currentTask?.channel}
          <span class="video-channel">{currentTask.channel}</span>
        {/if}
        {#if currentTask?.duration}
          <span class="video-duration">{duration(currentTask.duration)}</span>
        {/if}
      </div>
    </div>

    <div class="phase-bar">
      <div class="phase-segment" class:active={step === 'fetching_metadata'}>Metadata</div>
      <div class="phase-segment" class:active={step === 'preparing'}>Ready</div>
      <div class="phase-segment" class:active={step === 'downloading'} class:done={pct >= 72}>Download</div>
      <div class="phase-segment" class:active={step === 'merging'} class:skipped={currentTask?.totalItems === undefined}>Merge</div>
      <div class="phase-segment" class:active={step === 'converting'} class:skipped={true}>Convert</div>
      <div class="phase-segment" class:active={step === 'finalizing'}>Finalize</div>
    </div>

    <div class="progress-section">
      <div class="progress-header">
        <span class="pct-label">{pct}%</span>
        {#if currentTask?.status === 'running' && currentTask?.speed}
          <span class="speed-label">{currentTask.speed}</span>
        {/if}
      </div>
      <ProgressBar value={pct} />
    </div>

    <div class="bar-label">Parts</div>
    <MiniPartsBar percent={pct} segments={12} />

    <StatsGrid
      speed={currentTask?.speed}
      eta={currentTask?.eta}
      totalBytes={currentTask?.totalBytes}
      downloadedBytes={currentTask?.downloadedBytes}
      elapsed={currentTask?.elapsed}
      {step}
    />

    <div class="action-row live-actions">
      {#if isPaused}
        <button class="btn green" on:click={doResume}>Resume</button>
      {:else}
        <button class="btn orange" on:click={doPause} disabled={currentTask?.status !== 'running'}>Pause</button>
      {/if}
      <button class="btn red" on:click={cancel} disabled={currentTask?.status !== 'running' && !isPaused}>
        Cancel
      </button>
    </div>
  {/if}
</ModalFrame>

<style>
  .live-layout {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 20px;
  }
  .thumb {
    width: 120px;
    height: 68px;
    border-radius: 12px;
    object-fit: cover;
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.06);
  }
  .thumb.placeholder {
    width: 120px;
    height: 68px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.06);
  }
  .meta-area {
    display: grid;
    gap: 4px;
    min-width: 0;
  }
  .video-title {
    margin: 0;
    font-size: 16px;
    font-weight: 800;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .video-channel {
    font-size: 13px;
    color: var(--muted);
  }
  .video-duration {
    font-size: 13px;
    color: var(--muted);
  }

  .phase-bar {
    display: flex;
    gap: 0;
    margin-bottom: 16px;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .phase-segment {
    flex: 1;
    text-align: center;
    padding: 8px 4px;
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    background: rgba(255, 255, 255, 0.03);
    transition: background 0.3s, color 0.3s;
  }
  .phase-segment.active {
    color: white;
    background: rgba(124, 60, 255, 0.25);
  }
  .phase-segment.done {
    color: var(--green);
    background: rgba(21, 211, 139, 0.1);
  }
  .phase-segment.skipped {
    opacity: 0.3;
  }

  .progress-section {
    margin-bottom: 16px;
  }
  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .pct-label {
    font-size: 24px;
    font-weight: 900;
    font-variant-numeric: tabular-nums;
  }
  .speed-label {
    font-size: 13px;
    color: var(--muted);
  }

  .bar-label {
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
  }

  .live-actions {
    justify-content: flex-end;
    margin-top: 20px;
  }
</style>
