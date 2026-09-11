<script lang="ts">
	import { page } from '$app/state';
	import { locales, localizeHref } from '$lib/paraglide/runtime';
	import './layout.css';
	import rehearFavicon from '$lib/odi/icons/logoimage.png';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" type="image/png" href={rehearFavicon} />
</svelte:head>
{@render children()}

<div style="display:none">
	{#each locales as locale (locale)}
		<a href={localizeHref(page.url.pathname, { locale })}>{locale}</a>
	{/each}
</div>
