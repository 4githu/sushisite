<script lang="ts">
  const { label = '', value = '', placeholder = '입력하세요', state = 'default', helper = '' } = $props();
  const id = `input-${Math.random().toString(36).slice(2, 9)}`;
</script>

<div class="rehear-input-field {state}">
  {#if label}
    <label class="rehear-input-label" for={id}>{label}</label>
  {/if}
  <input
    class="rehear-input"
    type="text"
    value={value}
    placeholder={placeholder}
    disabled={state === 'disabled'}
  />
  {#if helper}
    <div class="rehear-input-helper">{helper}</div>
  {/if}
</div>
