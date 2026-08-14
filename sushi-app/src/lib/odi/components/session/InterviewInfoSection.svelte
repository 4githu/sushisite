<script lang="ts">
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

	const timeTicks = [
		{ value: 10, label: "10분" },
		{ value: 20, label: "20분" },
		{ value: 30, label: "30분" },
		{ value: 40, label: "40분" },
		{ value: 50, label: "50분" },
		{ value: 60, label: "60분" }
	];

	const situationItems = [
		{ label: "일대일", value: "one-to-one" },
		{ label: "일대다", value: "one-to-many" },
		{ label: "다대다", value: "many-to-many" }
	];

	const languageItems = [
		{ label: "한국어", value: "ko" },
		{ label: "영어", value: "en" }
	];

	const interviewerCountItems = [
		{ label: "1명", value: "1" },
		{ label: "2명", value: "2" },
		{ label: "3명", value: "3" }
	];

	const answerOrderItems = [
		{ label: "순서대로", value: "sequential" },
		{ label: "자유 순서", value: "free" },
		{ label: "면접관 지정", value: "interviewer-led" }
	];
</script>

<section class="interview-section">
	<h2 class="text-title-middle">
		면접 환경 정보
	</h2>

	<div class="environment-grid">
		<div class="field slider-field">
			<p class="text-body-active">
				면접 시간
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
				면접 상황
			</p>

			<SegmentedControl
                items={situationItems}
                bind:selected={interviewSituation}
            />
		</div>

		<div class="field language-field">
			<p class="text-body-active">
				사용 언어
			</p>

			<SessionSelect
				width="343px"
				placeholder="선택해주세요"
				items={languageItems}
				bind:value={language}
			/>
		</div>

		<div class="field interviewer-field">
			<p class="text-body-active">
				면접관 수
			</p>

			<SessionSelect
				width="343px"
				placeholder="선택해주세요"
				items={interviewerCountItems}
				bind:value={interviewerCount}
			/>
		</div>

		<div class="field order-field">
			<p class="text-body-active">
				답변 순서
			</p>

			<SessionSelect
				width="343px"
				placeholder="선택해주세요"
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
