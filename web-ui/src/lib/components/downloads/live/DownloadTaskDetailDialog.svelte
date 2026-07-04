<script lang="ts">
  import { cancelTask, retryTask } from '$lib/api/tasks';
  import { tasks } from '$lib/state/event-stream';
  import { showToast } from '$lib/state/toast-state';
  import { bytes, duration as fmtDuration, clampPercent } from '$lib/utils/format';
  import { API_BASE_URL } from '$lib/config/env';
  import type { TaskResponse, ProgressStep } from '$lib/api/types';

  export let task: TaskResponse;
  export let onClose: () => void = () => {};
  export let onChanged: () => void = () => {};

  let current = task;
  let paused = false;

  $: {
    const updated = $tasks.find(t => t.id === current.id);
    if (updated) current = updated;
  }

  $: pct = clampPercent(current.progressPercent);
  $: step = (current.progressStep as ProgressStep | undefined) ?? null;
  $: isVideo = current.type === 'video';
  $: thumbnailUrl = current.thumbnailPath ? `${API_BASE_URL}${current.thumbnailPath}` : null;
  $: fileList = current.fileProgress ?? [];
  $: activeIdx = fileList.findIndex(f => f.status === 'downloading');
  $: totalItems = current.totalItems ?? 0;
  $: currentIndex = current.currentIndex ?? 0;

  $: statusLabel = (() => {
    if (current.status === 'cancelled') return 'Cancelled';
    if (current.status === 'completed') return 'Completed';
    if (paused) return 'Paused';
    if (current.status === 'pending') return 'Starting';
    if (current.status === 'failed') return 'Failed';
    if (step === 'fetching_metadata') return 'Fetching metadata';
    if (step === 'preparing') return 'Preparing download';
    if (step === 'downloading') return 'Downloading parts';
    if (step === 'merging') return 'Merging parts';
    if (step === 'converting') return 'Converting';
    if (step === 'finalizing') return 'Finalizing';
    return 'Running';
  })();

  $: activityText = (() => {
    if (current.status === 'cancelled') return 'Task cancelled';
    if (current.status === 'completed') return 'Download complete';
    if (paused) return `Paused — ${stepLabel}`;
    if (step === 'fetching_metadata') return 'Fetching metadata…';
    if (step === 'preparing') return 'Preparing download…';
    if (step === 'downloading') return 'Downloading parts…';
    if (step === 'merging') return 'Merging parts…';
    if (step === 'converting') return 'Converting to MP4…';
    if (step === 'finalizing') return 'Finalizing file…';
    if (current.status === 'pending') return 'Waiting to start…';
    return 'Processing…';
  })();

  $: stepLabel = progressStepLabel(step);

  $: progressLabel = (() => {
    if (current.status === 'cancelled') return 'Stopped before completion';
    if (current.status === 'completed') return 'File is ready';
    if (step === 'fetching_metadata') return 'Reading title, duration, thumbnail, and streams';
    if (step === 'preparing') return 'Selecting streams and creating download parts';
    if (step === 'downloading') return 'Downloading video and audio in parts';
    if (step === 'merging') return 'Combining downloaded video and audio';
    if (step === 'converting') return 'Converting to the requested format';
    if (step === 'finalizing') return 'Cleaning temporary files and saving output';
    return 'Preparing download';
  })();

  $: partsCount = fileList.length || 12;
  $: partsDone = fileList.filter(f => f.status === 'completed').length;
  $: partsText = (() => {
    if (current.status === 'completed') return 'All parts downloaded';
    if (step === 'downloading') return 'Downloading parts';
    if (stepIndexBefore('downloading')) return 'Parts will appear when download starts';
    return 'Download parts complete';
  })();

  function progressStepLabel(s: string | null) {
    const labels: Record<string, string> = {
      fetching_metadata: 'Fetching metadata',
      preparing: 'Preparing download',
      downloading: 'Downloading parts',
      merging: 'Merging parts',
      converting: 'Converting',
      finalizing: 'Finalizing',
    };
    return labels[s ?? ''] || 'Processing';
  }

  function stepIndexBefore(name: string): boolean {
    const order = ['fetching_metadata', 'preparing', 'downloading', 'merging', 'converting', 'finalizing'];
    const idx = order.indexOf(step ?? '');
    const target = order.indexOf(name);
    return idx < target;
  }

  $: partsBarSegments = Array.from({ length: partsCount }, (_, i) => {
    if (current.status === 'completed') return 100;
    if (i < partsDone) return 100;
    if (i === partsDone && step === 'downloading') {
      return clampPercent(((pct - 14) / (72 - 14)) * 100);
    }
    return 0;
  });

  $: downloadedTotal = (() => {
    if (current.downloadedBytes != null) return current.downloadedBytes;
    return 0;
  })();

  $: formattedElapsed = current.elapsed != null ? formatElapsed(current.elapsed) : '00:00';

  function formatElapsed(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  $: isComplete = current.status === 'completed';
  $: isCancelled = current.status === 'cancelled' || current.status === 'failed';

  $: hintText = (() => {
    if (isCancelled) return 'This task was cancelled.';
    if (isComplete) return 'Download complete. The file is ready.';
    if (paused) return 'Download is paused.';
    return 'You can close this dialog. The task will continue in the background.';
  })();

  $: pauseBtnText = (() => {
    if (isComplete) return 'Open file';
    if (isCancelled) return 'Retry';
    if (paused) return 'Resume';
    return 'Pause';
  })();

  async function doCancel() {
    try {
      await cancelTask(current.id);
      showToast('Task cancelled');
      current = { ...current, status: 'cancelled' };
      onChanged();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Unable to cancel');
    }
  }

  async function doRetry() {
    try {
      const next = await retryTask(current.id);
      showToast(`Retry queued: ${next.taskId}`);
      onChanged();
      onClose();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Unable to retry');
    }
  }

  function doPause() {
    if (isComplete) {
      showToast('Open file action would connect to the completed file.');
      return;
    }
    if (isCancelled) {
      doRetry();
      return;
    }
    paused = !paused;
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(current.url);
      showToast('Link copied');
    } catch {
      showToast('Unable to copy link');
    }
  }

  function getMetaFormat(): string {
    const fmt = current.formatInfo?.[0];
    if (fmt?.ext) return fmt.ext.toUpperCase();
    return 'MP4';
  }

  $: playlistCoverColors = [
    'linear-gradient(135deg, #53b7ff, #1d2a79 45%, #07152d)',
    'linear-gradient(135deg, #ff7a45, #5b2ee8)',
    'linear-gradient(135deg, #14d894, #225cff)',
    'linear-gradient(135deg, #ffc857, #ff4d7e)',
  ];
