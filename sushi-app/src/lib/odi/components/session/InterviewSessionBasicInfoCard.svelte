<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";

	import CompanyInfoSection from "$lib/odi/components/session/InterviewCompanyInfoSection.svelte";
	import InterviewInfoSection from "$lib/odi/components/session/InterviewInfoSection.svelte";

	let {
		company = $bindable(""),
		department = $bindable(""),
		position = $bindable(""),
		jobDetail = $bindable(""),

		interviewTime = $bindable(30),
		interviewSituation = $bindable("one-to-one"),
		language = $bindable(""),
		interviewerCount = $bindable("1"),
		answerOrder = $bindable("first")
	}: {
		company?: string;
		department?: string;
		position?: string;
		jobDetail?: string;

		interviewTime?: number;
		interviewSituation?: string;
		language?: string;
		interviewerCount?: string;
		answerOrder?: string;
	} = $props();
</script>

<SurfaceCard padding="36px" minHeight="609px">
	<div class="basic-info-content">
		<CompanyInfoSection
			bind:company
			bind:department
			bind:position
			bind:jobDetail
		/>

		<InterviewInfoSection
			bind:interviewTime
			bind:interviewSituation
			bind:language
			bind:interviewerCount
			bind:answerOrder
		/>
	</div>
</SurfaceCard>

<style>
	.basic-info-content {
		display: flex;
		flex-direction: column;
		gap: var(--space-16);
	}
</style>