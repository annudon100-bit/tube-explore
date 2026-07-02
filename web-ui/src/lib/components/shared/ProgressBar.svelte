<script lang="ts">
  import { clampPercent } from '$lib/utils/format';
  export let value = 0;
</script>

<div class="progress-track" title={`${clampPercent(value)}%`}>
  <div class="progress-bar" style={`width: ${clampPercent(value)}%`}></div>
</div>
