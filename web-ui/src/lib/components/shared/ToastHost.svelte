<script lang="ts">
  import { toast } from '$lib/state/toast-state';
</script>

{#if $toast}
  <div class="toast">{$toast}</div>
{/if}
