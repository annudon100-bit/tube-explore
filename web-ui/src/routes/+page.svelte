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
  import DownloadTaskDetailDialog from '$lib/components/downloads/live/DownloadTaskDetailDialog.svelte';
  import VideoDownloadDialog from '$lib/components/downloads/VideoDownloadDialog.svelte';
  import PlaylistDownloadDialog from '$lib/components/downloads/PlaylistDownloadDialog.svelte';
  import DownloadsPage from '$lib/components/downloads/DownloadsPage.svelte';
  import FilesPage from '$lib/components/files/FilesPage.svelte';
  import ProfilesDialog from '$lib/components/profiles/ProfilesDialog.svelte';
  import SettingsDialog from '$lib/components/settings/SettingsDialog.svelte';
  import HealthDialog from '$lib/components/settings/HealthDialog.svelte';
  import RadarrInstances from '$lib/components/radarr/RadarrInstances.svelte';
  import RadarrInstanceForm from '$lib/components/radarr/RadarrInstanceForm.svelte';
  import RadarrSettings from '$lib/components/radarr/RadarrSettings.svelte';
  import MissingMovies from '$lib/components/radarr/MissingMovies.svelte';
  import RadarrSearchContext from '$lib/components/radarr/RadarrSearchContext.svelte';
  import { searchMedia } from '$lib/api/search';
  import { getMetadata } from '$lib/api/metadata';
  import { getPlaylist } from '$lib/api/playlist';
  import { getHealth } from '$lib/api/health';
  import { listProfiles } from '$lib/api/profiles';
  import { getTask } from '$lib/api/tasks';
  import type { HealthResponse, MetadataResponse, PlaylistResponse, ProfileResponse, SearchResponse, TaskResponse } from '$lib/api/types';
  import { connectEventStream, disconnectEventStream } from '$lib/state/event-stream';

  let currentPage: string = 'home';
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
  let pageData: Record<string, any> = {};
  let transitioning = false;

  function navigate(page: string, data?: any) {
    if (page === 'home' || page === 'downloads' || page === 'files' || page.startsWith('radarr-') || page === 'missing-movies') {
      if (data) pageData = data;
      currentPage = page;
    }
  }

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

  function openDownloadVideo(url = '') { downloadUrl = url; dialog = 'videoDownload'; selectedTask = null; }
  function openDownloadPlaylist(url = '') { downloadUrl = url; dialog = 'playlistDownload'; selectedTask = null; }
  function openDialog(key: string) { dialog = key; }
  function handleTask(task: TaskResponse) { selectedTask = task; dialog = 'taskDetail'; }
  async function handleCreatedTask(taskId: string) {
    transitioning = true;
    refreshChrome();
    try {
      const task = await getTask(taskId);
      selectedTask = task;
      dialog = 'taskDetail';
    } catch {
      dialog = null;
    }
    transitioning = false;
  }

  onMount(() => {
    refreshChrome();
    connectEventStream();
  });

  onDestroy(disconnectEventStream);
</script>

<Icons />

<AppShell {health} onOpen={openDialog} onTask={handleTask} activePage={currentPage} {navigate}>
  {#if currentPage === 'home'}
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
  {:else if currentPage === 'downloads'}
    <DownloadsPage onOpen={openDialog} onTask={handleTask} />
  {:else if currentPage === 'files'}
    <FilesPage />
  {:else if currentPage === 'radarr-instances'}
    <RadarrInstances {navigate} />
  {:else if currentPage === 'radarr-instance-form'}
    <RadarrInstanceForm {navigate} instance={pageData.instance ?? null} />
  {:else if currentPage === 'radarr-settings'}
    <RadarrSettings {navigate} />
  {:else if currentPage === 'missing-movies'}
    <MissingMovies {navigate} instance={pageData.instance ?? null} />
  {:else if currentPage === 'radarr-search-context'}
    <RadarrSearchContext {navigate} instance={pageData.instance} movie={pageData.movie} presetUrl={pageData.presetUrl || ''} />
  {/if}
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
  <VideoDownloadDialog url={downloadUrl} {profiles} onClose={() => { if (!transitioning) dialog = null; }} onCreated={handleCreatedTask} />
{/if}

{#if dialog === 'playlistDownload'}
  <PlaylistDownloadDialog url={downloadUrl} {profiles} onClose={() => { if (!transitioning) dialog = null; }} onCreated={handleCreatedTask} />
{/if}

{#if dialog === 'taskDetail' && selectedTask}<DownloadTaskDetailDialog task={selectedTask} onClose={() => { dialog = null; selectedTask = null; }} onChanged={refreshChrome} />{/if}

{#if dialog === 'profiles'}<ProfilesDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'settings'}<SettingsDialog onClose={() => { dialog = null; refreshChrome(); }} />{/if}
{#if dialog === 'health'}<HealthDialog {health} onClose={() => { dialog = null; refreshChrome(); }} />{/if}
