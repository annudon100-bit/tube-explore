<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import QualityFields from '$lib/components/downloads/QualityFields.svelte';
  import { createProfile, patchProfile } from '$lib/api/profiles';
  import { showToast } from '$lib/state/toast-state';
  import type { AudioFormat, FormatType, ProfileResponse, ProfileCreateRequest, ProfileUpdateRequest, QualityMode } from '$lib/api/types';

  export let profile: ProfileResponse | null = null;
  export let onClose: () => void = () => {};
  export let onSaved: () => void = () => {};
  let form: Partial<ProfileCreateRequest & ProfileUpdateRequest> = profile ? { ...profile } : { downloadQualityMode: 'best', embedMetadata: true, embedThumbnail: true, subtitles: false, formatType: 'video+audio' as FormatType };
  let error: string | null = null;
  let busy = false;

  function set(key: string, value: unknown) { form = { ...form, [key]: value }; }

  $: showAudio = form.formatType === 'audio-only' || !!form.audioFormat;

  async function save() {
    error = null; busy = true;
    try {
      if (profile) await patchProfile(profile.id, form);
      else await createProfile(form as ProfileCreateRequest);
      showToast(profile ? 'Profile updated' : 'Profile created');
      onSaved(); onClose();
    } catch (e) { error = e instanceof Error ? e.message : 'Unable to save profile'; }
    finally { busy = false; }
  }

  const audioFormatOptions: { label: string; value: AudioFormat }[] = [
    { label: 'Best (default)', value: 'best' },
    { label: 'MP3', value: 'mp3' },
    { label: 'AAC', value: 'aac' },
    { label: 'FLAC', value: 'flac' },
    { label: 'Opus', value: 'opus' },
    { label: 'Vorbis', value: 'vorbis' },
    { label: 'M4A', value: 'm4a' },
    { label: 'WAV', value: 'wav' },
    { label: 'ALAC', value: 'alac' },
  ];
</script>

<ModalFrame title={profile ? 'Edit profile' : 'Create profile'} onClose={onClose}>
  <ErrorMessage message={error} />
  <div class="form-grid">
    <div class="field"><label>Name</label><input class="input" value={form.name || ''} on:input={(e) => set('name', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Label</label><input class="input" value={form.label || ''} on:input={(e) => set('label', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Download directory</label><input class="input" value={form.downloadDirectory || ''} on:input={(e) => set('downloadDirectory', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Download format</label><input class="input" value={form.downloadFormat || ''} on:input={(e) => set('downloadFormat', (e.currentTarget as HTMLInputElement).value)} /></div>

    <QualityFields mode={(form.downloadQualityMode || '') as QualityMode | ''} value={form.downloadQualityValue ?? null} onChange={(m, v) => { set('downloadQualityMode', m || null); set('downloadQualityValue', v); }} />

    <div class="field">
      <label>Format type</label>
      <select class="select" value={form.formatType || 'video+audio'} on:change={(e) => set('formatType', (e.currentTarget as HTMLSelectElement).value || null)}>
        <option value="video+audio">Video + Audio</option>
        <option value="video-only">Video only</option>
        <option value="audio-only">Audio only</option>
      </select>
    </div>

    {#if form.formatType === 'audio-only'}
      <div class="field">
        <label>Audio format</label>
        <select class="select" value={form.audioFormat || 'mp3'} on:change={(e) => set('audioFormat', (e.currentTarget as HTMLSelectElement).value as AudioFormat || null)}>
          {#each audioFormatOptions as opt}
            <option value={opt.value}>{opt.label}</option>
          {/each}
        </select>
      </div>
      <div class="field">
        <label>Audio quality</label>
        <input class="input" placeholder="e.g. 192K, 320K" value={form.audioQuality || ''} on:input={(e) => set('audioQuality', (e.currentTarget as HTMLInputElement).value || null)} />
        <span class="help">Bitrate: 128K, 192K, 320K, etc.</span>
      </div>
    {:else}
      <div class="field">
        <label>Remux to container</label>
        <select class="select" value={form.remuxTo || ''} on:change={(e) => set('remuxTo', (e.currentTarget as HTMLSelectElement).value || null)}>
          <option value="">No remux</option>
          <option value="mp4">MP4</option>
          <option value="mkv">MKV</option>
          <option value="webm">WebM</option>
          <option value="mov">MOV</option>
          <option value="avi">AVI</option>
        </select>
        <span class="help">Changes container without re-encoding.</span>
      </div>
    {/if}

    <div class="field full"><label>Filename template</label><input class="input" value={form.filenameTemplate || ''} on:input={(e) => set('filenameTemplate', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field full"><label>Playlist template</label><input class="input" value={form.playlistTemplate || ''} on:input={(e) => set('playlistTemplate', (e.currentTarget as HTMLInputElement).value)} /></div>
    <label class="checkbox-line"><input type="checkbox" checked={form.embedMetadata !== false} on:change={(e) => set('embedMetadata', (e.currentTarget as HTMLInputElement).checked)} /> Embed metadata</label>
    <label class="checkbox-line"><input type="checkbox" checked={form.embedThumbnail !== false} on:change={(e) => set('embedThumbnail', (e.currentTarget as HTMLInputElement).checked)} /> Embed thumbnail</label>
    <label class="checkbox-line"><input type="checkbox" checked={!!form.subtitles} on:change={(e) => set('subtitles', (e.currentTarget as HTMLInputElement).checked)} /> Subtitles</label>
    <div class="field"><label>Subtitle languages</label><input class="input" value={form.subtitleLangs || ''} on:input={(e) => set('subtitleLangs', (e.currentTarget as HTMLInputElement).value)} /></div>
  </div>
  <div class="dialog-actions"><button class="btn" on:click={onClose}>Cancel</button><button class="btn primary" disabled={busy || !form.name} on:click={save}>{busy ? 'Saving…' : 'Save profile'}</button></div>
</ModalFrame>
