<script lang="ts">
  import { listFiles, getFileStats, fileDownloadUrl } from '$lib/api/files';
  import { bytes, dateTime } from '$lib/utils/format';
  import EmptyState from '$lib/components/shared/EmptyState.svelte';
  import { tasks } from '$lib/state/event-stream';
  import type { FileInfo, FileStatsResponse, FileCategory } from '$lib/api/types';

  let busy = false;
  let error: string | null = null;

  let files: FileInfo[] = [];
  let total = 0;
  let stats: FileStatsResponse | null = null;

  let search = '';
  let fileType = 'all';
  let sortBy: string | undefined = undefined;
  let sortOrder = 'desc';
  let limit = 50;
  let offset = 0;
  let gridMode = false;

  let selected = new Set<string>();
  let activeFolder: string | null = null;

  let lastCompletedCount = 0;

  async function load() {
    busy = true; error = null;
    try {
      const typeParam = activeFolder && activeFolder !== 'all' ? activeFolder : (fileType !== 'all' ? fileType : undefined);
      const [fileResp, statsResp] = await Promise.all([
        listFiles({ limit, offset, search: search || undefined, fileType: typeParam, sortBy: sortBy as any, sortOrder: sortOrder as any }),
        getFileStats(),
      ]);
      files = fileResp.items;
      total = fileResp.total;
      stats = statsResp;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unable to load files';
      files = [];
      total = 0;
    } finally { busy = false; }
  }

  $: loadKey = `${limit}:${offset}:${search}:${fileType}:${sortBy}:${sortOrder}:${activeFolder}`;
  $: if (loadKey) load();

  $: {
    const cc = $tasks.filter(t => t.status === 'completed' && t.result && t.result.length > 0).length;
    if (cc !== lastCompletedCount) {
      lastCompletedCount = cc;
      load();
    }
  }

  const folderMeta: Record<string, { icon: string; label: string }> = {
    video: { icon: 'i-play', label: 'Videos' },
    playlist: { icon: 'i-list', label: 'Playlists' },
    audio: { icon: 'i-music', label: 'Audio' },
    image: { icon: 'i-folder', label: 'Images' },
    other: { icon: 'i-folder', label: 'Others' },
  };

  function folderCat(stats: FileStatsResponse | null) {
    if (!stats) return [];
    return stats.categories.filter(c => c.count > 0);
  }

  function folderCount(stats: FileStatsResponse | null, type: string): string {
    if (!stats) return '';
    const cat = stats.categories.find(c => c.type === type);
    if (!cat) return '';
    return `${cat.count} items\n${bytes(cat.size)}`;
  }

  function folderSize(stats: FileStatsResponse | null, type: string): string {
    if (!stats) return '';
    const cat = stats.categories.find(c => c.type === type);
    return cat ? bytes(cat.size) : '';
  }

  function selectFolder(type: string | null) {
    activeFolder = activeFolder === type ? null : type;
    offset = 0;
    selected.clear();
  }

  function typeIcon(f: FileInfo): string {
    if (f.fileType === 'audio') return '#i-music';
    if (f.fileType === 'playlist') return '#i-list';
    if (f.fileType === 'image') return '#i-folder';
    return '#i-video';
  }

  function toggleSelect(id: string) {
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
  }

  function selectAll() {
    if (selected.size === files.length) selected.clear();
    else files.forEach(f => f.id && selected.add(f.id));
  }

  function clearSelection() { selected.clear(); }

  function formatDetail(f: FileInfo): string {
    if (f.fileType === 'playlist') return 'Video';
    return f.detail || f.format;
  }

  let prevBtnEl: HTMLButtonElement;
  let nextBtnEl: HTMLButtonElement;

  function prevPage() { offset = Math.max(0, offset - limit); }
  function nextPage() { offset += limit; }

  const pageCount = () => Math.max(1, Math.ceil(total / limit));
  const currentPage = () => Math.min(pageCount(), Math.floor(offset / limit) + 1);
