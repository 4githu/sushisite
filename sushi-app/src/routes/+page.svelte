<script lang="ts">
	import { page } from '$app/state';
	import OdiHome from './odi/+page.svelte';
</script>

{#if page.url.hostname === 'rehear.chobab.app'}
	<OdiHome />
{:else}
	<h1>Welcome to SvelteKit</h1>
	<p>Visit <a href="https://svelte.dev/docs/kit">svelte.dev/docs/kit</a> to read the documentation</p>
{/if}
