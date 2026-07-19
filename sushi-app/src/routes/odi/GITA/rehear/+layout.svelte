<script lang="ts">
	import Sidebar from './_components/Sidebar.svelte';
	import './rehear.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>Re:hear Session Setup</title>
</svelte:head>

<div class="rehear-app">
	<Sidebar />
	<main class="rehear-main">
		{@render children()}
	</main>
</div>