</script>

<div class="page">
  <header class="page-head">
    <div>
      <h1 class="page-title">Files</h1>
      <p class="page-subtitle">Organize and manage your downloaded content.</p>
    </div>

    <div class="toolbar">
      <label class="search-box">
        <svg width="20" height="20"><use href="#i-search"/></svg>
        <input type="search" placeholder="Search files..." bind:value={search} />
      </label>

      <label class="select-box">
        <svg width="20" height="20"><use href="#i-filter"/></svg>
        <select bind:value={fileType} on:change={() => { activeFolder = null; offset = 0; }}>
          <option value="all">All Files</option>
          <option value="video">Videos</option>
          <option value="playlist">Playlists</option>
          <option value="audio">Audio</option>
          <option value="image">Images</option>
          <option value="other">Others</option>
        </select>
      </label>

      <label class="select-box">
        <svg width="20" height="20"><use href="#i-sort"/></svg>
        <select bind:value={sortBy} on:change={() => { offset = 0; }}>
          <option value={undefined}>Newest</option>
          <option value="name">Name</option>
          <option value="size">Size</option>
        </select>
      </label>

      <div class="view-toggle" aria-label="View mode">
        <button class="view-btn" class:active={!gridMode} type="button" title="List view" on:click={() => gridMode = false}>
          <svg width="20" height="20"><use href="#i-list"/></svg>
        </button>
        <button class="view-btn" class:active={gridMode} type="button" title="Grid view" on:click={() => gridMode = true}>
          <svg width="20" height="20"><use href="#i-grid"/></svg>
        </button>
      </div>

      <button class="primary-btn" type="button" on:click={load} disabled={busy}>
        <svg width="20" height="20"><use href="#i-refresh"/></svg>
        Refresh
      </button>
    </div>
  </header>

  {#if stats}
    <section class="storage-panel">
      <div class="storage-left">
        <div class="donut" aria-hidden="true">
          <div class="donut-fill" style="--pct: {stats.totalUsed / stats.totalCapacity * 100}%"></div>
        </div>
        <div>
          <div class="storage-label">Storage Used</div>
          <div class="storage-value">{bytes(stats.totalUsed)} / {bytes(stats.totalCapacity)}</div>
          <div class="storage-sub">{Math.round(stats.totalUsed / stats.totalCapacity * 100)}% used</div>
        </div>
      </div>

      <div>
        <div class="storage-bar">
          <div class="storage-fill" style="width: {stats.totalUsed / stats.totalCapacity * 100}%"></div>
        </div>
        <div class="storage-legend">
          {#each stats.categories as cat}
            {#if cat.count > 0}
              <span class="legend-item">
                <span class="legend-dot {cat.type}"></span>
                {cat.label} {bytes(cat.size)}
              </span>
            {/if}
          {/each}
        </div>
      </div>

      <button class="secondary-btn" type="button">
        <svg width="20" height="20"><use href="#i-chart"/></svg>
        Manage Storage
      </button>
    </section>
  {/if}

  <div class="section-row">
    <h2 class="section-title">Folders</h2>
    {#if activeFolder}
      <button class="text-btn" type="button" on:click={() => { activeFolder = null; offset = 0; }}>Clear filter &rarr;</button>
    {/if}
  </div>

  <section class="folder-grid" aria-label="Folders">
    {#if stats}
      {#each stats.categories as cat}
        {#if cat.count > 0}
          {@const meta = folderMeta[cat.type] || { icon: 'i-folder', label: cat.label }}
          <button
            class="folder-card"
            class:active={activeFolder === cat.type}
            on:click={() => selectFolder(cat.type)}
          >
            <div class="folder-icon {cat.type}">
              <svg width="32" height="32"><use href="#{meta.icon}"/></svg>
            </div>
            <div class="folder-name">{meta.label}</div>
            <div class="folder-meta">{cat.count} items<br />{bytes(cat.size)}</div>
          </button>
        {/if}
      {/each}
    {/if}
  </section>

  <div class="section-row">
    <h2 class="section-title">{activeFolder ? (folderMeta[activeFolder]?.label || 'Files') : 'Recent Files'}</h2>
    {#if activeFolder || fileType !== 'all' || search}
      <button class="text-btn" type="button" on:click={() => { activeFolder = null; fileType = 'all'; search = ''; offset = 0; }}>Clear filter</button>
    {/if}
  </div>

  {#if error}
    <div class="error-box">{error}</div>
  {/if}

  <section class="files-panel" class:grid-mode={gridMode}>
    <div class="bulk-bar" style="display: {selected.size ? 'flex' : 'none'}">
      <span>{selected.size} selected</span>
      <div class="bulk-actions">
        <button class="small-btn" type="button" disabled>Download</button>
        <button class="small-btn" type="button" on:click={clearSelection}>Clear</button>
      </div>
    </div>

    {#if busy && files.length === 0}
      <div class="loading-state"><strong>Loading files…</strong></div>
    {:else if files.length === 0}
      <EmptyState title="No files found" detail="Try changing the search or filter." />
    {:else}
      <div class="table-wrap" style="display: {gridMode ? 'none' : 'block'}">
        <table class="table">
          <thead>
            <tr>
              <th style="width:44px">
                <input class="check" type="checkbox" aria-label="Select all"
                  checked={files.length > 0 && files.every(f => f.id && selected.has(f.id))}
                  on:change={selectAll} />
              </th>
              <th>Name</th>
              <th>Type</th>
              <th>Size</th>
              <th>Date Added</th>
              <th style="text-align:right; width:160px">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each files as f, i}
              <tr class="file-row">
                <td>
                  <input class="check file-check" type="checkbox"
                    checked={f.id ? selected.has(f.id) : false}
                    on:change={() => f.id && toggleSelect(f.id)} />
                </td>
                <td>
                  <div class="file-cell">
                    <div class="file-thumb" style="background: {['linear-gradient(135deg, #1f5f99, #5b2ee8)','linear-gradient(135deg, #10a5a7, #2374ff)','linear-gradient(135deg, #0a6a4c, #ffc857)','linear-gradient(135deg, #5f2e89, #ff7a45)','linear-gradient(135deg, #8640ff, #ff4d7e)'][i % 5]}">
                      {#if f.thumbnailUrl}
                        <img class="thumb-img" src={f.thumbnailUrl} alt="" loading="lazy" />
                      {/if}
                    </div>
                    <div>
                      <div class="file-title" title={f.name}>{f.name}</div>
                      <div class="file-path">{f.path}</div>
                    </div>
                  </div>
                </td>
                <td>
                  <span class="type-pill">
                    <span class="type-icon {f.fileType}">
                      <svg width="16" height="16"><use href={typeIcon(f)}/></svg>
                    </span>
                    <span>{f.format}<span class="type-sub">{formatDetail(f)}</span></span>
                  </span>
                </td>
                <td><span class="file-size">{bytes(f.size)}</span></td>
                <td><span class="file-date">{dateTime(f.createdAt)}</span></td>
                <td>
                  <div class="row-actions">
                    <a class="icon-btn" href={f.id ? fileDownloadUrl(f.id) : '#'} title="Download" download>
                      <svg width="20" height="20"><use href="#i-download"/></svg>
                    </a>
                    <button class="icon-btn" type="button" title="More">
                      <svg width="20" height="20"><use href="#i-more"/></svg>
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="grid-files" style="display: {gridMode ? 'grid' : 'none'}">
        {#each files as f, i}
          <article class="file-card">
            <div class="file-thumb" style="background: {['linear-gradient(135deg, #1f5f99, #5b2ee8)','linear-gradient(135deg, #10a5a7, #2374ff)','linear-gradient(135deg, #0a6a4c, #ffc857)','linear-gradient(135deg, #5f2e89, #ff7a45)','linear-gradient(135deg, #8640ff, #ff4d7e)'][i % 5]}">
              {#if f.thumbnailUrl}
                <img class="thumb-img" src={f.thumbnailUrl} alt="" loading="lazy" />
              {/if}
            </div>
            <div class="file-title" title={f.name}>{f.name}</div>
            <div class="file-path">{f.path}</div>
            <div class="folder-meta">{f.format} &bull; {bytes(f.size)}</div>
            <div class="file-card-actions">
              <a class="icon-btn" href={f.id ? fileDownloadUrl(f.id) : '#'} title="Download" download>
                <svg width="20" height="20"><use href="#i-download"/></svg>
              </a>
              <button class="icon-btn" type="button" title="More">
                <svg width="20" height="20"><use href="#i-more"/></svg>
              </button>
            </div>
          </article>
        {/each}
      </div>
    {/if}

    <footer class="panel-footer">
      <span>{total > 0 ? `Showing ${offset + 1} to ${Math.min(offset + limit, total)} of ${total} files` : 'No files'}</span>
      <div class="pagination">
        <button class="page-btn" type="button" disabled={offset === 0} on:click={prevPage}>&lsaquo;</button>
        <button class="page-btn active" type="button">{currentPage()}</button>
        {#if pageCount() > 1}
          <button class="page-btn" type="button" disabled={offset + limit >= total} on:click={nextPage}>&rsaquo;</button>
        {/if}
      </div>
    </footer>
  </section>
</div>

<style>
  .page {
    min-width: 0;
  }

  .page-head {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 24px;
    align-items: start;
    margin-bottom: 24px;
  }

  .page-title {
    margin: 0;
    font-size: clamp(32px, 4vw, 46px);
    line-height: 1;
    letter-spacing: -0.06em;
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
    justify-content: flex-end;
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
    width: min(320px, 34vw);
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
    min-width: 94px;
  }

  .view-toggle {
    height: 48px;
    padding: 5px;
    display: flex;
    gap: 4px;
    border-radius: 15px;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .view-btn {
    width: 38px;
    height: 36px;
    border: 0;
    border-radius: 11px;
    display: grid;
    place-items: center;
    color: var(--muted);
    background: transparent;
    cursor: pointer;
  }

  .view-btn.active {
    color: white;
    background: rgba(124, 60, 255, 0.28);
  }

  .primary-btn {
    height: 48px;
    border: 0;
    border-radius: 15px;
    padding: 0 20px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: white;
    cursor: pointer;
    font-weight: 850;
    letter-spacing: -0.02em;
    background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%);
    box-shadow:
      0 16px 30px rgba(99, 49, 255, 0.34),
      inset 0 1px 0 rgba(255, 255, 255, 0.38),
      inset 0 -8px 14px rgba(39, 8, 143, 0.44);
    transition: 180ms ease;
  }

  .primary-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .storage-panel {
    padding: 22px;
    border-radius: 22px;
    background:
      linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)),
      rgba(8, 13, 34, 0.64);
    border: 1px solid rgba(255, 255, 255, 0.105);
    margin-bottom: 24px;
    display: grid;
    grid-template-columns: 220px 1fr auto;
    gap: 26px;
    align-items: center;
  }

  .storage-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .donut {
    width: 72px;
    height: 72px;
    border-radius: 999px;
    background: rgba(255,255,255,.08);
    display: grid;
    place-items: center;
    position: relative;
    overflow: hidden;
  }

  .donut-fill {
    position: absolute;
    inset: 0;
    border-radius: 999px;
    background: conic-gradient(var(--purple) 0deg, var(--purple) calc(var(--pct) * 3.6deg), transparent calc(var(--pct) * 3.6deg));
    box-shadow: 0 0 26px rgba(124,60,255,.22);
  }

  .donut::after {
    content: "";
    position: relative;
    z-index: 1;
    width: 50px;
    height: 50px;
    border-radius: 999px;
    background: #0a0f26;
  }

  .storage-label {
    color: var(--muted);
    font-size: 14px;
    font-weight: 750;
  }

  .storage-value {
    margin-top: 6px;
    font-size: 18px;
    font-weight: 900;
  }

  .storage-sub {
    margin-top: 5px;
    color: var(--muted);
    font-size: 14px;
  }

  .storage-bar {
    height: 12px;
    border-radius: 999px;
    background: rgba(255,255,255,.08);
    overflow: hidden;
  }

  .storage-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(180deg, #a783ff, #753cff);
    box-shadow: 0 0 18px rgba(124,60,255,.65);
    transition: width 400ms ease;
    min-width: 0;
  }

  .storage-legend {
    margin-top: 18px;
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    color: var(--muted);
    font-size: 14px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
  }

  .legend-dot.video { background: var(--purple); }
  .legend-dot.playlist { background: var(--blue); }
  .legend-dot.audio { background: var(--green); }
  .legend-dot.image { background: var(--yellow); }
  .legend-dot.other { background: #7b86a9; }

  .secondary-btn {
    height: 46px;
    border-radius: 14px;
    padding: 0 18px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: white;
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(255,255,255,.1);
    cursor: pointer;
    font-weight: 800;
  }

  .section-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin: 24px 0 14px;
  }

  .section-title {
    margin: 0;
    font-size: 20px;
    letter-spacing: -0.035em;
  }

  .text-btn {
    border: 0;
    background: transparent;
    color: var(--purple-light);
    cursor: pointer;
    font-weight: 850;
  }

  .folder-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 14px;
  }

  .folder-card {
    min-height: 154px;
    border-radius: 18px;
    background:
      linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025)),
      rgba(8,13,34,.6);
    border: 1px solid rgba(255,255,255,.095);
    padding: 18px;
    position: relative;
    cursor: pointer;
    transition: 180ms ease;
    outline: none;
  }

  .folder-card:hover,
  .folder-card.active {
    border-color: rgba(167,134,255,.34);
    background: rgba(124,60,255,.08);
    transform: translateY(-1px);
  }

  .folder-icon {
    width: 70px;
    height: 58px;
    border-radius: 13px;
    display: grid;
    place-items: center;
    margin-bottom: 16px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.2);
  }

  .folder-icon.video { background: linear-gradient(135deg, #b353ff, #6c35ff); }
  .folder-icon.playlist { background: linear-gradient(135deg, #3aa0ff, #225cff); }
  .folder-icon.audio { background: linear-gradient(135deg, #49e3ad, #10ad72); }
  .folder-icon.image { background: linear-gradient(135deg, #ffd15a, #ff9d1e); }
  .folder-icon.other { background: linear-gradient(135deg, #8894b8, #5d6a8f); }

  .folder-name {
    font-size: 16px;
    font-weight: 900;
  }

  .folder-meta {
    margin-top: 6px;
    color: var(--muted);
    font-size: 14px;
    line-height: 1.45;
  }

  .files-panel {
    border-radius: 22px;
    overflow: hidden;
    background:
      linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)),
      rgba(8, 13, 34, 0.64);
    border: 1px solid rgba(255, 255, 255, 0.105);
    box-shadow: 0 22px 60px rgba(0,0,0,.22);
  }

  .bulk-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 18px;
    background: rgba(124,60,255,.12);
    border-bottom: 1px solid rgba(167,134,255,.16);
    color: white;
    font-size: 14px;
    font-weight: 800;
  }

  .bulk-actions {
    display: flex;
    gap: 10px;
  }

  .small-btn {
    height: 34px;
    padding: 0 12px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.1);
    background: rgba(255,255,255,.045);
    color: white;
    cursor: pointer;
    font-size: 13px;
    font-weight: 850;
  }

  .small-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .table {
    width: 100%;
    border-collapse: collapse;
  }

  .table th,
  .table td {
    padding: 13px 18px;
    border-bottom: 1px solid rgba(255,255,255,.07);
    text-align: left;
  }

  .table th {
    color: var(--muted);
    font-size: 13px;
    font-weight: 850;
    background: rgba(255,255,255,.025);
    white-space: nowrap;
  }

  .table td {
    vertical-align: middle;
  }

  .check {
    width: 18px;
    height: 18px;
    accent-color: var(--purple);
  }

  .file-cell {
    display: grid;
    grid-template-columns: 86px minmax(0, 1fr);
    gap: 14px;
    align-items: center;
    min-width: 0;
  }

  .file-thumb {
    width: 86px;
    height: 50px;
    border-radius: 10px;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.08);
  }

  .thumb-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .file-title {
    color: white;
    font-size: 15px;
    font-weight: 850;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .file-path {
    margin-top: 5px;
    color: var(--muted);
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .type-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    color: white;
    font-weight: 800;
  }

  .type-icon {
    width: 24px;
    height: 24px;
    border-radius: 7px;
    display: grid;
    place-items: center;
  }

  .type-icon.video { color: var(--purple-light); background: rgba(124,60,255,.16); }
  .type-icon.playlist { color: var(--blue); background: rgba(47,140,255,.14); }
  .type-icon.audio { color: var(--green); background: rgba(20,216,148,.14); }
  .type-icon.image { color: var(--yellow); background: rgba(255,200,87,.14); }
  .type-icon.other { color: #7b86a9; background: rgba(123,134,169,.14); }

  .type-sub {
    display: block;
    margin-top: 3px;
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
  }

  .file-size,
  .file-date {
    color: var(--text);
    font-size: 14px;
    white-space: nowrap;
  }

  .row-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
  }

  .icon-btn {
    width: 44px;
    height: 44px;
    border-radius: 13px;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(255,255,255,.045);
    color: var(--muted);
    cursor: pointer;
    display: grid;
    place-items: center;
    transition: 180ms ease;
    text-decoration: none;
  }

  .icon-btn:hover {
    color: white;
    background: rgba(124,60,255,.18);
    border-color: rgba(167,134,255,.25);
  }

  .icon-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .grid-files {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    padding: 16px;
  }

  .file-card {
    border-radius: 18px;
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.08);
    padding: 12px;
  }

  .file-card .file-thumb {
    width: 100%;
    height: 120px;
    margin-bottom: 12px;
  }

  .file-card-actions {
    margin-top: 12px;
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .panel-footer {
    padding: 14px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    color: var(--muted);
    font-size: 14px;
  }

  .pagination {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .page-btn {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,.08);
    background: rgba(255,255,255,.035);
    color: var(--muted);
    cursor: pointer;
  }

  .page-btn.active {
    color: white;
    background: var(--purple);
  }

  .page-btn:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .error-box {
    margin-bottom: 16px;
    padding: 12px 18px;
    border-radius: 14px;
    background: rgba(255,77,126,.12);
    border: 1px solid rgba(255,77,126,.2);
    color: var(--red);
    font-size: 14px;
    font-weight: 750;
  }

  .loading-state {
    padding: 48px 20px;
    text-align: center;
    color: var(--muted);
  }

  @media (max-width: 1180px) {
    .folder-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .storage-panel {
      grid-template-columns: 1fr;
    }

    .grid-files {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (max-width: 900px) {
    .page-head {
      grid-template-columns: 1fr;
    }

    .toolbar {
      justify-content: flex-start;
    }

    .search-box {
      width: 100%;
    }

    .folder-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .grid-files {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 680px) {
    .toolbar {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }

    .search-box,
    .primary-btn {
      grid-column: 1 / -1;
    }

    .folder-grid {
      grid-template-columns: 1fr;
    }

    .storage-legend {
      gap: 10px;
    }

    .file-cell {
      grid-template-columns: 70px minmax(0, 1fr);
    }

    .file-thumb {
      width: 70px;
      height: 44px;
    }

    .grid-files {
      grid-template-columns: 1fr;
    }

    .panel-footer {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
