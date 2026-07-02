<script lang="ts">
  import { onMount } from 'svelte';
  import AppShell from '$lib/components/layout/AppShell.svelte';
  import HeroActionPanel from '$lib/components/home/HeroActionPanel.svelte';
  import QuickManageCards from '$lib/components/home/QuickManageCards.svelte';
  import ToastHost from '$lib/components/shared/ToastHost.svelte';
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import SearchResults from '$lib/components/search/SearchResults.svelte';
  import MetadataResult from '$lib/components/search/MetadataResult.svelte';
  import PlaylistResult from '$lib/components/search/PlaylistResult.svelte';
  import VideoDownloadDialog from '$lib/components/downloads/VideoDownloadDialog.svelte';
  import PlaylistDownloadDialog from '$lib/components/downloads/PlaylistDownloadDialog.svelte';
  import TasksDialog from '$lib/components/tasks/TasksDialog.svelte';
  import TaskDetailDialog from '$lib/components/tasks/TaskDetailDialog.svelte';
  import FilesDialog from '$lib/components/files/FilesDialog.svelte';
  import ProfilesDialog from '$lib/components/profiles/ProfilesDialog.svelte';
  import PresetsDialog from '$lib/components/presets/PresetsDialog.svelte';
  import OutboxDialog from '$lib/components/outbox/OutboxDialog.svelte';
  import SettingsDialog from '$lib/components/settings/SettingsDialog.svelte';
  import HealthDialog from '$lib/components/settings/HealthDialog.svelte';
  import { searchMedia } from '$lib/api/search';
  import { getMetadata } from '$lib/api/metadata';
  import { getPlaylist } from '$lib/api/playlist';
  import { getHealth } from '$lib/api/health';
  import { listProfiles } from '$lib/api/profiles';
  import { listPresets } from '$lib/api/presets';
  import type { ConversionPresetResponse, HealthResponse, MetadataResponse, PlaylistResponse, ProfileResponse, SearchResponse, TaskResponse } from '$lib/api/types';

  let health: HealthResponse | null = null;
  let profiles: ProfileResponse[] = [];
  let presets: ConversionPresetResponse[] = [];
  let busy = false;
  let error: string | null = null;
  let dialog: string | null = null;
  let downloadUrl = '';
  let selectedTask: TaskResponse | null = null;
  let searchResult: SearchResponse | null = null;
  let metadata: MetadataResponse | null = null;
  let playlist: PlaylistResponse | null = null;

  async function refreshChrome() {
    try {
      [health, profiles, presets] = await Promise.all([
        getHealth().catch(() => null),
        listProfiles({ limit: 200, offset: 0 }).catch(() => []),
        listPresets({ limit: 200, offset: 0 }).catch(() => [])
      ]);
    } catch {
      // individual calls already guarded
    }
  }

  async function run<T>(fn: () => Promise<T>, onDone: (value: T) => void) {
    busy = true; error = null;
    try { onDone(await fn()); } catch (e) { error = e instanceof Error ? e.message : 'Request failed'; } finally { busy = false; }
  }

  function openDownloadVideo(url = '') { downloadUrl = url; dialog = 'videoDownload'; }
  function openDownloadPlaylist(url = '') { downloadUrl = url; dialog = 'playlistDownload'; }
  function openDialog(key: string) { dialog = key; }
  function handleTask(task: TaskResponse) { selectedTask = task; dialog = 'taskDetail'; }
  function handleViewAll() { dialog = 'tasks'; }

  onMount(refreshChrome);
</script>

