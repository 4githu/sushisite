<script lang="ts">
  import Icon from './Icon.svelte';
  const { label = '', value = '', placeholder = '선택하세요', disabled = false, icon = 'Property 1=chevron_down, Size=20' } = $props();
</script>

<div class="rehear-select {disabled ? 'disabled' : ''}">
  {#if label}
    <div class="rehear-select-label">{label}</div>
  {/if}
  <button class="rehear-select-control" disabled={disabled}>
    <span>{value || placeholder}</span>
    <span class="rehear-select-icon">
      <Icon name={icon} size={20} alt="{label} icon" />
    </span>
  </button>
</div>
