<script lang="ts">
  import { clampPercent } from '$lib/utils/format';

  export let percent = 0;
  export let segments = 12;

  $: completed = Math.floor((clampPercent(percent) / 100) * segments);
  $: active = Math.min(completed, segments - 1);
</script>

<div class="parts-grid" style={`--cols: ${segments}`}>
  {#each Array(segments) as _, i}
    <div
      class="part"
      class:done={i < completed}
      class:current={i === active && percent > 0 && percent < 100}
      class:pending={i > active}
    ></div>
  {/each}
</div>

<style>
  .parts-grid {
    display: grid;
    grid-template-columns: repeat(var(--cols, 12), 1fr);
    gap: 4px;
  }
  .part {
    aspect-ratio: 1;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.08);
    transition: background 0.3s ease, box-shadow 0.3s ease;
  }
  .part.done {
    background: linear-gradient(135deg, var(--purple), var(--purple-light));
    box-shadow: 0 0 8px rgba(124, 60, 255, 0.3);
  }
  .part.current {
    background: linear-gradient(135deg, var(--purple), var(--purple-light));
    box-shadow: 0 0 12px rgba(124, 60, 255, 0.5);
    animation: pulse-part 1.4s ease-in-out infinite;
  }
  .part.pending {
    background: rgba(255, 255, 255, 0.05);
  }
  @keyframes pulse-part {
    0%, 100% { opacity: 0.7; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.05); }
  }
</style>