</script>

<div class="modal-backdrop" role="presentation" on:click={onClose} on:keydown={(e) => e.key === 'Escape' && onClose()}>
  <div class="modal-custom" class:cancelled={isCancelled} class:complete={isComplete} class:paused={paused} role="dialog" aria-modal="true" tabindex="0" on:click|stopPropagation>
  <header class="modal-header">
    <div class="title-wrap">
      <div class="title-icon" aria-hidden="true">
        <svg width="24" height="24" viewBox="0 0 24 24">
          <path d="M12 3v12m0 0 5-5m-5 5-5-5M4 20h16"
            fill="none" stroke="currentColor" stroke-width="2.2"
            stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div>
        <h1 class="modal-title">{isVideo ? 'Download task' : 'Playlist download'}</h1>
        <div class="status-chip">
          <span class="pulse"></span>
          <span class="status-text">{statusLabel}</span>
        </div>
      </div>
    </div>
    <button class="close-btn" type="button" aria-label="Close" on:click={onClose}>×</button>
  </header>

  <main class="content">
    {#if isVideo}
      <section class="media-row">
        <div class="thumb" aria-label="Video thumbnail">
          {#if thumbnailUrl}
            <img src={thumbnailUrl} alt="" class="thumb-img" />
          {/if}
          {#if current.duration}
            <span class="duration">{fmtDuration(current.duration)}</span>
          {/if}
        </div>
        <div class="media-content">
          <h2 class="video-title" title={current.title ?? ''}>{current.title || 'Untitled'}</h2>
          <div class="video-meta">
            <span>{current.channel || 'Unknown channel'}</span>
            <span>•</span>
            <span>{isVideo ? 'Video download' : 'Playlist download'}</span>
            <span>•</span>
            <span>{getMetaFormat()}</span>
          </div>
          <div class="activity-text">{activityText}</div>
          <div class="progress-top">
            <span class="progress-label">{progressLabel}</span>
            <span class="percent" class:completePercent={isComplete}>{pct}%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style={`width: ${pct}%`}></div>
          </div>
          <div class="parts-line">
            <span>{partsText}</span>
            <span>{Math.min(partsDone, partsCount)} / {partsCount}</span>
          </div>
          <div class="mini-parts">
            {#each partsBarSegments as seg}
              <div class="part">
                <div class="part-fill" style={`width: ${seg}%`}></div>
              </div>
            {/each}
          </div>
        </div>
      </section>
    {:else}
      <section class="playlist-row">
        <div class="playlist-cover">
          {#if thumbnailUrl}
            <img src={thumbnailUrl} alt="" class="cover-img" />
          {:else}
            <div class="cover-main" style={`background: ${playlistCoverColors[0]}`}></div>
            <div class="cover-stack">
              {#each playlistCoverColors.slice(1) as color}
                <div style={`background: ${color}`}></div>
              {/each}
            </div>
          {/if}
          <div class="playlist-count">
            <strong>{totalItems || fileList.length || '—'}</strong>
            <span>videos</span>
          </div>
        </div>
        <div class="playlist-main">
          <h2 class="playlist-title" title={current.title ?? ''}>{current.title || 'Untitled playlist'}</h2>
          <div class="playlist-subtitle">{current.channel || ''}</div>
          <div class="playlist-meta">
            <span>{totalItems || fileList.length || 0} videos</span>
            <span>•</span>
            <span>{current.duration ? fmtDuration(current.duration) : '—'}</span>
            <span>•</span>
            <span>{getMetaFormat()}</span>
          </div>
          <div class="overall-progress">
            <div class="progress-top">
              <span class="progress-label">{statusLabel === 'Starting' ? 'Preparing playlist' : progressLabel}</span>
              <span class="percent" class:completePercent={isComplete}>{pct}%</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style={`width: ${pct}%`}></div>
            </div>
            <div class="overall-line">
              <span>{Math.min(currentIndex, totalItems)} of {totalItems} videos completed</span>
              <span>•</span>
              <span>{bytes(downloadedTotal)} of {current.totalBytes ? bytes(current.totalBytes) : '—'}</span>
              <span>•</span>
              <span>ETA {current.eta || '—'}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="activity-card">
          <div class="spinner" class:stopped={isComplete || isCancelled}></div>
        <div class="activity-info">
          <div class="activity-eyebrow">{isCancelled ? 'Task cancelled' : isComplete ? 'Finished' : progressStepLabel(step)}</div>
          <div class="activity-title">{activityText}</div>
        </div>
        <div class="item-progress">
          <div class="item-progress-meta">{bytes(downloadedTotal)} / {current.totalBytes ? bytes(current.totalBytes) : '—'}</div>
          <div class="progress-track">
            <div class="progress-fill" style={`width: ${pct}%`}></div>
          </div>
        </div>
      </section>
    {/if}

    <section class="stats-grid">
      <div class="stat">
        <div class="stat-label">{isVideo ? 'Downloaded' : 'Current video'}</div>
        <div class="stat-value">{isVideo ? bytes(downloadedTotal) : `${Math.min(currentIndex + 1, totalItems)} / ${totalItems}`}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Speed</div>
        <div class="stat-value">{current.speed || (step === 'fetching_metadata' ? '…' : '—')}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Elapsed</div>
        <div class="stat-value">{formattedElapsed}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Remaining</div>
        <div class="stat-value">{current.status === 'completed' ? '0s' : current.eta || '—'}</div>
      </div>
    </section>

    {#if !isVideo && fileList.length > 0}
      <section class="strip-panel">
        <div class="strip-header">
          <h3>Playlist progress</h3>
          <span>{fileList.filter(f => f.status === 'completed').length} / {fileList.length} complete</span>
        </div>
        <div class="item-strip">
          {#each fileList as file, i}
            <div class="playlist-item" class:done={file.status === 'completed'} class:active={i === activeIdx && !isComplete}>
              <div class="item-thumb">
                {#if file.thumbnailUrl}
                  <img src={file.thumbnailUrl} alt="" class="item-thumb-img" />
                {/if}
                <span class="item-badge">{file.status === 'completed' ? '✓' : i + 1}</span>
                {#if file.duration}
                  <span class="item-duration">{fmtDuration(file.duration)}</span>
                {/if}
              </div>
              <div class="item-name">{i + 1}. {file.title || `Video ${i + 1}`}</div>
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <div class="source-box" title={current.url}>
      <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20.1l1.1-1.1"
          fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <span>{current.url}</span>
    </div>
  </main>

  <footer class="footer">
    <div class="hint">{hintText}</div>
    <div class="actions">
      <button class="ghost-btn" type="button" on:click={copyLink}>Copy link</button>
      <button class="danger-btn" type="button" disabled={isCancelled || isComplete} on:click={doCancel} style={isCancelled || isComplete ? 'display:none' : ''}>Cancel</button>
      <button class="primary-btn" type="button" on:click={doPause}>{pauseBtnText}</button>
    </div>
  </footer>
</div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: grid;
    place-items: center;
    padding: 24px;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(6px);
  }

  .modal-custom {
    width: min(820px, 100%);
    max-height: calc(100dvh - 48px);
    border-radius: 30px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.095), rgba(255, 255, 255, 0.032)),
      var(--modal, rgba(8, 13, 34, 0.88));
    border: 1px solid var(--border);
    box-shadow: 0 34px 100px rgba(0, 0, 0, 0.54);
    backdrop-filter: blur(26px);
  }

  .modal-header {
    flex-shrink: 0;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    padding: 26px 28px 18px;
  }

  .title-wrap {
    display: flex;
    gap: 14px;
    min-width: 0;
  }

  .title-wrap > div:last-child {
    min-width: 0;
  }

  .title-icon {
    width: 44px;
    height: 44px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    color: white;
    background: linear-gradient(180deg, #956aff, #5b2ee8);
    box-shadow:
      0 14px 28px rgba(103, 55, 255, 0.32),
      inset 0 1px 0 rgba(255, 255, 255, 0.36),
      inset 0 -7px 12px rgba(37, 9, 132, 0.44);
    flex: 0 0 auto;
  }

  .modal-title {
    margin: 0;
    font-size: 24px;
    letter-spacing: -0.04em;
    line-height: 1.05;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    color: var(--muted, #a9afd0);
    font-size: 14px;
    font-weight: 650;
    max-width: 100%;
  }

  .status-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pulse {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--green, #14d894);
    box-shadow: 0 0 16px rgba(20, 216, 148, 0.85);
    flex: 0 0 auto;
  }

  .cancelled .pulse {
    background: var(--red, #ff4d7e);
    box-shadow: 0 0 16px rgba(255, 77, 126, 0.75);
  }

  .complete .pulse {
    background: var(--green, #14d894);
  }

  .paused .pulse {
    background: #ffc857;
    box-shadow: 0 0 16px rgba(255, 200, 87, 0.65);
  }

  .close-btn {
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    border: 0;
    border-radius: 15px;
    color: var(--text);
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.09);
    cursor: pointer;
    font-size: 24px;
    line-height: 1;
    display: grid;
    place-items: center;
  }

  .content {
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 10px 28px 26px;
  }

  /* ── Video layout ───────────────────────────────── */

  .media-row {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 24px;
    align-items: center;
    min-width: 0;
  }

  .media-content {
    min-width: 0;
    overflow: hidden;
  }

  .thumb {
    position: relative;
    height: 126px;
    border-radius: 20px;
    overflow: hidden;
    background:
      linear-gradient(135deg, rgba(84, 54, 255, 0.2), rgba(255, 69, 153, 0.16));
    box-shadow: 0 18px 44px rgba(0, 0, 0, 0.32);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .duration {
    position: absolute;
    right: 10px;
    bottom: 10px;
    padding: 5px 8px;
    border-radius: 9px;
    color: white;
    background: rgba(0, 0, 0, 0.7);
    font-size: 13px;
    font-weight: 800;
  }

  .video-title {
    margin: 0;
    font-size: 25px;
    line-height: 1.18;
    letter-spacing: -0.04em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .video-meta {
    margin-top: 9px;
    color: var(--muted, #a9afd0);
    font-size: 15px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .activity-text {
    margin-top: 22px;
    color: var(--purple-light, #a786ff);
    font-size: 15px;
    font-weight: 750;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .progress-top {
    margin-top: 10px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 16px;
    min-width: 0;
  }

  .progress-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted, #a9afd0);
    font-size: 14px;
    font-weight: 650;
  }

  .percent {
    flex: 0 0 auto;
    color: var(--purple-light, #a786ff);
    font-size: 24px;
    font-weight: 900;
    letter-spacing: -0.04em;
  }

  .percent.completePercent {
    color: var(--green, #14d894);
  }

  .progress-track {
    width: 100%;
    min-width: 0;
    margin-top: 10px;
    height: 10px;
    overflow: hidden;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.075);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
  }

  .progress-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(180deg, #a783ff, #753cff);
    box-shadow: 0 0 22px rgba(124, 60, 255, 0.76);
    transition: width 450ms ease;
  }

  .complete .progress-fill {
    background: linear-gradient(180deg, #4af0b2, #14d894);
    box-shadow: 0 0 18px rgba(20, 216, 148, 0.55);
  }

  .complete .percent {
    color: var(--green, #14d894);
  }

  .cancelled .percent,
  .cancelled .activity-text,
  .cancelled .activity-title {
    color: var(--red, #ff4d7e);
  }

  .parts-line {
    margin-top: 12px;
    color: var(--muted, #a9afd0);
    font-size: 14px;
    display: flex;
    justify-content: space-between;
    gap: 14px;
    min-width: 0;
  }

  .parts-line span:first-child {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .parts-line span:last-child {
    flex: 0 0 auto;
  }

  .mini-parts {
    margin-top: 10px;
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 5px;
  }

  .part {
    height: 6px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
  }

  .part-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(180deg, #a783ff, #753cff);
    transition: width 300ms ease;
  }

  .complete .part-fill {
    background: linear-gradient(180deg, #4af0b2, #14d894);
    box-shadow: 0 0 18px rgba(20, 216, 148, 0.55);
  }

  /* ── Playlist layout ────────────────────────────── */

  .playlist-row {
    display: grid;
    grid-template-columns: 224px minmax(0, 1fr);
    gap: 26px;
    align-items: center;
    min-width: 0;
  }

  .playlist-cover {
    position: relative;
    height: 138px;
    border-radius: 20px;
    overflow: hidden;
    display: grid;
    grid-template-columns: 1.5fr 0.7fr;
    box-shadow: 0 18px 44px rgba(0, 0, 0, 0.32);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .cover-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    grid-column: 1 / -1;
  }

  .cover-main {
    position: relative;
  }

  .cover-stack {
    display: grid;
    grid-template-rows: repeat(3, 1fr);
  }

  .playlist-count {
    position: absolute;
    inset: auto auto 16px 16px;
    padding: 10px 12px;
    border-radius: 15px;
    background: rgba(0, 0, 0, 0.68);
    backdrop-filter: blur(12px);
    text-align: center;
    font-weight: 900;
    line-height: 1;
  }

  .playlist-count strong {
    display: block;
    font-size: 28px;
    letter-spacing: -0.04em;
  }

  .playlist-count span {
    display: block;
    margin-top: 4px;
    font-size: 12px;
    color: var(--muted, #a9afd0);
  }

  .playlist-main {
    min-width: 0;
    overflow: hidden;
  }

  .playlist-title {
    margin: 0;
    font-size: 26px;
    line-height: 1.18;
    letter-spacing: -0.04em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .playlist-subtitle {
    margin-top: 8px;
    color: var(--muted, #a9afd0);
    font-size: 16px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .playlist-meta {
    margin-top: 12px;
    color: var(--muted, #a9afd0);
    font-size: 15px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .overall-progress {
    margin-top: 24px;
    min-width: 0;
    overflow: hidden;
  }

  .overall-progress .progress-top {
    margin-bottom: 10px;
  }

  .overall-line {
    margin-top: 12px;
    color: var(--muted, #a9afd0);
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    font-size: 15px;
  }

  /* ── Activity card ──────────────────────────────── */

  .activity-card {
    margin-top: 24px;
    padding: 16px;
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) minmax(180px, 230px);
    gap: 16px;
    align-items: center;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.08);
    min-width: 0;
  }

  .activity-info {
    min-width: 0;
    overflow: hidden;
  }

  .item-progress {
    min-width: 0;
    overflow: hidden;
  }

  .spinner {
    width: 38px;
    height: 38px;
    border-radius: 999px;
    border: 4px solid rgba(255, 255, 255, 0.09);
    border-top-color: var(--purple-light, #a786ff);
    animation: spin 1s linear infinite;
  }

  .spinner.stopped {
    animation: none;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .activity-eyebrow {
    color: var(--muted, #a9afd0);
    font-size: 13px;
    font-weight: 750;
    margin-bottom: 4px;
  }

  .activity-title {
    font-size: 17px;
    font-weight: 850;
    letter-spacing: -0.02em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .item-progress-meta {
    color: var(--muted, #a9afd0);
    font-size: 13px;
    font-weight: 650;
    margin-bottom: 9px;
    text-align: right;
  }

  .activity-card .progress-track {
    height: 8px;
  }

  /* ── Stats grid ─────────────────────────────────── */

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-top: 22px;
  }

  .stat {
    padding: 14px 15px;
    border-radius: 17px;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.075);
  }

  .stat-label {
    color: var(--muted-2, #737b9f);
    font-size: 11px;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .stat-value {
    margin-top: 7px;
    color: var(--text);
    font-size: 16px;
    font-weight: 800;
    letter-spacing: -0.02em;
  }

  /* ── Playlist strip ─────────────────────────────── */

  .strip-panel {
    margin-top: 22px;
    padding: 18px 18px 20px;
    border-radius: 22px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .strip-header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    margin-bottom: 14px;
  }

  .strip-header h3 {
    margin: 0;
    font-size: 17px;
    letter-spacing: -0.03em;
  }

  .strip-header span {
    color: var(--muted, #a9afd0);
    font-size: 14px;
    font-weight: 700;
  }

  .item-strip {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 4px;
    scrollbar-width: thin;
  }

  .playlist-item {
    flex: 0 0 128px;
    min-width: 128px;
  }

  .item-thumb {
    height: 78px;
    border-radius: 14px;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.09);
    background: var(--item-thumb-bg, linear-gradient(135deg, #293b8f, #7c3cff));
  }

  .item-thumb-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .playlist-item:nth-child(2) .item-thumb { background: linear-gradient(135deg, #1d5f8f, #14d894); }
  .playlist-item:nth-child(3) .item-thumb { background: linear-gradient(135deg, #7434a4, #ff4d7e); }
  .playlist-item:nth-child(4) .item-thumb { background: linear-gradient(135deg, #0a3d62, #ffc857); }
  .playlist-item:nth-child(5) .item-thumb { background: linear-gradient(135deg, #1b7f79, #225cff); }
  .playlist-item:nth-child(6) .item-thumb { background: linear-gradient(135deg, #5d2aa4, #ff7a45); }

  .item-badge {
    position: absolute;
    left: 8px;
    top: 8px;
    width: 25px;
    height: 25px;
    display: grid;
    place-items: center;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 900;
    background: rgba(0, 0, 0, 0.58);
    color: white;
  }

  .playlist-item.done .item-badge {
    background: var(--green, #14d894);
    color: #02130d;
  }

  .playlist-item.active .item-thumb {
    outline: 2px solid var(--purple-light, #a786ff);
    box-shadow: 0 0 24px rgba(124, 60, 255, 0.26);
  }

  .item-duration {
    position: absolute;
    right: 7px;
    bottom: 7px;
    padding: 3px 6px;
    border-radius: 7px;
    background: rgba(0, 0, 0, 0.66);
    font-size: 11px;
    font-weight: 800;
  }

  .item-name {
    margin-top: 8px;
    color: var(--muted, #a9afd0);
    font-size: 13px;
    line-height: 1.28;
    height: 34px;
    overflow: hidden;
  }

  .playlist-item.active .item-name {
    color: white;
    font-weight: 750;
  }

  /* ── Source box ─────────────────────────────────── */

  .source-box {
    margin-top: 18px;
    padding: 13px 15px;
    border-radius: 17px;
    color: var(--muted, #a9afd0);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.07);
    display: flex;
    gap: 12px;
    align-items: center;
    min-width: 0;
    font-size: 14px;
  }

  .source-box span {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  /* ── Footer ─────────────────────────────────────── */

  .footer {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 22px 28px 28px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.018);
  }

  .hint {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted, #a9afd0);
    font-size: 14px;
  }

  .actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .ghost-btn,
  .primary-btn,
  .danger-btn {
    height: 48px;
    padding: 0 22px;
    border-radius: 15px;
    cursor: pointer;
    font-weight: 850;
    letter-spacing: -0.02em;
  }

  .ghost-btn {
    color: var(--text);
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .ghost-btn:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .danger-btn {
    color: #fff;
    background: rgba(255, 77, 126, 0.12);
    border: 1px solid rgba(255, 77, 126, 0.36);
  }

  .danger-btn:hover {
    background: rgba(255, 77, 126, 0.2);
  }

  .primary-btn {
    min-width: 150px;
    color: #fff;
    border: 0;
    background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%);
    box-shadow:
      0 16px 30px rgba(99, 49, 255, 0.36),
      inset 0 1px 0 rgba(255, 255, 255, 0.38),
      inset 0 -8px 14px rgba(39, 8, 143, 0.44);
  }

  .primary-btn:hover {
    transform: translateY(-2px);
    box-shadow:
      0 18px 36px rgba(99, 49, 255, 0.44),
      inset 0 1px 0 rgba(255, 255, 255, 0.42),
      inset 0 -8px 14px rgba(39, 8, 143, 0.44);
  }

  .primary-btn:disabled,
  .danger-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }

  /* ── Responsive ─────────────────────────────────── */

  @media (max-width: 760px) {
    .modal-backdrop {
      padding: 14px;
    }

    .modal-custom {
      max-height: calc(100dvh - 28px);
    }

    .modal-header,
    .content,
    .footer {
      padding-left: 18px;
      padding-right: 18px;
    }

    .modal-custom {
      border-radius: 24px;
    }

    .media-row {
      grid-template-columns: 1fr;
      gap: 18px;
    }

    .thumb {
      height: 190px;
    }

    .video-title {
      white-space: normal;
      font-size: 23px;
    }

    .playlist-row {
      grid-template-columns: 1fr;
    }

    .playlist-cover {
      height: 180px;
    }

    .playlist-title {
      white-space: normal;
      font-size: 23px;
    }

    .activity-card {
      grid-template-columns: 40px 1fr;
    }

    .activity-card .item-progress {
      grid-column: 1 / -1;
    }

    .item-progress-meta {
      text-align: left;
    }

    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .item-strip {
      overflow-x: auto;
      padding-bottom: 4px;
    }

    .playlist-item {
      flex-basis: 128px;
      min-width: 128px;
    }

    .footer {
      flex-direction: column;
      align-items: stretch;
    }

    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }

    .primary-btn {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 430px) {
    .stats-grid {
      grid-template-columns: 1fr;
    }

    .actions {
      grid-template-columns: 1fr;
    }

    .primary-btn {
      min-width: 0;
    }
  }
</style>
