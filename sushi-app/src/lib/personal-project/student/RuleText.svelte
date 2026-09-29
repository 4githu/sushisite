<script lang="ts">
	let { text }: { text: string } = $props();
	// Limited inline Markdown. Text remains escaped; no raw HTML is rendered.
	const parts = $derived(text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g));
</script>

{#each parts as part}
	{#if part.startsWith('**') && part.endsWith('**')}<strong>{part.slice(2, -2)}</strong>
	{:else if part.startsWith('`') && part.endsWith('`')}<code>{part.slice(1, -1)}</code>
	{:else if /^\[[^\]]+\]\(https?:\/\/[^\s)]+\)$/.test(part)}{@const split = part.indexOf('](')}<a
			href={part.slice(split + 2, -1)}
			target="_blank"
			rel="noopener noreferrer">{part.slice(1, split)}</a
		>
	{:else}{part}{/if}
{/each}

<style>
	code {
		font-size: 0.9em;
		background: #eef0f3;
		border-radius: 4px;
		padding: 1px 4px;
	}
	a {
		overflow-wrap: anywhere;
	}
</style>
