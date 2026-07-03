<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import DownloadOptionsForm from './DownloadOptionsForm.svelte';
  import { startPlaylistDownload } from '$lib/api/downloads';
  import { showToast } from '$lib/state/toast-state';
  import type { DownloadPlaylistRequest, ProfileResponse } from '$lib/api/types';

  export let url = '';
  export let profiles: ProfileResponse[] = [];
  export let onClose: () => void = () => {};
  export let onCreated: (taskId: string) => void = () => {};
  let form: Partial<DownloadPlaylistRequest> = { url, embedMetadata: true, embedThumbnail: true };
  let busy = false;
  let error: string | null = null;

  async function submit() {
    error = null;
    busy = true;
    try {
      const result = await startPlaylistDownload(form as DownloadPlaylistRequest);
      showToast(`Playlist download queued: ${result.taskId}`);
      onCreated(result.taskId);
      onClose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start playlist download';
    } finally {
      busy = false;
    }
  }
</script>

<ModalFrame title="New playlist download" onClose={onClose}>
  <ErrorMessage message={error} />
  <DownloadOptionsForm value={form} {profiles} isPlaylist onChange={(v) => form = v} />
  <div class="dialog-actions">
    <button class="btn" on:click={onClose}>Cancel</button>
    <button class="btn primary" disabled={busy || !form.url} on:click={submit}>{busy ? 'Starting…' : 'Start playlist download'}</button>
  </div>
</ModalFrame>
