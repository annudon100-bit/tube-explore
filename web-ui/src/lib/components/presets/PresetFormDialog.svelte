<script lang="ts">
  import ModalFrame from '$lib/components/shared/ModalFrame.svelte';
  import ErrorMessage from '$lib/components/shared/ErrorMessage.svelte';
  import { createPreset, patchPreset } from '$lib/api/presets';
  import { showToast } from '$lib/state/toast-state';
  import type { AudioCodec, Container, ConversionPresetCreateRequest, ConversionPresetResponse, OutputExt, VideoCodec } from '$lib/api/types';

  export let preset: ConversionPresetResponse | null = null;
  export let onClose: () => void = () => {};
  export let onSaved: () => void = () => {};
  const containers: Container[] = ['mp4','mkv','webm','mp3','flac','m4a','opus','wav','mov','avi'];
  const videoCodecs: Array<VideoCodec | ''> = ['', 'h264','hevc','av1','vp9'];
  const audioCodecs: Array<AudioCodec | ''> = ['', 'aac','mp3','opus','flac','vorbis'];
  let form: any = preset ? { ...preset } : { container: 'mp4', outputExt: 'mp4' };
  let error: string | null = null; let busy = false;
  function set(key: string, value: unknown) { form = { ...form, [key]: value || null }; }
  async function save() { error = null; busy = true; try { if (preset) await patchPreset(preset.name, form); else await createPreset(form as ConversionPresetCreateRequest); showToast(preset ? 'Preset updated' : 'Preset created'); onSaved(); onClose(); } catch(e) { error = e instanceof Error ? e.message : 'Unable to save preset'; } finally { busy = false; } }
</script>

<ModalFrame title={preset ? 'Edit preset' : 'Create preset'} onClose={onClose}>
  <ErrorMessage message={error} />
  <div class="form-grid">
    <div class="field"><label>Name</label><input class="input" value={form.name || ''} on:input={(e) => set('name', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Label</label><input class="input" value={form.label || ''} on:input={(e) => set('label', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Container</label><select class="select" value={form.container || 'mp4'} on:change={(e) => set('container', (e.currentTarget as HTMLSelectElement).value)}>{#each containers as item}<option value={item}>{item}</option>{/each}</select></div>
    <div class="field"><label>Output extension</label><select class="select" value={form.outputExt || 'mp4'} on:change={(e) => set('outputExt', (e.currentTarget as HTMLSelectElement).value)}>{#each containers as item}<option value={item}>{item}</option>{/each}</select></div>
    <div class="field"><label>Video codec</label><select class="select" value={form.videoCodec || ''} on:change={(e) => set('videoCodec', (e.currentTarget as HTMLSelectElement).value)}>{#each videoCodecs as item}<option value={item}>{item || 'None'}</option>{/each}</select></div>
    <div class="field"><label>Audio codec</label><select class="select" value={form.audioCodec || ''} on:change={(e) => set('audioCodec', (e.currentTarget as HTMLSelectElement).value)}>{#each audioCodecs as item}<option value={item}>{item || 'None'}</option>{/each}</select></div>
    <div class="field"><label>Video bitrate</label><input class="input" placeholder="5M" value={form.videoBitrate || ''} on:input={(e) => set('videoBitrate', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Audio bitrate</label><input class="input" placeholder="128k" value={form.audioBitrate || ''} on:input={(e) => set('audioBitrate', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>FPS</label><input class="input" type="number" value={form.videoFps ?? ''} on:input={(e) => set('videoFps', Number((e.currentTarget as HTMLInputElement).value) || null)} /></div>
    <div class="field"><label>Video preset</label><input class="input" placeholder="slow, medium, fast" value={form.videoPreset || ''} on:input={(e) => set('videoPreset', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Pixel format</label><input class="input" placeholder="yuv420p" value={form.videoPixfmt || ''} on:input={(e) => set('videoPixfmt', (e.currentTarget as HTMLInputElement).value)} /></div>
    <div class="field"><label>Sample rate</label><input class="input" type="number" value={form.audioSamplerate ?? ''} on:input={(e) => set('audioSamplerate', Number((e.currentTarget as HTMLInputElement).value) || null)} /></div>
    <div class="field"><label>Audio channels</label><input class="input" type="number" value={form.audioChannels ?? ''} on:input={(e) => set('audioChannels', Number((e.currentTarget as HTMLInputElement).value) || null)} /></div>
    <div class="field"><label>Max width</label><input class="input" type="number" value={form.maxWidth ?? ''} on:input={(e) => set('maxWidth', Number((e.currentTarget as HTMLInputElement).value) || null)} /></div>
    <div class="field"><label>Max height</label><input class="input" type="number" value={form.maxHeight ?? ''} on:input={(e) => set('maxHeight', Number((e.currentTarget as HTMLInputElement).value) || null)} /></div>
  </div>
  <div class="dialog-actions"><button class="btn" on:click={onClose}>Cancel</button><button class="btn primary" disabled={busy || !form.name || !form.container || !form.outputExt} on:click={save}>{busy ? 'Saving…' : 'Save preset'}</button></div>
</ModalFrame>
