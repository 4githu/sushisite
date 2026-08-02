<script lang="ts">
	import { browser } from '$app/environment';

	let {
		kind,
		value,
		onselect,
		onclose
	}: {
		kind: 'text' | 'highlight';
		value?: string;
		onselect: (color?: string) => void;
		onclose: () => void;
	} = $props();

	const palette = $derived(
		kind === 'text'
			? ['#111827', '#dc2626', '#ea580c', '#16a34a', '#2563eb', '#7c3aed']
			: ['#fef08a', '#fed7aa', '#fecaca', '#bbf7d0', '#bfdbfe', '#ddd6fe']
	);
	const storageKey = $derived(`textediter-recent-${kind}`);
	let recent = $state<string[]>([]);
	let custom = $derived(value ?? palette[0]);

	$effect(() => {
		if (!browser) return;
		try {
			recent = JSON.parse(localStorage.getItem(storageKey) ?? '[]')
				.filter((item: unknown) => typeof item === 'string')
				.slice(0, 6);
		} catch {
			recent = [];
		}
	});

	function choose(color?: string) {
		if (color && browser) {
			recent = [color, ...recent.filter((item) => item !== color)].slice(0, 6);
			localStorage.setItem(storageKey, JSON.stringify(recent));
		}
		onselect(color);
	}

	function keydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			event.preventDefault();
			onclose();
		}
		if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
			const buttons = Array.from(
				(event.currentTarget as HTMLElement).querySelectorAll<HTMLButtonElement>('.swatch')
			);
			const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
			buttons[
				(index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length
			]?.focus();
		}
	}
</script>

<div
	class="color-popover"
	role="dialog"
	tabindex="-1"
	aria-label={kind === 'text' ? '글자색 선택' : '형광펜 색상 선택'}
	onkeydown={keydown}
>
	<p>기본 색상</p>
	<div class="swatches">
		{#each palette as color (color)}
			<button
				class="swatch"
				style:--swatch={color}
				aria-label={`${color} 선택`}
				aria-pressed={value === color}
				onclick={() => choose(color)}>{value === color ? '✓' : ''}</button
			>
		{/each}
	</div>
	{#if recent.length}
		<p>최근 사용</p>
		<div class="swatches">
			{#each recent as color (color)}
				<button
					class="swatch"
					style:--swatch={color}
					aria-label={`최근 색상 ${color}`}
					aria-pressed={value === color}
					onclick={() => choose(color)}>{value === color ? '✓' : ''}</button
				>
			{/each}
		</div>
	{/if}
	<label>사용자 지정 <input type="color" bind:value={custom} aria-label="사용자 지정 색상" /></label
	>
	<div class="popover-actions">
		<button onclick={() => choose(custom)}>적용</button><button onclick={() => choose(undefined)}
			>색상 제거</button
		>
	</div>
</div>
