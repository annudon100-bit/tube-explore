<script lang="ts">
  import { onMount } from 'svelte';
  import { listArrInstances, listSonarrSeries, listSonarrEpisodes, inspectSonarrPlaylist, createSonarrPlaylistMapping, updateSonarrPlaylistMapping, downloadSonarrPlaylistMapping } from '$lib/api/arr';
  import type { PlaylistMappingResponse, PlaylistEntryInfo } from '$lib/api/arr';
  import { showToast } from '$lib/state/toast-state';
  import type { ArrInstanceResponse } from '$lib/api/types';

  export let navigate: (page: string, data?: any) => void = () => {};
  export let mappingData: PlaylistMappingResponse | null = null;

  let instances: ArrInstanceResponse[] = [];
  let selectedInstanceId = '';
  let selectedInstance: ArrInstanceResponse | null = null;
  let seriesList: Array<{ id: number; title: string; seasonCount: number }> = [];
  let selectedSeriesId: number | null = null;
  let selectedSeason: number | null = null;

  let playlistUrl = '';
  let entries: PlaylistEntryInfo[] = [];
  let seriesTitle = '';
  let inspecting = false;

  let episodes: Array<{ id: number; seriesId?: number; episodeNumber?: number; seasonNumber?: number; title: string; hasFile: boolean }> = [];
  let loadingEpisodes = false;

  interface MappingEntry {
    index: number;
    sourceTitle: string;
    sourceUrl: string;
    duration?: number | null;
    selectedEpisodeId: number | null;
    selectedEpisodeLabel: string;
    confidence: 'high' | 'medium' | 'low' | 'none' | 'manual';
    action: 'download' | 'skip';
    warning: string | null;
  }

  let mappings: MappingEntry[] = [];
  let autoMapping = false;
  let downloading = false;
  let editing = false;
  let editingMappingId: string | null = null;
  let saving = false;

  async function load() {
    try {
      instances = await listArrInstances('sonarr');
      if (mappingData) {
        editing = true;
        editingMappingId = mappingData.id;
        const inst = instances.find(i => i.id === mappingData.arrInstanceId);
        if (inst) {
          selectedInstanceId = inst.id;
          await onInstanceChange();
          selectedSeriesId = mappingData.seriesId;
          await onSeriesChange();
          selectedSeason = mappingData.seasonNumber ?? null;
          playlistUrl = mappingData.playlistUrl;
          seriesTitle = mappingData.seriesTitle;
          entries = mappingData.items.map(item => ({
            index: item.playlistIndex,
            title: item.videoTitle,
            url: item.videoUrl,
            duration: item.videoDuration ?? null,
            thumbnail: null,
          }));
          mappings = mappingData.items.map(item => ({
            index: item.playlistIndex,
            sourceTitle: item.videoTitle,
            sourceUrl: item.videoUrl,
            duration: item.videoDuration ?? null,
            selectedEpisodeId: item.episodeId ?? null,
            selectedEpisodeLabel: item.episodeTitle ? `S${String(item.seasonNumber ?? 0).padStart(2, '0')}E${String(item.episodeNumber ?? 0).padStart(2, '0')} - ${item.episodeTitle}` : '',
            confidence: (item.confidence || 'none') as MappingEntry['confidence'],
            action: (item.action === 'skip' ? 'skip' : 'download') as 'download' | 'skip',
            warning: null,
          }));
        }
      } else if (instances.length > 0) {
        selectedInstanceId = instances[0].id;
        await onInstanceChange();
      }
    } catch { /* ignore */ }
  }

  onMount(load);

  async function onInstanceChange() {
    selectedInstance = instances.find(i => i.id === selectedInstanceId) || null;
    selectedSeriesId = null;
    selectedSeason = null;
    seriesList = [];
    episodes = [];
    entries = [];
    mappings = [];
    if (selectedInstanceId) {
      try {
        const raw = await listSonarrSeries(selectedInstanceId);
        seriesList = raw.map(s => ({ id: s.id, title: s.title, seasonCount: s.seasonCount }));
      } catch { showToast('Failed to load series'); }
    }
  }

  async function onSeriesChange() {
    selectedSeason = null;
    episodes = [];
    entries = [];
    mappings = [];
    if (selectedInstanceId && selectedSeriesId) {
      loadingEpisodes = true;
      try {
        episodes = await listSonarrEpisodes(selectedInstanceId, selectedSeriesId);
      } catch { showToast('Failed to load episodes'); }
      finally { loadingEpisodes = false; }
    }
  }

  async function inspectPlaylist() {
    if (!playlistUrl.trim() || !selectedInstanceId || !selectedSeriesId) {
      showToast('Select an instance and series first');
      return;
    }
    inspecting = true;
    mappings = [];
    try {
      const result = await inspectSonarrPlaylist(selectedInstanceId, {
        seriesId: selectedSeriesId,
        seasonNumber: selectedSeason ?? undefined,
        playlistUrl: playlistUrl.trim(),
      });
      entries = result.entries;
      seriesTitle = result.seriesTitle || '';
      episodes = result.episodes;
      mappings = result.entries.map((entry, i) => ({
        index: i,
        sourceTitle: entry.title || 'Untitled',
        sourceUrl: entry.url,
        duration: entry.duration,
        selectedEpisodeId: null,
        selectedEpisodeLabel: '',
        confidence: 'none' as const,
        action: 'download' as const,
        warning: null,
      }));
      autoMap();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to inspect playlist');
    } finally { inspecting = false; }
  }

  function autoMap() {
    if (!episodes.length || !mappings.length) return;
    autoMapping = true;

    const seasonEpisodes = selectedSeason !== null
      ? episodes.filter(e => e.seasonNumber === selectedSeason)
      : episodes;

    for (const m of mappings) {
      if (m.action === 'skip') continue;
      const title = m.sourceTitle.toLowerCase().replace(/[^a-z0-9\s]/g, '');
      let bestMatch: typeof seasonEpisodes[0] | null = null;
      let bestScore = 0;
      let matchMethod: 'title' | 'number' = 'title';

      for (const ep of seasonEpisodes) {
        const epTitle = (ep.title || '').toLowerCase().replace(/[^a-z0-9\s]/g, '');
        const words = title.split(/\s+/).filter(Boolean);
        const matchCount = words.filter(w => epTitle.includes(w)).length;
        const exactMatch = title === epTitle || title.includes(epTitle) || epTitle.includes(title);
        const score = exactMatch ? matchCount + 10 : matchCount;

        if (score > bestScore && score >= 1) {
          bestScore = score;
          bestMatch = ep;
          matchMethod = 'title';
        }
      }

      if (!bestMatch) {
        const epNumMatch = title.match(/(?:episode|ep|part|#)\s*(\d+)/i);
        if (epNumMatch) {
          const videoEpNum = parseInt(epNumMatch[1], 10);
          const byNumber = seasonEpisodes.find(e => e.episodeNumber === videoEpNum);
          if (byNumber) {
            bestMatch = byNumber;
            bestScore = 1;
            matchMethod = 'number';
          }
        }
      }

      if (bestMatch) {
        m.selectedEpisodeId = bestMatch.id;
        m.selectedEpisodeLabel = `S${String(bestMatch.seasonNumber).padStart(2, '0')}E${String(bestMatch.episodeNumber).padStart(2, '0')} - ${bestMatch.title || ''}`;
        m.confidence = matchMethod === 'number' ? 'low' : bestScore >= 8 ? 'high' : bestScore >= 4 ? 'medium' : 'low';
        m.warning = m.confidence === 'low' ? 'Low confidence match — please verify' : null;
      } else {
        m.selectedEpisodeId = null;
        m.selectedEpisodeLabel = '';
        m.confidence = 'none';
        m.warning = 'No matching episode found';
      }
    }

    autoMapping = false;
    mappings = mappings;
  }

  function setEpisode(mapping: MappingEntry, episodeId: string) {
    const ep = episodes.find(e => e.id === Number(episodeId));
    if (ep) {
      mapping.selectedEpisodeId = ep.id;
      mapping.selectedEpisodeLabel = `S${String(ep.seasonNumber).padStart(2, '0')}E${String(ep.episodeNumber).padStart(2, '0')} - ${ep.title || ''}`;
      mapping.confidence = 'manual';
      mapping.warning = null;
      mappings = mappings;
    }
  }

  function toggleSkip(mapping: MappingEntry) {
    mapping.action = mapping.action === 'skip' ? 'download' : 'skip';
    if (mapping.action === 'skip') {
      mapping.selectedEpisodeId = null;
      mapping.selectedEpisodeLabel = '';
      mapping.confidence = 'none';
      mapping.warning = null;
    }
    mappings = mappings;
  }

  function clearMapping() {
    for (const m of mappings) {
      m.selectedEpisodeId = null;
      m.selectedEpisodeLabel = '';
      m.confidence = 'none';
      m.warning = null;
      m.action = 'download';
    }
    mappings = mappings;
  }

  async function saveOnly() {
    if (!editingMappingId) return;
    const items = mappings.filter(m => m.action === 'download' && m.selectedEpisodeId).map(m => ({
      playlistIndex: m.index,
      episodeId: m.selectedEpisodeId!,
      seasonNumber: episodes.find(e => e.id === m.selectedEpisodeId)?.seasonNumber ?? undefined,
      episodeNumber: episodes.find(e => e.id === m.selectedEpisodeId)?.episodeNumber ?? undefined,
      episodeTitle: episodes.find(e => e.id === m.selectedEpisodeId)?.title || '',
      videoTitle: m.sourceTitle,
      videoUrl: m.sourceUrl,
      videoDuration: m.duration ?? undefined,
      action: m.action as 'download' | 'skip',
      confidence: m.confidence,
    }));
    saving = true;
    try {
      await updateSonarrPlaylistMapping(editingMappingId, { items });
      showToast('Mapping saved');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to save mapping');
    } finally { saving = false; }
  }

  async function saveAndDownload() {
    const toDownload = mappings.filter(m => m.action === 'download' && m.selectedEpisodeId);
    if (!toDownload.length) {
      showToast('No mapped items to download');
      return;
    }

    downloading = true;
    saving = true;
    try {
      const items = toDownload.map(m => ({
        playlistIndex: m.index,
        episodeId: m.selectedEpisodeId!,
        seasonNumber: episodes.find(e => e.id === m.selectedEpisodeId)?.seasonNumber ?? undefined,
        episodeNumber: episodes.find(e => e.id === m.selectedEpisodeId)?.episodeNumber ?? undefined,
        episodeTitle: episodes.find(e => e.id === m.selectedEpisodeId)?.title || '',
        videoTitle: m.sourceTitle,
        videoUrl: m.sourceUrl,
        videoDuration: m.duration ?? undefined,
        action: 'download' as const,
        confidence: m.confidence,
      }));

      let mappingId: string;
      if (editingMappingId) {
        const updated = await updateSonarrPlaylistMapping(editingMappingId, { items });
        mappingId = updated.id;
        showToast('Mapping updated');
      } else {
        const created = await createSonarrPlaylistMapping(selectedInstanceId!, {
          name: `${seriesTitle} playlist - ${new Date().toLocaleDateString()}`,
          seriesId: selectedSeriesId!,
          seasonNumber: selectedSeason ?? undefined,
          playlistUrl: playlistUrl.trim(),
          items,
        });
        mappingId = created.id;
      }

      const dlResult = await downloadSonarrPlaylistMapping(mappingId);
      const count = 'count' in dlResult ? dlResult.count : 1;
      showToast(`Started ${count} download${count !== 1 ? 's' : ''}`);
      navigate('downloads');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to start downloads');
    } finally { downloading = false; saving = false; }
  }

  $: mappedCount = mappings.filter(m => m.action === 'download' && m.selectedEpisodeId).length;
  $: skippedCount = mappings.filter(m => m.action === 'skip').length;
  $: unmappedCount = mappings.filter(m => m.action === 'download' && !m.selectedEpisodeId).length;
  $: canStart = unmappedCount === 0 && mappedCount > 0;

  function confidenceClass(c: string): string {
    if (c === 'high') return 'green';
    if (c === 'medium') return 'yellow';
    if (c === 'low') return 'red';
    if (c === 'manual') return 'purple';
    return 'muted';
  }
</script>

<div class="page">
  <header class="page-head">
    <div>
      <div class="crumbs">
        <span class="crumb">Sonarr</span> ›
        <span>Playlist Mapping</span>
      </div>
      <h1 class="page-title">{editing ? 'Edit' : 'New'} Playlist Mapping</h1>
      <p class="page-subtitle">Map YouTube playlist entries to Sonarr episodes before downloading.</p>
    </div>
  </header>

  <div class="two-col">
    <div>
      <section class="context-strip">
        <div class="context-item">
          <label class="context-label">Sonarr Instance</label>
          <select class="input" bind:value={selectedInstanceId} on:change={onInstanceChange}>
            <option value="">Select instance…</option>
            {#each instances as inst}
              <option value={inst.id}>{inst.name}</option>
            {/each}
          </select>
        </div>
        <div class="context-item">
          <label class="context-label">Series</label>
          <select class="input" bind:value={selectedSeriesId} on:change={onSeriesChange}>
            <option value={null}>Select series…</option>
            {#each seriesList as s}
              <option value={s.id}>{s.title}</option>
            {/each}
          </select>
        </div>
        <div class="context-item">
          <label class="context-label">Season</label>
          <select class="input" bind:value={selectedSeason}>
            <option value={null}>All seasons</option>
            {#if selectedSeriesId}
              {#each episodes.reduce((acc: number[], e) => { if (e.seasonNumber != null && !acc.includes(e.seasonNumber)) acc.push(e.seasonNumber); return acc; }, []).sort() as season}
                <option value={season}>Season {season}</option>
              {/each}
            {/if}
          </select>
        </div>
      </section>

      <section class="panel">
        <div class="playlist-input">
          <label class="search-box" style="flex:1">
            <svg width="18" height="18"><use href="#i-link"/></svg>
            <input type="url" bind:value={playlistUrl} placeholder="Paste YouTube playlist URL…" />
          </label>
          <button class="primary-btn" type="button" disabled={inspecting || !playlistUrl.trim()} on:click={inspectPlaylist}>
            <svg width="18" height="18"><use href="#i-refresh"/></svg>
            {inspecting ? 'Inspecting…' : entries.length ? 'Re-inspect' : 'Inspect'}
          </button>
        </div>
      </section>

      {#if entries.length}
        <section class="panel" style="margin-top:18px">
          <div class="mapping-toolbar">
            <div class="toolbar-left">
              <h2>Playlist Entries ({mappings.length})</h2>
              <span class="sub">Mapped: {mappedCount} | Skipped: {skippedCount} | Unmapped: {unmappedCount}</span>
            </div>
            <div class="toolbar-right">
              <button class="secondary-btn-sm" type="button" on:click={autoMap} disabled={!episodes.length || autoMapping}>
                {autoMapping ? 'Auto-mapping…' : 'Auto-map'}
              </button>
              <button class="secondary-btn-sm" type="button" on:click={clearMapping}>Clear</button>
            </div>
          </div>

          <div class="mapping-table">
            {#if mappings.length === 0}
              <div class="empty-state-sm"><strong>All entries mapped</strong></div>
            {:else}
              {#each mappings as mapping, i}
                <div class="mapping-row" class:skipped={mapping.action === 'skip'}>
                  <div class="row-index">#{mapping.index + 1}</div>
                  <div class="row-info">
                    <div class="row-title">{mapping.sourceTitle}</div>
                    <div class="row-sub">{mapping.duration ? `${Math.round(mapping.duration / 60)} min` : '—'}</div>
                  </div>
                  <div class="row-episode">
                    {#if episodes.length > 0}
                      <select class="input-sm" value={mapping.selectedEpisodeId ?? ''} on:change={(e) => setEpisode(mapping, e.currentTarget.value)} disabled={mapping.action === 'skip'}>
                        <option value="">— Select episode —</option>
                        {#if selectedSeason !== null}
                          {#each episodes.filter(e => e.seasonNumber === selectedSeason) as ep}
                            <option value={ep.id}>S{String(ep.seasonNumber).padStart(2, '0')}E{String(ep.episodeNumber).padStart(2, '0')} - {ep.title || 'Untitled'}{ep.hasFile ? ' ✓' : ''}</option>
                          {/each}
                        {:else}
                          {#each episodes as ep}
                            <option value={ep.id}>S{String(ep.seasonNumber).padStart(2, '0')}E{String(ep.episodeNumber).padStart(2, '0')} - {ep.title || 'Untitled'}{ep.hasFile ? ' ✓' : ''}</option>
                          {/each}
                        {/if}
                      </select>
                    {:else}
                      <span class="sub">Load episodes first</span>
                    {/if}
                  </div>
                  <div>
                    {#if mapping.selectedEpisodeId}
                      <span class="badge {confidenceClass(mapping.confidence)}">{mapping.confidence}</span>
                    {:else if mapping.action !== 'skip'}
                      <span class="badge muted">none</span>
                    {/if}
                  </div>
                  <div>
                    <label class="checkline" title={mapping.action === 'skip' ? 'Include' : 'Skip'}>
                      <input class="checkbox" type="checkbox" checked={mapping.action === 'download'} on:change={() => toggleSkip(mapping)} />
                    </label>
                  </div>
                  {#if mapping.warning}
                    <div class="row-warning">{mapping.warning}</div>
                  {/if}
                </div>
              {/each}
            {/if}
          </div>
        </section>
      {/if}
    </div>

    <aside class="side-panel">
      {#if entries.length}
        <div class="side-card summary-card">
          <h3>Mapping Summary</h3>
          <div class="summary-stats">
            <div class="stat-row">
              <span>Total entries</span>
              <b>{mappings.length}</b>
            </div>
            <div class="stat-row">
              <span>Mapped</span>
              <b class="green">{mappedCount}</b>
            </div>
            <div class="stat-row">
              <span>Skipped</span>
              <b class="yellow">{skippedCount}</b>
            </div>
            <div class="stat-row">
              <span>Unmapped</span>
              <b class="red">{unmappedCount}</b>
            </div>
          </div>
          {#if editing}
            <button class="secondary-btn full" type="button" disabled={saving} on:click={saveOnly}>
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          {/if}
          <button class="primary-btn full" type="button" disabled={!canStart || saving} on:click={saveAndDownload}>
            <svg width="18" height="18"><use href="#i-download"/></svg>
            {saving ? 'Saving…' : editing ? 'Update & Download' : 'Start Download'}{!saving && canStart ? ` (${mappedCount})` : ''}
          </button>
          {#if unmappedCount > 0}
            <p class="sub" style="margin-top:8px;text-align:center">All included entries must be mapped or skipped before downloading.</p>
          {/if}
        </div>
      {/if}

      <div class="side-card">
        <h3>How It Works</h3>
        <div class="steps">
          <div class="step">
            <div class="step-num">1</div>
            <div><b>Select instance & series</b><div class="sub">Choose the Sonarr instance and TV series.</div></div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div><b>Paste playlist</b><div class="sub">Inspect a YouTube playlist URL.</div></div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div><b>Auto-map</b><div class="sub">Suggest episode mappings by title.</div></div>
          </div>
          <div class="step">
            <div class="step-num">4</div>
            <div><b>Review & download</b><div class="sub">Fix conflicts, skip non-episodes, then start.</div></div>
          </div>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .page { min-width: 0; }
  .page-head { margin-bottom: 24px; }
  .page-title { margin: 8px 0 0; font-size: clamp(30px, 3.6vw, 42px); line-height: 1; letter-spacing: -0.055em; font-weight: 950; }
  .page-subtitle { margin: 10px 0 0; color: var(--muted); font-size: 15px; }
  .crumbs { margin-bottom: 4px; color: var(--muted); font-size: 14px; display: flex; gap: 6px; align-items: center; }
  .crumb { color: var(--purple-light); }
  .two-col { display: flex; gap: 24px; align-items: flex-start; }
  .two-col > div { flex: 1; min-width: 0; }
  .two-col > aside { width: 340px; flex: 0 0 auto; }
  .context-strip { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; padding: 16px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); margin-bottom: 18px; }
  .context-item { display: flex; flex-direction: column; gap: 6px; }
  .context-label { color: var(--muted); font-size: 13px; font-weight: 750; }
  .input { height: 44px; border-radius: 12px; padding: 0 14px; border: 1px solid rgba(255,255,255,.12); background: rgba(255,255,255,.045); color: white; font-size: 14px; outline: 0; width: 100%; }
  .input:focus { border-color: rgba(167,134,255,.4); }
  select.input { appearance: auto; }
  select.input option, select.input-sm option { color: #e0e0e0; background: #141829; }
  .panel { border-radius: 22px; overflow: hidden; background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025)), rgba(8,13,34,.64); border: 1px solid rgba(255,255,255,.105); box-shadow: 0 22px 60px rgba(0,0,0,.22); }
  .playlist-input { display: flex; gap: 12px; align-items: center; padding: 14px 18px; }
  .search-box { height: 44px; border-radius: 12px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.1); color: white; display: flex; align-items: center; gap: 8px; padding: 0 12px; }
  .search-box input { width: 100%; border: 0; outline: 0; color: white; background: transparent; font-size: 14px; }
  .primary-btn { height: 44px; border: 0; border-radius: 14px; padding: 0 18px; display: inline-flex; align-items: center; gap: 8px; color: white; cursor: pointer; font-weight: 850; font-size: 14px; background: linear-gradient(180deg, #956aff 0%, #6c35ff 56%, #4f22d8 100%); box-shadow: 0 12px 24px rgba(99,49,255,.3), inset 0 1px 0 rgba(255,255,255,.38), inset 0 -8px 14px rgba(39,8,143,.44); transition: 180ms ease; white-space: nowrap; }
  .primary-btn:hover { transform: translateY(-1px); }
  .primary-btn:disabled { opacity: 0.5; cursor: default; }
  .primary-btn.full, .secondary-btn.full { width: 100%; justify-content: center; height: 48px; margin-top: 12px; }
  .secondary-btn.full { border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.045); color: white; border-radius: 14px; display: inline-flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 850; letter-spacing: -0.02em; font-size: 15px; transition: 180ms ease; }
  .secondary-btn.full:hover { background: rgba(255,255,255,.075); }
  .secondary-btn.full:disabled { opacity: 0.5; cursor: default; }
  .mapping-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 18px; border-bottom: 1px solid rgba(255,255,255,.08); flex-wrap: wrap; }
  .toolbar-left { display: flex; align-items: center; gap: 12px; }
  .toolbar-left h2 { margin: 0; font-size: 16px; letter-spacing: -0.03em; }
  .toolbar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .checkline { display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 4px; border-radius: 6px; }
  .checkline:hover { background: rgba(255,255,255,.05); }
  .checkbox { width: 16px; height: 16px; accent-color: var(--purple); }
  .secondary-btn-sm { height: 34px; padding: 0 12px; border-radius: 9px; border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.045); color: white; cursor: pointer; font-weight: 800; font-size: 13px; white-space: nowrap; transition: 180ms ease; }
  .secondary-btn-sm:hover { background: rgba(255,255,255,.075); }
  .sub { color: var(--muted); font-size: 12px; }
  .mapping-table { display: grid; gap: 2px; padding: 6px 10px 14px; }
  .mapping-row { display: grid; grid-template-columns: 40px 1fr 220px 80px 36px; gap: 10px; align-items: center; padding: 10px 12px; border-radius: 12px; transition: 180ms ease; }
  .mapping-row:hover { background: rgba(255,255,255,.026); }
  .mapping-row.skipped { opacity: 0.5; }
  .row-index { font-weight: 900; font-size: 14px; color: var(--muted); text-align: center; }
  .row-title { font-weight: 800; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row-sub { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .row-warning { grid-column: 1 / -1; color: #ffc857; font-size: 12px; padding: 4px 0 0 50px; }
  .input-sm { height: 36px; border-radius: 9px; padding: 0 10px; border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.045); color: white; font-size: 13px; outline: 0; width: 100%; }
  .input-sm:focus { border-color: rgba(167,134,255,.4); }
  .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 850; }
  .badge.green { background: rgba(20,216,148,.16); color: var(--green); }
  .badge.yellow { background: rgba(255,200,87,.16); color: #ffc857; }
  .badge.red { background: rgba(255,77,126,.16); color: var(--red); }
  .badge.muted { background: rgba(169,175,208,.12); color: var(--muted); }
  .badge.purple { background: rgba(124,60,255,.2); color: var(--purple-light); }
  .icon-btn-sm { width: 32px; height: 32px; border-radius: 8px; border: 1px solid rgba(255,255,255,.08); background: transparent; color: var(--muted); cursor: pointer; display: grid; place-items: center; transition: 180ms ease; }
  .icon-btn-sm:hover { color: white; background: rgba(124,60,255,.15); }
  .empty-state-sm { padding: 32px 20px; text-align: center; color: var(--muted); font-size: 14px; }
  .empty-state-sm strong { color: white; }
  .side-panel { display: flex; flex-direction: column; gap: 16px; position: sticky; top: 24px; align-self: start; }
  .side-card { padding: 18px; border-radius: 18px; background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025)), rgba(8,13,34,.6); border: 1px solid rgba(255,255,255,.095); }
  .side-card h3 { margin: 0 0 14px; font-size: 16px; letter-spacing: -0.03em; }
  .summary-card { max-height: calc(100vh - 100px); overflow-y: auto; }
  .summary-stats { display: flex; flex-direction: column; gap: 10px; }
  .stat-row { display: flex; justify-content: space-between; align-items: center; font-size: 14px; }
  .stat-row b { font-weight: 850; }
  .stat-row .green { color: var(--green); }
  .stat-row .yellow { color: #ffc857; }
  .stat-row .red { color: var(--red); }
  .steps { display: flex; flex-direction: column; gap: 12px; }
  .step { display: flex; gap: 12px; align-items: flex-start; }
  .step-num { width: 26px; height: 26px; border-radius: 999px; background: rgba(124,60,255,.2); color: var(--purple-light); display: grid; place-items: center; font-weight: 900; font-size: 13px; flex: 0 0 auto; }
  @media (max-width: 1240px) { .two-col { flex-direction: column; } .two-col > aside { width: 100%; } .context-strip { grid-template-columns: 1fr 1fr; } .mapping-row { grid-template-columns: 30px 1fr 160px 60px 32px; } }
  @media (max-width: 900px) { .context-strip { grid-template-columns: 1fr; } .mapping-row { grid-template-columns: 24px 1fr; gap: 6px; } .mapping-row .row-episode, .mapping-row .badge, .mapping-row .icon-btn-sm { grid-column: 2; } }
</style>
