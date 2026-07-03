<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import AppShell from '$lib/components/layout/AppShell.svelte';
  import HeroActionPanel from '$lib/components/home/HeroActionPanel.svelte';
  import QuickManageCards from '$lib/components/home/QuickManageCards.svelte';
  import Icons from '$lib/components/layout/Icons.svelte';
  import ToastHost from '$lib/components/shared/ToastHost.svelte';
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import SearchResults from '$lib/components/search/SearchResults.svelte';
  import MetadataResult from '$lib/components/search/MetadataResult.svelte';
  import PlaylistResult from '$lib/components/search/PlaylistResult.svelte';
  import LiveVideoProgress from '$lib/components/downloads/live/LiveVideoProgress.svelte';
  import LivePlaylistProgress from '$lib/components/downloads/live/LivePlaylistProgress.svelte';
  import TasksDialog from '$lib/components/tasks/TasksDialog.svelte';
  import TaskDetailDialog from '$lib/components/tasks/TaskDetailDialog.svelte';
  import FilesDialog from '$lib/components/files/FilesDialog.svelte';
  import ProfilesDialog from '$lib/components/profiles/ProfilesDialog.svelte';
  import SettingsDialog from '$lib/components/settings/SettingsDialog.svelte';
  import HealthDialog from '$lib/components/settings/HealthDialog.svelte';
  import { searchMedia } from '$lib/api/search';
  import { getMetadata } from '$lib/api/metadata';
  import { getPlaylist } from '$lib/api/playlist';
  import { getHealth } from '$lib/api/health';
  import { listProfiles } from '$lib/api/profiles';
  import type { HealthResponse, MetadataResponse, PlaylistResponse, ProfileResponse, SearchResponse, TaskResponse } from '$lib/api/types';
  import { connectEventStream, disconnectEventStream } from '$lib/state/event-stream';

  let health: HealthResponse | null = null;
  let profiles: ProfileResponse[] = [];
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
      [health, profiles] = await Promise.all([
        getHealth().catch(() => null),
        listProfiles({ limit: 200, offset: 0 }).catch(() => [])
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

  onMount(() => {
    refreshChrome();
    connectEventStream();
  });

  onDestroy(disconnectEventStream);
</script>

<Icons />

<AppShell {health} onOpen={openDialog} onTask={handleTask} onViewAll={handleViewAll}>
  <section class="hero">
    <div class="logo-lockup">
      <svg class="logo-mark" viewBox="0 0 120 120" aria-hidden="true">
        <use href="#logo-symbol"></use>
      </svg>
      <h1 class="wordmark">Tube <span>Explore</span></h1>
    </div>

    <HeroActionPanel
      {busy}
      onSearch={(q, limit) => run(() => searchMedia(q, limit), (data) => { searchResult = data; dialog = 'searchResults'; })}
      onInspectMetadata={(url) => run(() => getMetadata(url), (data) => { metadata = data; dialog = 'metadata'; })}
      onInspectPlaylist={(url) => run(() => getPlaylist(url), (data) => { playlist = data; dialog = 'playlist'; })}
      onDownloadVideo={openDownloadVideo}
      onDownloadPlaylist={openDownloadPlaylist}
    />

    <ErrorMessage message={error} />

    <QuickManageCards onOpen={openDialog} />
  </section>
</AppShell>

<ToastHost />

{#if dialog === 'searchResults' && searchResult}
  <ModalFrame title={`Search results for "${searchResult.query}"`} size="large" onClose={() => dialog = null}>
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
  <LiveVideoProgress url={downloadUrl} {profiles} onClose={() => dialog = null} onCreated={refreshChrome} />
{/if}

{#if dialog === 'playlistDownload'}
  <LivePlaylistProgress url={downloadUrl} {profiles} onClose={() => dialog = null} onCreated={refreshChrome} />
{/if}

{#if dialog === 'tasks'}<TasksDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'taskDetail' && selectedTask}<TaskDetailDialog task={selectedTask} onClose={() => { dialog = null; selectedTask = null; }} onChanged={refreshChrome} />{/if}
{#if dialog === 'files'}<FilesDialog onClose={() => dialog = null} />{/if}
{#if dialog === 'profiles'}<ProfilesDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'settings'}<SettingsDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'health'}<HealthDialog {health} onClose={() => { dialog = null; refreshChrome(); }} />{/if}
