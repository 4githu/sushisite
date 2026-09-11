<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		children,
		padding = '36px',
		minHeight = '609px'
	}: {
		children: Snippet;
		padding?: string;
		minHeight?: string;
	} = $props();

	const styleVars = $derived(`--card-padding:${padding}; --card-min-height:${minHeight};`);
</script>

<section class="surface-card" style={styleVars}>
	<div class="surface-card-body">
		{@render children()}
	</div>
</section>

<style>
	.surface-card {
		width: 100%;
		height: 100%;

		min-height: min(var(--card-min-height), max(380px, calc(100dvh - 330px)));

		background: var(--surface);

		border-radius: var(--radius-md);

		box-shadow: var(--shadow-sm);

		overflow: hidden;
	}

	.surface-card-body {
		width: 100%;
		height: 100%;

		padding: var(--card-padding);

		display: flex;
		flex-direction: column;
	}

	@media (max-width: 640px) {
		.surface-card {
			min-height: auto;
		}

		.surface-card-body {
			padding: 20px;
		}
	}

	@media (max-height: 820px) and (min-width: 641px) {
		.surface-card-body {
			padding: 28px;
		}
	}
</style>
