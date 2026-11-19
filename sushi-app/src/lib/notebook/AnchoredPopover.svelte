<script lang="ts">
	import { tick } from 'svelte';
	import type { Snippet } from 'svelte';
	let {
		anchor,
		open,
		onclose,
		children,
		width = 240
	}: {
		anchor: HTMLElement | null;
		open: boolean;
		onclose: () => void;
		children: Snippet;
		width?: number;
	} = $props();
	let element = $state<HTMLDivElement>();
	$effect(() => {
		const node = element,
			a = anchor,
			show = open;
		if (!node || !a) return;
		const place = () => {
			const r = a.getBoundingClientRect();
			node.style.left = Math.max(8, Math.min(innerWidth - width - 8, r.left)) + 'px';
			node.style.top = Math.min(innerHeight - node.offsetHeight - 8, r.bottom + 6) + 'px';
		};
		if (show) {
			if (!node.matches(':popover-open')) node.showPopover();
			place();
			void tick().then(place);
		} else if (node.matches(':popover-open')) node.hidePopover();
		window.addEventListener('resize', place);
		window.addEventListener('scroll', place, true);
		return () => {
			window.removeEventListener('resize', place);
			window.removeEventListener('scroll', place, true);
		};
	});
</script>

<div
	bind:this={element}
	popover="auto"
	class="notebook-popover"
	style:width={width + 'px'}
	ontoggle={(e) => {
		if (e.newState === 'closed' && open) onclose();
	}}
>
	{@render children()}
</div>

<style>
	.notebook-popover {
		position: fixed;
		inset: auto;
		margin: 0;
		padding: 0;
		border: 0;
		border-radius: 6px;
		background: transparent;
		max-width: calc(100vw - 16px);
		max-height: calc(100dvh - 16px);
		overflow: auto;
		box-shadow: 0 8px 24px #24252918;
	}
</style>
