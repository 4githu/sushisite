<script lang="ts">
	let {
		title,
		description,
		eyebrow = 'Session Setup'
	}: {
		title: string;
		description: string;
		eyebrow?: string;
	} = $props();
</script>

<header class="rehear-page-header">
	<p>{eyebrow}</p>
	<h1>{title}</h1>
	<span>{description}</span>
</header>
