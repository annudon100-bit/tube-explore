<script lang="ts">
  import { tasks } from '$lib/state/event-stream';
  import { cancelTask, pauseTask, resumeTask, retryTask } from '$lib/api/tasks';
  import { bytes, duration as fmtDuration, clampPercent } from '$lib/utils/format';
  import { showToast } from '$lib/state/toast-state';
  import type { TaskResponse } from '$lib/api/types';

  export let onOpen: (key: string) => void = () => {};
  export let onTask: (task: TaskResponse) => void = () => {};

  let activeFilter = 'all';
  let searchTerm = '';
  let typeFilter = 'all';
  let sortKey = 'newest';
  let expandedId: string | null = null;

  function toggleExpand(id: string) {
    expandedId = expandedId === id ? null : id;
  }

  function stepLabel(item: TaskResponse): string {
    if (item.status === 'completed') return 'Complete';
    if (item.status === 'paused') return 'Paused';
    if (item.status === 'cancelled' || item.status === 'failed') return 'Stopped';
    if (item.progressStep === 'fetching_metadata') return 'Fetching metadata';
    if (item.progressStep === 'preparing') return 'Preparing';
    if (item.progressStep === 'downloading') return 'Downloading parts';
    if (item.progressStep === 'merging') return 'Merging';
    if (item.progressStep === 'converting') return 'Converting';
    if (item.progressStep === 'finalizing') return 'Finalizing';
    return 'Downloading';
  }

  $: filtered = filterAndSort($tasks, activeFilter, searchTerm, typeFilter, sortKey);

  $: summary = computeSummary($tasks);

  $: tabCounts = {
    all: $tasks.length,
    downloading: $tasks.filter(t => t.status === 'running' || t.status === 'pending').length,
    completed: $tasks.filter(t => t.status === 'completed').length,
    paused: $tasks.filter(t => t.status === 'paused').length,
    cancelled: $tasks.filter(t => t.status === 'cancelled' || t.status === 'failed').length,
  };

  function computeSummary(t: TaskResponse[]) {
    const downloading = t.filter(d => d.status === 'running' || d.status === 'pending');
    const completed = t.filter(d => d.status === 'completed');
    const paused = t.filter(d => d.status === 'paused');
    const cancelled = t.filter(d => d.status === 'cancelled' || d.status === 'failed');
    const totalSpeed = downloading.reduce((s, d) => s + (parseFloat(d.speed ?? '0') || 0), 0);
    const completedSize = completed.reduce((s, d) => s + (d.totalBytes ?? 0), 0);
    return { downloading, completed, paused, cancelled, totalSpeed, completedSize };
  }

  function filterAndSort(t: TaskResponse[], filter: string, search: string, typeF: string, sort: string) {
    let visible = t.filter(item => {
      const matchesFilter = filter === 'all' || item.status === filter || (filter === 'downloading' && (item.status === 'running' || item.status === 'pending')) || (filter === 'cancelled' && (item.status === 'cancelled' || item.status === 'failed'));
      const matchesType = typeF === 'all' || item.type === typeF;
      const term = search.trim().toLowerCase();
      const matchesSearch = !term || (item.title ?? '').toLowerCase().includes(term) || (item.channel ?? '').toLowerCase().includes(term);
      return matchesFilter && matchesType && matchesSearch;
    });
    if (sort === 'progress') {
      visible = visible.sort((a, b) => (b.progressPercent ?? 0) - (a.progressPercent ?? 0));
    } else if (sort === 'name') {
      visible = visible.sort((a, b) => (a.title ?? '').localeCompare(b.title ?? ''));
    } else {
      visible = visible.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    }
    return visible;
  }

  function setFilter(filter: string) { activeFilter = filter; }

  function formatSize(bytesVal?: number | null) {
    if (!bytesVal && bytesVal !== 0) return '—';
    if (bytesVal < 1024 * 1024) return `${(bytesVal / 1024).toFixed(0)} KB`;
    if (bytesVal < 1024 * 1024 * 1024) return `${(bytesVal / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytesVal / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  function formatSpeed(speedStr?: string | null) {
    if (!speedStr) return '—';
    const val = parseFloat(speedStr);
    if (!val) return '—';
    if (val < 1024) return `${val.toFixed(1)} KB/s`;
    return `${(val / 1024).toFixed(1)} MB/s`;
  }

  function statusIcon(item: TaskResponse): string {
    if (item.status === 'completed') return '#i-play';
    if (item.status === 'cancelled' || item.status === 'failed') return '#i-play';
    if (item.status === 'paused') return '#i-play';
    return '#i-pause';
  }

  function statusAction(item: TaskResponse): string {
    if (item.status === 'completed') return 'open';
    if (item.status === 'cancelled' || item.status === 'failed') return 'retry';
    if (item.status === 'paused') return 'resume';
    return 'pause';
  }

  async function handleAction(item: TaskResponse, action: string) {
    try {
      if (action === 'cancel') {
        await cancelTask(item.id);
        showToast('Task cancelled');
      } else if (action === 'pause') {
        await pauseTask(item.id);
        showToast('Download paused');
      } else if (action === 'resume') {
        await resumeTask(item.id);
        showToast('Download resumed');
      } else if (action === 'retry') {
        const next = await retryTask(item.id);
        showToast(`Retry queued: ${next.taskId}`);
      } else if (action === 'open') {
        onTask(item);
      } else if (action === 'details') {
        onTask(item);
      }
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Action failed');
    }
  }



  const tabLabels: Record<string, string> = {
    all: 'All',
    downloading: 'Downloading',
    completed: 'Completed',
    paused: 'Paused',
    cancelled: 'Cancelled',
  };

  function etaDisplay(item: TaskResponse): string {
    if (item.status === 'completed') return '—';
    if (item.status === 'paused') return '—';
    if (item.status === 'cancelled' || item.status === 'failed') return '—';
    return item.eta || '—';
  }

  import { API_BASE_URL } from '$lib/config/env';

  const thumbColors = [
    'linear-gradient(135deg, #1f5f99, #5b2ee8)',
    'linear-gradient(135deg, #10a5a7, #2374ff)',
    'linear-gradient(135deg, #344f99, #e9549c)',
    'linear-gradient(135deg, #0a6a4c, #ffc857)',
    'linear-gradient(135deg, #5f2e89, #ff7a45)',
    'linear-gradient(135deg, #167b93, #14d894)',
    'linear-gradient(135deg, #8640ff, #ff4d7e)',
  ];

  const playlistCoverColors = [
    'linear-gradient(135deg, #53b7ff, #1d2a79 45%, #07152d)',
    'linear-gradient(135deg, #ff7a45, #5b2ee8)',
    'linear-gradient(135deg, #14d894, #225cff)',
    'linear-gradient(135deg, #ffc857, #ff4d7e)',
  ];

  function thumbUrl(item: TaskResponse): string | null {
    if (item.thumbnailPath) return `${API_BASE_URL}${item.thumbnailPath}`;
    return null;
  }

  function formatElapsed(sec?: number | null): string {
    if (!sec && sec !== 0) return '—';
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function percentClass(status: string): string {
    if (status === 'completed') return 'pct-completed';
    if (status === 'paused') return 'pct-paused';
    if (status === 'cancelled' || status === 'failed') return 'pct-cancelled';
    return '';
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <h1 class="page-title">Downloads</h1>
      <p class="page-subtitle">Monitor active downloads and manage your download tasks.</p>
    </div>
  </header>

  <div class="toolbar">
    <label class="search-box">
      <svg width="20" height="20"><use href="#i-search"/></svg>
      <input type="search" placeholder="Search downloads..." bind:value={searchTerm} />
    </label>
    <label class="select-box">
      <svg width="20" height="20"><use href="#i-sliders"/></svg>
      <select bind:value={typeFilter}>
        <option value="all">All Types</option>
        <option value="video">Videos</option>
        <option value="playlist">Playlists</option>
      </select>
    </label>
    <label class="select-box">
      <svg width="20" height="20">
        <path d="M7 4v16m0 0-3-3m3 3 3-3M17 20V4m0 0-3 3m3-3 3 3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <select bind:value={sortKey}>
        <option value="newest">Newest First</option>
        <option value="progress">Most Progress</option>
        <option value="name">Name</option>
      </select>
    </label>
    <button class="primary-btn" type="button" on:click={() => onOpen('videoDownload')}>
      <svg width="20" height="20">
        <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
      </svg>
      New Download
    </button>
  </div>

  <div class="summary-grid">
    <article class="summary-card">
      <div class="summary-icon downloading">
        <svg width="26" height="26"><use href="#i-download"/></svg>
      </div>
      <div>
        <div class="summary-number">{summary.downloading.length}</div>
        <div class="summary-label">Downloading</div>
        <div class="summary-sub">{summary.totalSpeed.toFixed(1)} MB/s</div>
      </div>
    </article>
    <article class="summary-card">
      <div class="summary-icon completed">
        <svg width="26" height="26">
          <path d="m5 13 4 4L19 7" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div>
        <div class="summary-number">{summary.completed.length}</div>
        <div class="summary-label">Completed</div>
        <div class="summary-sub">{formatSize(summary.completedSize)}</div>
      </div>
    </article>
    <article class="summary-card">
      <div class="summary-icon paused">
        <svg width="26" height="26">
          <path d="M8 5v14M16 5v14" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"/>
        </svg>
      </div>
      <div>
        <div class="summary-number">{summary.paused.length}</div>
        <div class="summary-label">Paused</div>
        <div class="summary-sub">Resume anytime</div>
      </div>
    </article>
    <article class="summary-card">
      <div class="summary-icon cancelled">
        <svg width="26" height="26">
          <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
      </div>
      <div>
        <div class="summary-number">{summary.cancelled.length}</div>
        <div class="summary-label">Cancelled</div>
        <div class="summary-sub">Can retry later</div>
      </div>
    </article>
  </div>

  <section class="panel">
    <div class="tabs-bar" role="tablist">
      {#each ['all', 'downloading', 'completed', 'paused', 'cancelled'] as filter}
        <button
          class="tab-btn"
          class:active={activeFilter === filter}
          type="button"
          on:click={() => setFilter(filter)}
        >
          {tabLabels[filter]}
          <span class="tab-count">{tabCounts[filter]}</span>
        </button>
      {/each}
    </div>

    <div class="section-head">
      <h2>{tabLabels[activeFilter]} ({filtered.length})</h2>
      <div class="section-meta">
        Total speed: <strong>{summary.totalSpeed.toFixed(1)} MB/s</strong>
      </div>
    </div>

    <div class="download-list">
      {#each filtered as item, i}
        <div class="download-block" class:expanded={expandedId === item.id}>
          <article class="download-row" data-id={item.id}>
            <div class="thumb" class:playlist={item.type === 'playlist'} style="background: {thumbColors[i % thumbColors.length]}">
              {#if item.type === 'playlist'}
                <div class="thumb-main" style="background: {thumbUrl(item) ? `url(${thumbUrl(item)})` : playlistCoverColors[0]}; {thumbUrl(item) ? 'background-size: cover; background-position: center;' : ''}"></div>
                <div class="thumb-stack">
                  {#each playlistCoverColors.slice(1) as color}
                    <div style="background: {color}"></div>
                  {/each}
                </div>
                <span class="badge badge-playlist">
                  <strong>{item.totalItems || '—'}</strong>
                  <span>videos</span>
                </span>
              {:else}
                {#if thumbUrl(item)}
                  <img src={thumbUrl(item)} alt="" class="thumb-img" />
                {/if}
                {#if item.duration}
                  <span class="badge badge-duration">{fmtDuration(item.duration)}</span>
                {/if}
              {/if}
            </div>

            <div class="download-info">
              <h3 class="download-title" title={item.title ?? ''}>{item.title || 'Untitled'}</h3>
              <div class="download-meta">
                {#if item.type === 'playlist'}
                  <span class="tag">Playlist</span>
                  {#if item.totalItems}
                    <span>•</span>
                    <span>{item.totalItems} videos</span>
                  {/if}
                  {#if item.status === 'running' || item.status === 'pending'}
                    {#if item.currentIndex !== null && item.currentIndex !== undefined}
                      <span>•</span>
                      <span>Downloading {item.currentIndex + 1} of {item.totalItems ?? '—'}</span>
                    {/if}
                  {/if}
                {:else}
                  <span>Video</span>
                {/if}
                {#if item.channel}
                  <span>•</span>
                  <span>{item.channel}</span>
                {/if}
              </div>
              <div class="progress-line">
                <div class="progress-track">
                  <div
                    class="progress-fill {percentClass(item.status)}"
                    style="width: {clampPercent(item.progressPercent)}%"
                  ></div>
                </div>
                <div class="progress-percent {percentClass(item.status)}">{Math.round(clampPercent(item.progressPercent))}%</div>
              </div>
            </div>

            <div class="download-stats">
              {#if item.status === 'completed'}
                <strong>{formatSize(item.totalBytes ?? 0)}</strong><br />
                {item.completedAt ? new Date(item.completedAt).toLocaleString() : 'Completed'}
              {:else if item.status === 'cancelled'}
                <strong>{formatSize(item.downloadedBytes ?? 0)} / {formatSize(item.totalBytes ?? 0)}</strong><br />
                Cancelled{ item.error ? ` • ${item.error}` : '' }
              {:else if item.status === 'failed'}
                <strong>{formatSize(item.downloadedBytes ?? 0)} / {formatSize(item.totalBytes ?? 0)}</strong><br />
                Failed{ item.error ? ` • ${item.error}` : '' }
              {:else if item.status === 'paused'}
                <strong>{formatSize(item.downloadedBytes ?? 0)} / {formatSize(item.totalBytes ?? 0)}</strong><br />
                Paused
              {:else}
                <strong>{formatSize(item.downloadedBytes ?? 0)} / {formatSize(item.totalBytes ?? 0)}</strong><br />
                {formatSpeed(item.speed)} • ETA {etaDisplay(item)}
              {/if}
            </div>

            <div class="row-actions">
              {#if item.status === 'running' || item.status === 'pending'}
                <button class="icon-btn" type="button" title="Pause" on:click={() => handleAction(item, 'pause')}>
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path d="M8 5v14M16 5v14" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"/>
                  </svg>
                </button>
                <button class="icon-btn" type="button" title="Cancel" on:click={() => handleAction(item, 'cancel')}>
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/>
                  </svg>
                </button>
              {:else if item.status === 'paused'}
                <button class="icon-btn" type="button" title="Resume" on:click={() => handleAction(item, 'resume')}>
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
                  </svg>
                </button>
                <button class="icon-btn" type="button" title="Cancel" on:click={() => handleAction(item, 'cancel')}>
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/>
                  </svg>
                </button>
              {:else if item.status === 'completed'}
                <button class="icon-btn" type="button" title="Open file" on:click={() => handleAction(item, 'open')}>
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
                  </svg>
                </button>
              {:else}
                <button class="icon-btn" type="button" title="Retry" on:click={() => handleAction(item, 'retry')}>
                  <svg width="20" height="20" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
                  </svg>
                </button>
              {/if}
              {#if item.type === 'playlist'}
                <button class="icon-btn" type="button"
                  title={expandedId === item.id ? 'Collapse playlist' : 'Expand playlist'}
                  on:click={() => toggleExpand(item.id)}>
                  <svg width="20" height="20">
                    <use href={expandedId === item.id ? '#i-chevron-up' : '#i-chevron-down'}/>
                  </svg>
                </button>
              {/if}
              <button class="icon-btn" type="button" title="Details" on:click={() => handleAction(item, 'details')}>
                <svg width="20" height="20" viewBox="0 0 24 24">
                  <path d="M12 5.5h.01M12 12h.01M12 18.5h.01" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </article>

          {#if item.type === 'playlist' && expandedId === item.id}
            {@const currentFile = item.fileProgress?.find(f => f.status === 'downloading')
              ?? item.fileProgress?.find(f => f.status === 'running')
              ?? item.fileProgress?.find(f => f.status === 'pending')
              ?? null}
            {@const sortedFiles = [...(item.fileProgress ?? [])].sort((a, b) => a.index - b.index)}
            {@const doneCount = sortedFiles.filter(f => f.status === 'completed').length}
            {@const total = item.totalItems ?? sortedFiles.length ?? 0}
            {@const current = currentFile ? currentFile.index + 1 : (item.status === 'completed' ? total + 1 : doneCount + 1)}
            {@const queuedCount = Math.max(0, total - current)}
            {@const failedCount = item.fileProgress?.filter(f => f.status === 'failed' || f.status === 'error').length ?? 0}
            {@const maxMini = Math.min(total, 11)}
            {@const visibleIndices = total > 11
              ? [...Array(9).keys()].map(i => i + 1).concat(['…' as const, total] as const)
              : [...Array(maxMini).keys()].map(i => i + 1)}
            <section class="expand-panel">
              <div class="expand-section">
                <h4 class="expand-title">Currently downloading</h4>
                <div class="current-item">
                  <div class="mini-thumb"></div>
                  <div>
                    <div class="current-name">{currentFile?.title ?? item.title ?? 'Untitled'}</div>
                    <div class="current-step">{stepLabel(item)}</div>
                    <div class="current-sub">
                      {#if currentFile}
                        {formatSize(currentFile.downloadedBytes)} / {formatSize(currentFile.totalBytes)} • {formatSpeed(currentFile.speed)}
                      {:else if item.status === 'completed'}
                        All playlist videos completed
                      {:else}
                        Waiting for next item
                      {/if}
                    </div>
                  </div>
                </div>
              </div>

              <div class="expand-section">
                <h4 class="expand-title">Playlist progress</h4>
                <div class="playlist-strip">
                  {#each visibleIndices as entry}
                    {#if entry === '…'}
                      <div class="mini-index">…</div>
                    {:else}
                      {@const idx = entry as number}
                      <div class="mini-index"
                        class:done={idx < current || item.status === 'completed'}
                        class:active={idx === current && item.status !== 'completed'}>
                        {idx < current || item.status === 'completed' ? '✓' : idx}
                      </div>
                    {/if}
                  {/each}
                </div>
              </div>

              <div class="expand-section">
                <h4 class="expand-title">Summary</h4>
                <div class="playlist-summary">
                  <div>Completed: <strong class="good">{doneCount}</strong></div>
                  <div>Current: <strong class="purple">{item.status === 'completed' ? '—' : current}</strong></div>
                  <div>Queued: <strong>{queuedCount}</strong></div>
                  <div>Failed: <strong class="bad">{failedCount}</strong></div>
                </div>
                <button class="retry-small" type="button" disabled={failedCount === 0}
                  on:click={() => handleAction(item, 'retry')}>Retry failed items</button>
              </div>
            </section>
          {/if}
        </div>
      {/each}
    </div>

    {#if filtered.length === 0}
      <div class="empty-state">
        <strong>No downloads found</strong>
        <p>Try changing the filter or search term.</p>
      </div>
    {/if}
  </section>
</div>

<style>
  .page {
    min-width: 0;
  }

  .page-head {
    margin-bottom: 24px;
  }

  .page-title {
    margin: 0;
    font-size: clamp(30px, 3.6vw, 42px);
    line-height: 1;
    letter-spacing: -0.055em;
    font-weight: 950;
  }

  .page-subtitle {
    margin: 10px 0 0;
    color: var(--muted);
    font-size: 15px;
  }

  .toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 20px;
  }

  .search-box,
  .select-box {
    height: 48px;
    border-radius: 15px;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: white;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px;
  }

  .search-box {
    width: min(320px, 30vw);
    flex: 1 1 auto;
  }

  .search-box svg,
  .select-box svg {
    color: var(--muted);
    flex: 0 0 auto;
  }

  .search-box input {
    width: 100%;
    min-width: 0;
    border: 0;
    outline: 0;
    color: white;
    background: transparent;
    font-size: 14px;
  }

  .search-box input::placeholder {
    color: rgba(210, 212, 238, 0.55);
  }

  .select-box select {
    border: 0;
    outline: 0;
    color: white;
    background: transparent;
    appearance: none;
    cursor: pointer;
    font-size: 14px;
    min-width: 100px;
  }

  .primary-btn {
    height: 48px;
    border: 0;
    border-radius: 15px;
    padding: 0 22px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: white;
    cursor: pointer;
    font-weight: 850;
    letter-spacing: -0.02em;
    font-size: 15px;
    background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%);
    box-shadow:
      0 16px 30px rgba(99, 49, 255, 0.34),
      inset 0 1px 0 rgba(255, 255, 255, 0.38),
      inset 0 -8px 14px rgba(39, 8, 143, 0.44);
    transition: 180ms ease;
    white-space: nowrap;
    width: auto;
    flex: 0 0 auto;
  }

  .primary-btn:hover {
    transform: translateY(-1px);
    box-shadow:
      0 20px 38px rgba(99, 49, 255, 0.44),
      inset 0 1px 0 rgba(255, 255, 255, 0.42),
      inset 0 -8px 14px rgba(39, 8, 143, 0.44);
  }

  .primary-btn svg {
    flex: 0 0 auto;
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin-bottom: 18px;
  }

  .summary-card {
    min-height: 100px;
    padding: 18px;
    border-radius: 18px;
    background:
      linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)),
      rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.095);
    display: flex;
    align-items: center;
    gap: 15px;
  }

  .summary-icon {
    width: 50px;
    height: 50px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    flex: 0 0 auto;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.28);
  }

  .summary-icon.downloading {
    background: rgba(124, 60, 255, 0.2);
    color: var(--purple-light);
  }

  .summary-icon.completed {
    background: rgba(20, 216, 148, 0.14);
    color: var(--green);
  }

  .summary-icon.paused {
    background: rgba(255, 200, 87, 0.14);
    color: #ffc857;
  }

  .summary-icon.cancelled {
    background: rgba(255, 77, 126, 0.14);
    color: var(--red);
  }

  .summary-number {
    font-size: 26px;
    line-height: 1;
    font-weight: 950;
    letter-spacing: -0.05em;
  }

  .summary-label {
    margin-top: 4px;
    color: var(--muted);
    font-size: 14px;
    font-weight: 700;
  }

  .summary-sub {
    margin-top: 4px;
    color: #737b9f;
    font-size: 13px;
  }

  .panel {
    border-radius: 22px;
    overflow: hidden;
    background:
      linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)),
      rgba(8, 13, 34, 0.64);
    border: 1px solid rgba(255, 255, 255, 0.105);
    box-shadow: 0 22px 60px rgba(0,0,0,.22);
  }

  .tabs-bar {
    height: 56px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 14px;
    border-bottom: 1px solid rgba(255,255,255,.08);
    overflow-x: auto;
    scrollbar-width: none;
  }

  .tabs-bar::-webkit-scrollbar {
    display: none;
  }

  .tab-btn {
    height: 44px;
    border: 0;
    border-radius: 12px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    padding: 0 14px;
    white-space: nowrap;
    font-weight: 800;
    font-size: 14px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: 180ms ease;
    flex: 0 0 auto;
  }

  .tab-btn.active {
    color: white;
    background: rgba(124, 60, 255, 0.18);
  }

  .tab-count {
    font-size: 12px;
    font-weight: 750;
    opacity: 0.7;
  }

  .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 18px 8px;
  }

  .section-head h2 {
    margin: 0;
    font-size: 18px;
    letter-spacing: -0.03em;
  }

  .section-meta {
    color: var(--muted);
    font-size: 14px;
  }

  .section-meta strong {
    color: var(--purple-light);
  }

  .download-list {
    padding: 6px 10px 14px;
    display: grid;
    gap: 2px;
  }

  .download-row {
    display: grid;
    grid-template-columns: 140px minmax(0, 1fr) minmax(160px, 210px) auto;
    gap: 16px;
    align-items: center;
    padding: 12px;
  }

  .thumb {
    position: relative;
    height: 82px;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.08);
    box-shadow: 0 14px 30px rgba(0,0,0,.24);
  }

  .thumb.playlist {
    display: grid;
    grid-template-columns: 1.35fr 0.65fr;
  }

  .thumb-main {
    background: linear-gradient(135deg, #53b7ff, #1d2a79 45%, #07152d);
  }

  .thumb-stack {
    display: grid;
    grid-template-rows: repeat(3, 1fr);
  }

  .thumb-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .badge {
    position: absolute;
    right: 6px;
    bottom: 6px;
    padding: 3px 6px;
    border-radius: 7px;
    background: rgba(0,0,0,.7);
    color: white;
    font-size: 11px;
    font-weight: 850;
    line-height: 1;
  }

  .badge-playlist {
    left: 6px;
    right: auto;
    text-align: center;
    line-height: 1.15;
  }

  .badge-playlist strong {
    display: block;
    font-size: 15px;
  }

  .badge-playlist span {
    display: block;
    font-size: 9px;
    opacity: 0.8;
  }

  .download-info {
    min-width: 0;
    overflow: hidden;
  }

  .download-title {
    margin: 0;
    font-size: 16px;
    font-weight: 900;
    letter-spacing: -0.025em;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .download-meta {
    margin-top: 6px;
    color: var(--muted);
    font-size: 13px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    min-width: 0;
  }

  .download-meta > span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tag {
    color: var(--purple-light);
    background: rgba(124, 60, 255, 0.18);
    border: 1px solid rgba(167, 134, 255, 0.24);
    padding: 1px 7px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 850;
  }

  .progress-line {
    margin-top: 10px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 44px;
    gap: 10px;
    align-items: center;
  }

  .progress-track {
    height: 7px;
    overflow: hidden;
    border-radius: 999px;
    background: rgba(255,255,255,.075);
  }

  .progress-fill {
    width: 0%;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(180deg, #a783ff, #753cff);
    box-shadow: 0 0 18px rgba(124, 60, 255, 0.7);
    transition: width 500ms ease;
  }

  .progress-fill.pct-completed {
    background: linear-gradient(180deg, #4af0b2, #14d894);
    box-shadow: 0 0 18px rgba(20, 216, 148, 0.55);
  }

  .progress-fill.pct-paused {
    background: linear-gradient(180deg, #ffd46c, #ffc857);
    box-shadow: 0 0 18px rgba(255, 200, 87, 0.45);
  }

  .progress-fill.pct-cancelled {
    background: linear-gradient(180deg, #ff739a, #ff4d7e);
    box-shadow: 0 0 18px rgba(255, 77, 126, 0.45);
  }

  .progress-percent {
    color: var(--purple-light);
    font-size: 14px;
    font-weight: 950;
    text-align: right;
  }

  .progress-percent.pct-completed { color: var(--green); }
  .progress-percent.pct-paused { color: #ffc857; }
  .progress-percent.pct-cancelled { color: var(--red); }

  .download-stats {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.6;
    min-width: 0;
  }

  .download-stats strong {
    color: white;
    font-weight: 750;
  }

  .row-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .icon-btn {
    width: 42px;
    height: 42px;
    border-radius: 13px;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(255,255,255,.045);
    color: var(--muted);
    cursor: pointer;
    display: grid;
    place-items: center;
    transition: 180ms ease;
    flex: 0 0 auto;
  }

  .icon-btn:hover {
    color: white;
    background: rgba(124,60,255,.18);
    border-color: rgba(167,134,255,.25);
  }

  .empty-state {
    padding: 48px 20px;
    text-align: center;
    color: var(--muted);
  }

  .empty-state strong {
    display: block;
    color: white;
    font-size: 18px;
    margin-bottom: 6px;
  }

  .empty-state p {
    margin: 0;
    font-size: 14px;
  }

  .download-block {
    border-radius: 18px;
    border: 1px solid transparent;
    transition: 180ms ease;
  }

  .download-block:hover {
    background: rgba(255,255,255,.026);
    border-color: rgba(255,255,255,.065);
  }

  .download-block.expanded {
    background: rgba(255,255,255,.035);
    border-color: rgba(255,255,255,.085);
  }

  .expand-panel {
    margin: 0 12px 14px;
    padding: 18px;
    border-radius: 18px;
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.075);
    display: grid;
    grid-template-columns: 1fr 1.45fr 0.75fr;
    gap: 20px;
  }

  .expand-section {
    min-width: 0;
    border-right: 1px solid rgba(255,255,255,.08);
    padding-right: 20px;
  }

  .expand-section:last-child {
    border-right: 0;
    padding-right: 0;
  }

  .expand-title {
    margin: 0 0 12px;
    font-size: 15px;
    font-weight: 900;
    letter-spacing: -0.02em;
  }

  .current-item {
    display: grid;
    grid-template-columns: 84px 1fr;
    gap: 12px;
    align-items: center;
  }

  .mini-thumb {
    height: 70px;
    border-radius: 12px;
    background: linear-gradient(135deg, #4db8ff, #7c3cff);
    border: 1px solid rgba(255,255,255,.1);
  }

  .current-name {
    font-size: 14px;
    font-weight: 850;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .current-step {
    margin-top: 5px;
    color: var(--muted);
    font-size: 13px;
  }

  .current-sub {
    margin-top: 8px;
    color: var(--muted);
    font-size: 13px;
  }

  .playlist-summary {
    display: grid;
    gap: 8px;
    color: var(--muted);
    font-size: 14px;
  }

  .playlist-summary strong {
    color: white;
    font-weight: 900;
  }

  .playlist-summary .good { color: var(--green); }
  .playlist-summary .purple { color: var(--purple-light); }
  .playlist-summary .bad { color: var(--red); }

  .playlist-strip {
    display: flex;
    gap: 8px;
    align-items: center;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: thin;
  }

  .mini-index {
    flex: 0 0 34px;
    height: 34px;
    border-radius: 9px;
    display: grid;
    place-items: center;
    border: 1px solid rgba(255,255,255,.1);
    background: rgba(255,255,255,.04);
    color: var(--muted);
    font-size: 13px;
    font-weight: 900;
    position: relative;
  }

  .mini-index.done {
    background: rgba(20,216,148,.18);
    color: var(--green);
    border-color: rgba(20,216,148,.25);
  }

  .mini-index.active {
    background: rgba(124,60,255,.28);
    color: white;
    border-color: rgba(167,134,255,.45);
    box-shadow: 0 0 18px rgba(124,60,255,.24);
  }

  .mini-index.active::after {
    content: "";
    position: absolute;
    bottom: -8px;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 0;
    border-top: 6px solid var(--purple-light);
  }

  .retry-small {
    margin-top: 12px;
    height: 34px;
    padding: 0 12px;
    border-radius: 10px;
    border: 1px solid rgba(167, 134, 255, 0.28);
    background: rgba(124, 60, 255, 0.12);
    color: var(--purple-light);
    cursor: pointer;
    font-size: 13px;
    font-weight: 850;
  }

  .retry-small:disabled {
    opacity: 0.4;
    cursor: default;
  }

  @media (max-width: 1180px) {
    .summary-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .download-row {
      grid-template-columns: 120px minmax(0, 1fr) auto;
    }

    .download-stats {
      grid-column: 2 / 3;
    }

    .row-actions {
      grid-row: 1 / span 2;
      grid-column: 3 / 4;
    }

    .expand-panel {
      grid-template-columns: 1fr;
    }

    .expand-section {
      border-right: 0;
      padding-right: 0;
    }

    .search-box {
      width: min(260px, 28vw);
    }
  }

  @media (max-width: 900px) {
    .page {
      padding-bottom: 24px;
    }

    .toolbar {
      gap: 10px;
    }

    .search-box {
      width: 100%;
      flex: 1 1 100%;
    }

    .select-box {
      flex: 1 0 auto;
    }

    .primary-btn {
      flex: 1 0 auto;
    }

    .summary-grid {
      gap: 10px;
    }

    .summary-card {
      min-height: 88px;
      padding: 14px;
    }

    .summary-icon {
      width: 44px;
      height: 44px;
    }

    .summary-number {
      font-size: 22px;
    }
  }

  @media (max-width: 680px) {
    .page-head {
      margin-bottom: 18px;
    }

    .page-title {
      font-size: 32px;
    }

    .toolbar {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }

    .search-box {
      grid-column: 1 / -1;
      width: 100%;
    }

    .primary-btn {
      grid-column: 1 / -1;
      justify-content: center;
    }

    .summary-grid {
      grid-template-columns: 1fr;
    }

    .download-row {
      grid-template-columns: 100px minmax(0, 1fr);
      gap: 10px;
    }

    .thumb {
      height: 70px;
    }

    .download-stats {
      grid-column: 1 / -1;
    }

    .row-actions {
      grid-column: 1 / -1;
      grid-row: auto;
      justify-content: flex-end;
    }

    .tabs-bar {
      gap: 4px;
      padding: 0 10px;
    }

    .tab-btn {
      font-size: 13px;
      padding: 0 10px;
      height: 40px;
    }

    .section-head {
      flex-direction: column;
      align-items: flex-start;
      gap: 6px;
    }
  }
</style>
