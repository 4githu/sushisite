<script lang="ts">
 import { locale as siteLocale, copy as tr } from "$lib/odi/i18n";
 import { locale, copy } from "$lib/odi/i18n";
	import SessionSlider from "$lib/odi/components/session/SessionSlider.svelte";
	import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";
	import SessionSelect from "$lib/odi/components/session/SessionSelect.svelte";

	let {
		interviewTime = $bindable(0),
		interviewSituation = $bindable(""),
		language = $bindable(""),
		interviewerCount = $bindable("0"),
		answerOrder = $bindable("")
	}: {
		interviewTime?: number;
		interviewSituation?: string;
		language?: string;
		interviewerCount?: string;
		answerOrder?: string;
	} = $props();

	const timeTicks = $derived([
		{ value: 10, label: tr($siteLocale, "10분") },
		{ value: 20, label: tr($siteLocale, "20분") },
		{ value: 30, label: tr($siteLocale, "30분") },
		{ value: 40, label: tr($siteLocale, "40분") },
		{ value: 50, label: tr($siteLocale, "50분") },
		{ value: 60, label: tr($siteLocale, "60분") }
	]);

	const situationItems = $derived([
		{ label: tr($siteLocale, "일대일"), value: "one-to-one" },
		{ label: tr($siteLocale, "일대다"), value: "one-to-many" },
		{ label: tr($siteLocale, "다대다"), value: "many-to-many" }
	]);

	const languageItems = $derived([
		{ label: tr($siteLocale, "한국어"), value: "ko" },
		{ label: tr($siteLocale, "영어"), value: "en" }
	]);

	const interviewerCountItems = $derived([
		{ label: tr($siteLocale, "1명"), value: "1" },
		{ label: tr($siteLocale, "2명"), value: "2" },
		{ label: tr($siteLocale, "3명"), value: "3" }
	]);

	const answerOrderItems = $derived([
		{ label: tr($siteLocale, "순서대로"), value: "sequential" },
		{ label: tr($siteLocale, "자유 순서"), value: "free" },
		{ label: tr($siteLocale, "면접관 지정"), value: "interviewer-led" }
	]);
</script>

<section class="interview-section">
	<h2 class="text-title-middle">
		{tr($siteLocale, "면접 환경 정보")}
	</h2>

	<div class="environment-grid">
		<div class="field slider-field">
			<p class="text-body-active">
				{tr($siteLocale, "면접 시간")}
			</p>

			<div class="slider-wrap">
				<SessionSlider
					mode="node"
					min={10}
					max={60}
					step={10}
					majorTicks={timeTicks}
					bind:value={interviewTime}
				/>
			</div>
		</div>

		<div class="field situation-field">
			<p class="text-body-active">
				{tr($siteLocale, "면접 상황")}
			</p>

			<SegmentedControl
                items={situationItems}
                bind:selected={interviewSituation}
            />
		</div>

		<div class="field language-field">
			<p class="text-body-active">
				{copy($locale, "사용 언어")}
			</p>

			<SessionSelect
				width="343px"
				placeholder={tr($siteLocale, "선택해주세요")}
				items={languageItems}
				bind:value={language}
			/>
		</div>

		<div class="field interviewer-field">
			<p class="text-body-active">
				{tr($siteLocale, "면접관 수")}
			</p>

			<SessionSelect
				width="343px"
				placeholder={tr($siteLocale, "선택해주세요")}
				items={interviewerCountItems}
				bind:value={interviewerCount}
			/>
		</div>

		<div class="field order-field">
			<p class="text-body-active">
				{tr($siteLocale, "답변 순서")}
			</p>

			<SessionSelect
				width="343px"
				placeholder={tr($siteLocale, "선택해주세요")}
				items={answerOrderItems}
				bind:value={answerOrder}
			/>
		</div>
	</div>
</section>

<style>
	.interview-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
	}

	.environment-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		column-gap: var(--space-10);
		row-gap: var(--space-8);
		align-items: start;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.slider-field {
		grid-column: 1;
		grid-row: 1;
		width: 100%;
	}

	.situation-field {
		grid-column: 2;
		grid-row: 1;
		width: 100%;
	}

	.language-field {
		grid-column: 1;
		grid-row: 2;
		width: 100%;
	}

	.interviewer-field {
		grid-column: 2;
		grid-row: 2;
		width: 100%;
	}

	.order-field {
		grid-column: 1;
		grid-row: 3;
		width: 100%;
	}

	.slider-wrap {
		width: 100%;
	}

	@media (max-width: 900px) {
		.environment-grid {
			grid-template-columns: 1fr;
		}

		.slider-field,
		.situation-field,
		.language-field,
		.interviewer-field,
		.order-field {
			grid-column: 1;
			grid-row: auto;
		}
	}
</style>
