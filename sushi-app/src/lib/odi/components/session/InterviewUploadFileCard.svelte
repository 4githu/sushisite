<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import UploadSection from "$lib/odi/components/session/UploadSection.svelte";

	let {
		resumeFile = $bindable(null),
		portfolioFile = $bindable(null)
	}: {
		resumeFile?: File | null;
		portfolioFile?: File | null;
	} = $props();
</script>

<SurfaceCard padding="43px 36px" minHeight="609px">
	<div class="upload-card-content">
		<UploadSection
			title="이력서 / 자기소개서 PDF"
			required
			accept=".pdf"
			maxSizeMB={300}
			bind:file={resumeFile}
		/>

		<UploadSection
			title="포트폴리오 PDF"
			accept=".pdf"
			maxSizeMB={300}
			bind:file={portfolioFile}
		/>
	</div>
</SurfaceCard>

<style>
	.upload-card-content {
		display: flex;
		flex-direction: column;
		gap: 76px;
	}
</style>