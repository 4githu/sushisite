<!-- src/lib/odi/components/login/OdiJoinGoalStep.svelte -->
<script lang="ts">
 import { locale as siteLocale, copy as tr } from "$lib/odi/i18n";
	import OdiJoinOptionCard from "$lib/odi/components/login/OdiJoinOptionCard.svelte";

	import {
		podium as Podium,
		voice as VoiceSelection,
		authCheck as Check,
		figmaDescription as Article,
		authVisibility as Visibility,
		figmaReportCalendar as Calendar
	} from "$lib/odi/icons";

	export type TrainingType = "presentation" | "interview" | "both";
	export type FocusArea = "content" | "delivery";
	export type PracticeFrequency = 2 | 3 | 5;

	let {
		trainingType = $bindable("both" as TrainingType),
		focusArea = $bindable("delivery" as FocusArea),
		practiceFrequency = $bindable(3 as PracticeFrequency)
	}: {
		trainingType?: TrainingType;
		focusArea?: FocusArea;
		practiceFrequency?: PracticeFrequency;
	} = $props();

	const trainingOptions = $derived([
		{
			value: "presentation" as const,
			title: tr($siteLocale, "발표 연습"),
			description: tr($siteLocale, "학술 발표, 세미나, 수업 발표 등"),
			icon: Podium
		},
		{
			value: "interview" as const,
			title: tr($siteLocale, "면접 연습"),
			description: tr($siteLocale, "취업, 입시, 다대다 면접 등"),
			icon: VoiceSelection
		},
		{
			value: "both" as const,
			title: tr($siteLocale, "둘 다"),
			description: "",
			icon: Check
		}
	]);

	const focusOptions = $derived([
		{
			value: "content" as const,
			title: tr($siteLocale, "내용 구성"),
			description: tr($siteLocale, "핵심 메시지, 구조와 흐름, 근거 활용 등"),
			icon: Article
		},
		{
			value: "delivery" as const,
			title: tr($siteLocale, "전달 방식"),
			description: tr($siteLocale, "시선 처리, 발화 속도, 발음 정확도 등"),
			icon: Visibility
		}
	]);

	const frequencyOptions = $derived([
		{ value: 2 as const, title: tr($siteLocale, "주 2회") },
		{ value: 3 as const, title: tr($siteLocale, "주 3회") },
		{ value: 5 as const, title: tr($siteLocale, "주 5회") }
	]);
</script>

<div class="goal-step">
	<section class="goal-section">
		<h2>{tr($siteLocale, "주로 어떤 상황을 연습하시나요?")}</h2>

		<div class="three-grid">
			{#each trainingOptions as option (option.value)}
				<OdiJoinOptionCard
					title={option.title}
					description={option.description}
					icon={option.icon}
					selected={trainingType === option.value}
					onclick={() => (trainingType = option.value)}
				/>
			{/each}
		</div>
	</section>

	<section class="goal-section">
		<h2>{tr($siteLocale, "가장 먼저 개선하고 싶은 부분은 무엇인가요?")}</h2>

		<div class="two-grid">
			{#each focusOptions as option (option.value)}
				<OdiJoinOptionCard
					title={option.title}
					description={option.description}
					icon={option.icon}
					selected={focusArea === option.value}
					onclick={() => (focusArea = option.value)}
					wide
				/>
			{/each}
		</div>
	</section>

	<section class="goal-section">
		<h2>{tr($siteLocale, "얼마나 자주 연습할까요?")}</h2>

		<div class="three-grid">
			{#each frequencyOptions as option (option.value)}
				<button
					type="button"
					class="frequency-card clickable"
					class:selected={practiceFrequency === option.value}
					onclick={() => (practiceFrequency = option.value)}
				>
					<img src={Calendar} alt="" />
					<span>{option.title}</span>
				</button>
			{/each}
		</div>
	</section>
</div>

<style>
	.goal-step {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 60px;
	}

	.goal-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.goal-section h2 {
		color: var(--brand-black);
		font-size: 26px;
		font-weight: var(--font-bold);
		line-height: 135%;
	}

	.three-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--space-4);
	}

	.two-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-4);
	}

	.frequency-card {
		height: 80px;
		padding: 11px 20px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-secondary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.frequency-card.selected {
		border: 2px solid var(--primary);
		background: rgba(0, 51, 255, 0.05);
		color: var(--brand-black);
	}

	.frequency-card img {
		width: 22px;
		height: 22px;
		object-fit: contain;
	}

	@media (max-width: 1200px) {
		.three-grid,
		.two-grid {
			grid-template-columns: 1fr;
		}
	}
</style>