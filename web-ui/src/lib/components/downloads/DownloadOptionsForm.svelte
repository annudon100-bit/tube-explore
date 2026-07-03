<script lang="ts">
  import type { AudioFormat, DownloadPlaylistRequest, DownloadVideoRequest, ProfileResponse, QualityMode } from '$lib/api/types';
  import QualityFields from './QualityFields.svelte';

  export let value: Partial<DownloadVideoRequest & DownloadPlaylistRequest> = {};
  export let profiles: ProfileResponse[] = [];
  export let isPlaylist = false;
  export let onChange: (value: Partial<DownloadVideoRequest & DownloadPlaylistRequest>) => void = () => {};

  function set<K extends keyof (DownloadVideoRequest & DownloadPlaylistRequest)>(key: K, v: (DownloadVideoRequest & DownloadPlaylistRequest)[K]) {
    value = { ...value, [key]: v };
    onChange(value);
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

<div class="form-grid">
  <div class="field full">
    <label>{isPlaylist ? 'Playlist URL' : 'Video URL'}</label>
    <input class="input" placeholder="https://..." value={value.url || ''} on:input={(e) => set('url', (e.currentTarget as HTMLInputElement).value)} />
  </div>

  <div class="field">
    <label>Profile</label>
    <select class="select" value={value.profileId || ''} on:change={(e) => set('profileId', (e.currentTarget as HTMLSelectElement).value || null)}>
      <option value="">No profile</option>
      {#each profiles as profile}
        <option value={profile.name}>{profile.label || profile.name}</option>
      {/each}
    </select>
  </div>

  {#if isPlaylist}
    <div class="field">
      <label>Playlist range</label>
      <input class="input" placeholder="1 or 1-5" value={value.range || ''} on:input={(e) => set('range', (e.currentTarget as HTMLInputElement).value || null)} />
    </div>
  {/if}

  <label class="checkbox-line">
    <input type="checkbox" checked={!!value.audioOnly} on:change={() => { const v = !value.audioOnly; set('audioOnly', v); if (!v) { set('audioFormat', null); set('audioQuality', null); } }} />
    Audio only
  </label>

  {#if value.audioOnly}
    <div class="field">
      <label>Audio format</label>
      <select class="select" value={value.audioFormat || 'mp3'} on:change={(e) => set('audioFormat', (e.currentTarget as HTMLSelectElement).value as AudioFormat || null)}>
        {#each audioFormatOptions as opt}
          <option value={opt.value}>{opt.label}</option>
        {/each}
      </select>
    </div>

    <div class="field">
      <label>Audio quality</label>
      <input class="input" placeholder="e.g. 192K, 320K" value={value.audioQuality || '192K'} on:input={(e) => set('audioQuality', (e.currentTarget as HTMLInputElement).value || null)} />
      <span class="help">Bitrate: 128K, 192K, 320K, etc.</span>
    </div>
  {:else}
    <div class="field">
      <label>Remux to container</label>
      <select class="select" value={value.remuxTo || ''} on:change={(e) => set('remuxTo', (e.currentTarget as HTMLSelectElement).value || null)}>
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

  <div class="field">
    <label>Download format</label>
    <input class="input" placeholder="yt-dlp format override" value={value.downloadFormat || ''} on:input={(e) => set('downloadFormat', (e.currentTarget as HTMLInputElement).value || null)} />
  </div>

  <QualityFields mode={(value.downloadQualityMode || '') as QualityMode | ''} value={value.downloadQualityValue ?? null} onChange={(mode, qualityValue) => { value = { ...value, downloadQualityMode: mode || null, downloadQualityValue: qualityValue }; onChange(value); }} />

  <div class="field">
    <label>Output subdirectory</label>
    <input class="input" placeholder="optional" value={value.outputDir || ''} on:input={(e) => set('outputDir', (e.currentTarget as HTMLInputElement).value || null)} />
  </div>

  <div class="field">
    <label>Absolute path override</label>
    <input class="input" placeholder="optional" value={value.downloadPathOverride || ''} on:input={(e) => set('downloadPathOverride', (e.currentTarget as HTMLInputElement).value || null)} />
    <span class="help">Avoid protected system paths such as /etc, /usr, /var, /root.</span>
  </div>

  <label class="checkbox-line"><input type="checkbox" checked={value.embedMetadata !== false} on:change={(e) => set('embedMetadata', (e.currentTarget as HTMLInputElement).checked)} /> Embed metadata</label>
  <label class="checkbox-line"><input type="checkbox" checked={value.embedThumbnail !== false} on:change={(e) => set('embedThumbnail', (e.currentTarget as HTMLInputElement).checked)} /> Embed thumbnail</label>
  <label class="checkbox-line"><input type="checkbox" checked={!!value.subtitles} on:change={(e) => set('subtitles', (e.currentTarget as HTMLInputElement).checked)} /> Download subtitles</label>

  <div class="field full">
    <label>Subtitle languages</label>
    <input class="input" placeholder="en,hi or all" value={value.subtitleLangs || ''} on:input={(e) => set('subtitleLangs', (e.currentTarget as HTMLInputElement).value || null)} />
  </div>
</div>
