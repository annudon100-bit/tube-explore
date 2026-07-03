<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import DownloadOptionsForm from '../DownloadOptionsForm.svelte';
  import MiniPartsBar from './MiniPartsBar.svelte';
  import StatsGrid from './StatsGrid.svelte';
  import ProgressBar from '$lib/components/shared/ProgressBar.svelte';
  import { startPlaylistDownload } from '$lib/api/downloads';
  import { showToast } from '$lib/state/toast-state';
  import { tasks } from '$lib/state/event-stream';
  import { duration, clampPercent } from '$lib/utils/format';
  import { API_BASE_URL } from '$lib/config/env';
  import type { DownloadPlaylistRequest, ProfileResponse, TaskResponse, ProgressStep } from '$lib/api/types';

  export let url = '';
  export let profiles: ProfileResponse[] = [];
  export let onClose: () => void = () => {};
  export let onCreated: (taskId: string) => void = () => {};

  let form: Partial<DownloadPlaylistRequest> = { url, embedMetadata: true, embedThumbnail: true };
  let busy = false;
  let error: string | null = null;
  let taskId: string | null = null;

  let currentTask: TaskResponse | null = null;

  function submit() {
    error = null;
    busy = true;
    startPlaylistDownload(form as DownloadPlaylistRequest)
      .then(result => {
        taskId = result.taskId;
        showToast(`Playlist download queued: ${result.taskId}`);
        onCreated(result.taskId);
      })
      .catch(e => {
        error = e instanceof Error ? e.message : 'Failed to start playlist download';
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
  $: fileList = currentTask?.fileProgress ?? [];
  $: totalItems = currentTask?.totalItems ?? 0;
  $: currentIndex = currentTask?.currentIndex ?? 0;

  function cancel() {
    if (taskId) {
      import('$lib/api/tasks').then(({ cancelTask }) => {
        cancelTask(taskId!).catch(() => {});
      });
    }
  }

  function closeAndCleanup() {
    onClose();
  }
</script>

<ModalFrame title={isLive ? 'Downloading playlist…' : 'New playlist download'} onClose={closeAndCleanup}>
  <ErrorMessage message={error} />

  {#if !isLive}
    <DownloadOptionsForm value={form} {profiles} isPlaylist onChange={(v) => form = v} />
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
        <h3 class="video-title">{currentTask?.title || 'Playlist'}</h3>
        {#if currentTask?.channel}
          <span class="video-channel">{currentTask.channel}</span>
        {/if}
      </div>
    </div>

    <div class="progress-section">
      <div class="progress-header">
        <span class="pct-label">{pct}% overall</span>
        {#if totalItems > 0}
          <span class="items-label">Item {Math.min(currentIndex + 1, totalItems)} of {totalItems}</span>
        {/if}
      </div>
      <ProgressBar value={pct} />
    </div>

    <StatsGrid
      speed={currentTask?.speed}
      eta={currentTask?.eta}
      totalBytes={currentTask?.totalBytes}
      downloadedBytes={currentTask?.downloadedBytes}
      elapsed={currentTask?.elapsed}
      {step}
    />

    {#if fileList.length > 0}
      <div class="playlist-items">
        <div class="items-header">Videos</div>
        {#each fileList as file, i}
          <div class="playlist-item" class:active={i === currentIndex} class:done={file.status === 'completed'} class:pending={file.status === 'pending'}>
            <span class="item-index">{i + 1}</span>
            <span class="item-title">{file.title || `Video ${i + 1}`}</span>
            <div class="item-meta">
              {#if file.status === 'downloading'}
                <span class="item-pct">{file.percent}%</span>
                {#if file.speed}
                  <span class="item-speed">{file.speed}</span>
                {/if}
              {:else if file.status === 'completed'}
                <span class="item-done">✓</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}

    <div class="action-row live-actions">
      <button class="btn orange" disabled>Pause (coming soon)</button>
      <button class="btn red" on:click={cancel} disabled={currentTask?.status !== 'running'}>
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

  .progress-section {
    margin-bottom: 14px;
  }
  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .pct-label {
    font-size: 20px;
    font-weight: 900;
    font-variant-numeric: tabular-nums;
  }
  .items-label {
    font-size: 13px;
    color: var(--muted);
  }

  .playlist-items {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin-top: 16px;
    max-height: 320px;
    overflow-y: auto;
  }
  .items-header {
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
    padding: 0 4px;
  }
  .playlist-item {
    display: grid;
    grid-template-columns: 28px 1fr auto;
    gap: 8px;
    align-items: center;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    transition: background 0.2s;
  }
  .playlist-item.active {
    background: rgba(124, 60, 255, 0.15);
  }
  .playlist-item.done {
    opacity: 0.7;
  }
  .playlist-item.pending {
    opacity: 0.5;
  }
  .item-index {
    font-size: 12px;
    font-weight: 700;
    color: var(--muted);
    text-align: center;
  }
  .item-title {
    font-size: 13px;
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .item-meta {
    display: flex;
    gap: 8px;
    font-size: 11px;
    color: var(--muted);
  }
  .item-pct {
    font-variant-numeric: tabular-nums;
  }
  .item-speed {
    color: var(--purple-light);
  }
  .item-done {
    color: var(--green);
  }

  .live-actions {
    justify-content: flex-end;
    margin-top: 20px;
  }
</style>
