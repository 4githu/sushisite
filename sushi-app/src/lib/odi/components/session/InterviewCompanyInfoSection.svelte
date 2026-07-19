<script lang="ts">
	import TextInput from "$lib/odi/components/common/TextInput.svelte";

	let {
		company = $bindable(""),
		department = $bindable(""),
		position = $bindable(""),
		jobDetail = $bindable("")
	}: {
		company?: string;
		department?: string;
		position?: string;
		jobDetail?: string;
	} = $props();
</script>

<section class="company-section">
	<h2 class="text-title-middle">
		지원 회사 정보
	</h2>

	<div class="input-row">
		<TextInput
			label="기업명"
			required
			width="342.5px"
			placeholder="입력해주세요"
			bind:value={company}
		/>

		<TextInput
			label="지원 부서"
			required
			width="342.5px"
			placeholder="입력해주세요"
			bind:value={department}
		/>

		<TextInput
			label="지원 포지션"
			required
			width="342.5px"
			placeholder="입력해주세요"
			bind:value={position}
		/>

		<TextInput
			label="상세 직무"
			width="342.5px"
			placeholder="입력해주세요"
			bind:value={jobDetail}
		/>
	</div>
</section>

<style>
	.company-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
	}

	.input-row {
		display: flex;
		align-items: flex-start;
		gap: var(--space-10);
	}
</style>