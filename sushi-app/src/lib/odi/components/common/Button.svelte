<script lang="ts">
	import { goto } from '$app/navigation';
	import type { Snippet } from 'svelte';

	type Variant = 'primary' | 'secondary' | 'soft' | 'outline' | 'ghost';

	type Size = 'sm' | 'md' | 'lg';

	let {
		variant = 'primary',
		size = 'md',

		width,
		block = false,

		href,

		leadingIcon,
		trailingIcon,

		iconSize = 24,

		disabled = false,

		children,

		onclick
	}: {
		variant?: Variant;
		size?: Size;

		width?: string;
		block?: boolean;

		href?: string;

		leadingIcon?: string;
		trailingIcon?: string;

		iconSize?: number;

		disabled?: boolean;

		children?: Snippet;

		onclick?: (event: MouseEvent) => void;
	} = $props();

	async function handleClick(event: MouseEvent) {
		if (disabled) return;

		if (href) {
			await goto(href);
			return;
		}

		onclick?.(event);
	}
</script>

<button
	type="button"
	class={['button', 'clickable', variant, size, block && 'block']}
	style:width
	{disabled}
	onclick={handleClick}
>
	{#if leadingIcon}
		<img
			class="icon"
			src={leadingIcon}
			alt=""
			style={`width:${iconSize}px;height:${iconSize}px;`}
		/>
	{/if}

	<span class={[size === 'lg' ? 'text-button-start' : 'text-button']}>
		{@render children?.()}
	</span>

	{#if trailingIcon}
		<img
			class="icon"
			src={trailingIcon}
			alt=""
			style={`width:${iconSize}px;height:${iconSize}px;`}
		/>
	{/if}
</button>

<style>
	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;

		width: fit-content;
		max-width: 100%;
		min-width: 0;

		flex-shrink: 0;

		gap: var(--space-2);

		padding-inline: var(--space-4);

		border-radius: var(--radius-sm);

		white-space: normal;
		text-align: center;
	}

	.block {
		width: 100%;
	}

	.sm {
		min-height: 42px;
		padding-block: 8px;
	}

	.md {
		min-height: 50px;
		padding-block: 10px;
	}

	.lg {
		min-height: 63px;
		padding-block: 12px;

		padding-inline: var(--space-5);
	}

	.primary {
		background: var(--primary);

		color: var(--text-on-primary);
	}

	.primary:hover:not(:disabled) {
		background: var(--primary-hover);
	}

	.secondary {
		background: var(--surface);

		color: var(--primary);

		border: 1px solid var(--cool-grey-light-active);
	}

	.secondary:hover:not(:disabled) {
		border-color: var(--primary);
	}

	.soft {
		background: rgb(from var(--primary) r g b / 10%);

		color: var(--primary);
	}

	.soft:hover:not(:disabled) {
		background: rgb(from var(--primary) r g b / 15%);
	}

	.outline {
		background: transparent;

		color: var(--primary);

		border: 1px solid var(--primary);
	}

	.outline:hover:not(:disabled) {
		background: var(--blue-light);
	}

	.ghost {
		background: transparent;

		color: var(--text-primary);
	}

	.button:disabled {
		background: var(--cool-grey-light-active);

		color: var(--text-disabled);

		border: none;
	}

	.icon {
		display: block;

		flex-shrink: 0;
	}
</style>
