<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import QualityFields from '$lib/components/downloads/QualityFields.svelte';
  import { createProfile, patchProfile } from '$lib/api/profiles';
  import { showToast } from '$lib/state/toast-state';
  import type { ProfileResponse, ProfileCreateRequest, ProfileUpdateRequest, QualityMode } from '$lib/api/types';

  export let profile: ProfileResponse | null = null;
  export let onClose: () => void = () => {};
  export let onSaved: () => void = () => {};
  let form: Partial<ProfileCreateRequest & ProfileUpdateRequest> = profile ? { ...profile } : { downloadQualityMode: 'best', convertQualityMode: 'best', embedMetadata: true, embedThumbnail: true, subtitles: false };
  let error: string | null = null;
  let busy = false;

  function set(key: string, value: unknown) { form = { ...form, [key]: value }; }
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
</script>

<ModalFrame title={profile ? 'Edit profile' : 'Create profile'} onClose={onClose}>
  <ErrorMessage message={error} />
  <div class="form-grid">
    <div class="field"><label>Name</label><input class="input" value={form.name || ''} on:input={(e) => set('name', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Label</label><input class="input" value={form.label || ''} on:input={(e) => set('label', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Download directory</label><input class="input" value={form.downloadDirectory || ''} on:input={(e) => set('downloadDirectory', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Download format</label><input class="input" value={form.downloadFormat || ''} on:input={(e) => set('downloadFormat', (e.currentTarget as HTMLInputElement).value)} /></div>
    <QualityFields mode={(form.downloadQualityMode || '') as QualityMode | ''} value={form.downloadQualityValue ?? null} onChange={(m, v) => { set('downloadQualityMode', m || null); set('downloadQualityValue', v); }} />
    <div class="field"><label>Conversion preset</label><input class="input" value={form.convertPreset || ''} on:input={(e) => set('convertPreset', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Convert format</label><input class="input" value={form.convertFormat || ''} on:input={(e) => set('convertFormat', (e.currentTarget as HTMLInputElement).value)} /></div>
    <QualityFields mode={(form.convertQualityMode || '') as QualityMode | ''} value={form.convertQualityValue ?? null} onChange={(m, v) => { set('convertQualityMode', m || null); set('convertQualityValue', v); }} />
    <div class="field full"><label>Filename template</label><input class="input" value={form.filenameTemplate || ''} on:input={(e) => set('filenameTemplate', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field full"><label>Playlist template</label><input class="input" value={form.playlistTemplate || ''} on:input={(e) => set('playlistTemplate', (e.currentTarget as HTMLInputElement).value)} /></div>
    <label class="checkbox-line"><input type="checkbox" checked={form.embedMetadata !== false} on:change={(e) => set('embedMetadata', (e.currentTarget as HTMLInputElement).checked)} /> Embed metadata</label>
    <label class="checkbox-line"><input type="checkbox" checked={form.embedThumbnail !== false} on:change={(e) => set('embedThumbnail', (e.currentTarget as HTMLInputElement).checked)} /> Embed thumbnail</label>
    <label class="checkbox-line"><input type="checkbox" checked={!!form.subtitles} on:change={(e) => set('subtitles', (e.currentTarget as HTMLInputElement).checked)} /> Subtitles</label>
    <div class="field"><label>Subtitle languages</label><input class="input" value={form.subtitleLangs || ''} on:input={(e) => set('subtitleLangs', (e.currentTarget as HTMLInputElement).value)} /></div>
  </div>
  <div class="dialog-actions"><button class="btn" on:click={onClose}>Cancel</button><button class="btn primary" disabled={busy || !form.name} on:click={save}>{busy ? 'Saving…' : 'Save profile'}</button></div>
</ModalFrame>
