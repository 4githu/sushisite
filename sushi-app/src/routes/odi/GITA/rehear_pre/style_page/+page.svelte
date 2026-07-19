<!-- +page.svelte -->

<script lang="ts">
	import BrandSection from "./BrandSection.svelte";
	import SystemColorSection from "./SystemColorSection.svelte";
	import TypographySection from "./TypographySection.svelte";
	import RadiusSection from "./RadiusSection.svelte";
	import ButtonStateSection from "./ButtonStateSection.svelte";
	import ShadowSection from "./ShadowSection.svelte";
</script>

<svelte:head>
	<title>Re:hear Design System</title>
</svelte:head>

<div class="page">

	<BrandSection />

	<SystemColorSection />

	<TypographySection />

	<RadiusSection />

	<ButtonStateSection />

	<ShadowSection />

</div>

<style>

.page{

	max-width:3200px;

	margin:0 auto;

	padding:48px;

	display:flex;

	flex-direction:column;

	gap:96px;

}

</style>