<AppShell {health} onOpen={openDialog} onNewDownload={() => openDownloadVideo('')} onTask={handleTask} onViewAll={handleViewAll}>
  <HeroActionPanel
    {busy}
    onSearch={(q, limit) => run(() => searchMedia(q, limit), (data) => { searchResult = data; dialog = 'searchResults'; })}
    onInspectMetadata={(url) => run(() => getMetadata(url), (data) => { metadata = data; dialog = 'metadata'; })}
    onInspectPlaylist={(url) => run(() => getPlaylist(url), (data) => { playlist = data; dialog = 'playlist'; })}
    onDownloadVideo={openDownloadVideo}
    onDownloadPlaylist={openDownloadPlaylist}
  />

  <ErrorMessage message={error} />

  <div class="grid main-grid">
    <section class="panel card">
      <div class="card-header"><h2>Quick actions</h2></div>
      <div class="simple-list">
        <button class="row clickable" on:click={() => openDownloadVideo('')}><div class="avatar">⇩</div><div><div class="row-title">New video download</div><div class="row-sub">Use a profile or override options.</div></div><strong>→</strong></button>
        <button class="row clickable" on:click={() => openDownloadPlaylist('')}><div class="avatar">♫</div><div><div class="row-title">New playlist download</div><div class="row-sub">Optionally select a range.</div></div><strong>→</strong></button>
        <button class="row clickable" on:click={() => dialog = 'files'}><div class="avatar">▣</div><div><div class="row-title">Downloaded files</div><div class="row-sub">Browse completed downloads.</div></div><strong>→</strong></button>
      </div>
    </section>
    <section class="panel card">
      <div class="card-header"><h2>Use it your way</h2></div>
      <div class="simple-list">
        <button class="row clickable" on:click={() => dialog = 'profiles'}><div class="avatar">♙</div><div><div class="row-title">Manage profiles</div><div class="row-sub">Create and edit download profiles.</div></div><strong>→</strong></button>
        <button class="row clickable" on:click={() => dialog = 'presets'}><div class="avatar">⚙</div><div><div class="row-title">Manage presets</div><div class="row-sub">Customize conversion presets.</div></div><strong>→</strong></button>
        <button class="row clickable" on:click={() => dialog = 'settings'}><div class="avatar">◌</div><div><div class="row-title">Settings</div><div class="row-sub">Configure application settings.</div></div><strong>→</strong></button>
      </div>
    </section>
  </div>

  <QuickManageCards onOpen={openDialog} />
</AppShell>

<ToastHost />

{#if dialog === 'searchResults' && searchResult}
  <ModalFrame title={`Search results for “${searchResult.query}”`} size="large" onClose={() => dialog = null}>
    <SearchResults data={searchResult} onInspect={(url) => run(() => getMetadata(url), (data) => { metadata = data; dialog = 'metadata'; })} onDownload={openDownloadVideo} />
  </ModalFrame>
{/if}

{#if dialog === 'metadata' && metadata}
  <ModalFrame title="Media metadata" size="large" onClose={() => dialog = null}>
    <MetadataResult data={metadata} onDownload={openDownloadVideo} />
  </ModalFrame>
{/if}

{#if dialog === 'playlist' && playlist}
  <ModalFrame title="Playlist" size="large" onClose={() => dialog = null}>
    <PlaylistResult data={playlist} onDownloadPlaylist={openDownloadPlaylist} onDownloadVideo={openDownloadVideo} />
  </ModalFrame>
{/if}

{#if dialog === 'videoDownload'}
  <VideoDownloadDialog url={downloadUrl} {profiles} {presets} onClose={() => dialog = null} onCreated={refreshChrome} />
{/if}

{#if dialog === 'playlistDownload'}
  <PlaylistDownloadDialog url={downloadUrl} {profiles} {presets} onClose={() => dialog = null} onCreated={refreshChrome} />
{/if}

{#if dialog === 'tasks'}<TasksDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'taskDetail' && selectedTask}<TaskDetailDialog task={selectedTask} onClose={() => { dialog = null; selectedTask = null; }} onChanged={refreshChrome} />{/if}
{#if dialog === 'files'}<FilesDialog onClose={() => dialog = null} />{/if}
{#if dialog === 'profiles'}<ProfilesDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'presets'}<PresetsDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'outbox'}<OutboxDialog onClose={() => dialog = null} />{/if}
{#if dialog === 'settings'}<SettingsDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'health'}<HealthDialog {health} onClose={() => { dialog = null; refreshChrome(); }} />{/if}