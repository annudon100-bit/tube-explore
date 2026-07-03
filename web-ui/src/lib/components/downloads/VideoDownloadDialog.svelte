<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import DownloadOptionsForm from './DownloadOptionsForm.svelte';
  import { startVideoDownload } from '$lib/api/downloads';
  import { showToast } from '$lib/state/toast-state';
  import type { DownloadVideoRequest, ProfileResponse } from '$lib/api/types';

  export let url = '';
  export let profiles: ProfileResponse[] = [];
  export let onClose: () => void = () => {};
  export let onCreated: (taskId: string) => void = () => {};
  let form: Partial<DownloadVideoRequest> = { url, embedMetadata: true, embedThumbnail: true };
  let busy = false;
  let error: string | null = null;

  async function submit() {
    error = null;
    busy = true;
    try {
      const result = await startVideoDownload(form as DownloadVideoRequest);
      showToast(`Video download queued: ${result.taskId}`);
      onCreated(result.taskId);
      onClose();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start download';
    } finally {
      busy = false;
    }
  }
</script>

<ModalFrame title="New video download" onClose={onClose}>
  <ErrorMessage message={error} />
  <DownloadOptionsForm value={form} {profiles} onChange={(v) => form = v} />
  <div class="dialog-actions">
    <button class="btn" on:click={onClose}>Cancel</button>
    <button class="btn primary" disabled={busy || !form.url} on:click={submit}>{busy ? 'Starting…' : 'Start download'}</button>
  </div>
</ModalFrame>
