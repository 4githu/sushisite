<script lang="ts">
  const { steps = [], current = 0 } = $props();
</script>

<div class="rehear-progress-stepper">
  {#each steps as step, index}
    <div class="rehear-step {index < current ? 'done' : index === current ? 'active' : ''}">
      <div class="rehear-step-circle">{index < current ? '✓' : index + 1}</div>
      <div class="rehear-step-label">{step}</div>
    </div>
  {/each}
</div>
