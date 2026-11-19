<script lang="ts">
 import { locale as siteLocale, copy as tr } from "$lib/odi/i18n";
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
		{tr($siteLocale, "지원 회사 정보")}
	</h2>

	<div class="input-row">
		<TextInput
			label={tr($siteLocale, "기업명")}
			required
			width="342.5px"
			placeholder={tr($siteLocale, "입력해주세요")}
			bind:value={company}
		/>

		<TextInput
			label={tr($siteLocale, "지원 부서")}
			required
			width="342.5px"
			placeholder={tr($siteLocale, "입력해주세요")}
			bind:value={department}
		/>

		<TextInput
			label={tr($siteLocale, "지원 포지션")}
			required
			width="342.5px"
			placeholder={tr($siteLocale, "입력해주세요")}
			bind:value={position}
		/>

		<TextInput
			label={tr($siteLocale, "상세 직무")}
			width="342.5px"
			placeholder={tr($siteLocale, "입력해주세요")}
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