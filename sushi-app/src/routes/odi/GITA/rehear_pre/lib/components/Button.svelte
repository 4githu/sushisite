<script lang="ts">
  const { label = 'Button', variant = 'primary', size = 'md', disabled = false } = $props();
</script>

<button
  type="button"
  class="btn {variant === 'secondary' ? 'btn-secondary' : variant === 'ghost' ? 'btn-ghost' : ''} {size === 'lg' ? 'btn-lg' : size === 'sm' ? 'btn-sm' : ''}"
  disabled={disabled}
>
  {label}
</button>
