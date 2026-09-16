<script lang="ts">
	import { onMount } from 'svelte';
	import { template } from '$lib/odi/stores';
	import { goto } from '$app/navigation';

	import Button from '$lib/odi/components/common/Button.svelte';
	import ProgressStepper from '$lib/odi/components/session/ProgressStepper.svelte';
	import InterviewerSettingCard from '$lib/odi/components/session/InterviewAISettingCard.svelte';
	import TipCard from '$lib/odi/components/session/TipCard.svelte';

	import { Check } from '$lib/odi/icons';

	type InterviewerPersona = 'hr' | 'practical' | 'executive' | 'mixed';

	type InterviewStyle = 'friendly' | 'neutral' | 'critical' | 'pressure';

	const steps = [
		{ label: '면접 기본 정보' },
		{ label: '자료 업로드' },
		{ label: 'AI 면접관 설정' },
		{ label: '세션 확인' }
	];

	let interviewerPersona = $state<InterviewerPersona>('hr');
	let interviewStyle = $state<InterviewStyle>('friendly');

	const tips = [
		{
			icon: './puplecheck.svg',
			description: '페르소나에 따라 질문의 영역, 난이도가 조절됩니다.'
		},
		{
			icon: Check,
			description: '답변에 맞춰 후속 질문을 제공합니다.'
		},
		{
			icon: Check,
			description: '중립적인 태도로 균형 잡힌 피드백을 제공합니다.'
		},
		{
			icon: Check,
			description: '직무 중심 질문으로 핵심 역량을 집중 평가합니다.'
		},
		{
			icon: Check,
			description:
				'스타일에 따라 압박 및 분위기를 조성하여 집중도를 높이고 유연한 대처 능력을 훈련할 수 있습니다.'
		}
	];

	function previousStep() {
		goto('/odi/session/interview/upload');
	}

	onMount(() => {
		const draft = template.get();
		if (draft?.type === 'interview') {
			interviewerPersona = draft.audience.interviewer_persona as InterviewerPersona;
			interviewStyle = draft.audience.interview_style as InterviewStyle;
		}
	});
	function nextStep() {
		template.patchAudience({
			interviewer_persona: interviewerPersona,
			interview_style: interviewStyle
		});
		void goto('/odi/session/interview/confirm');
	}
</script>

<section class="session-page">
	<header class="page-header">
		<p class="text-caption-main eyebrow">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">AI 면접관 설정</h1>

			<p class="text-caption-main description">
				면접관의 역할과 질문 스타일을 선택해 실제 면접과 비슷한 환경을 구성해요.
			</p>
		</div>
	</header>

	<ProgressStepper {steps} currentStep={2} />

	<div class="content-row">
		<InterviewerSettingCard bind:interviewerPersona bind:interviewStyle />

		<TipCard
			title="면접관 선택 TIP"
			description="AI 면접관은 실시간으로 지원자와 소통합니다."
			{tips}
		/>
	</div>

	<div class="actions">
		<Button variant="secondary" width="212px" onclick={previousStep}>이전 단계</Button>

		<Button width="212px" onclick={nextStep}>다음 단계</Button>
	</div>
</section>

<style>
	.session-page {
		width: 100%;
		min-height: 100vh;
		padding: var(--odi-page-padding-top) var(--odi-page-padding-inline)
			var(--odi-page-padding-bottom);

		display: flex;
		flex-direction: column;

		gap: var(--space-6);
		background: var(--surface);
	}

	.page-header {
		display: flex;
		flex-direction: column;

		gap: var(--space-6);
	}

	.eyebrow {
		color: var(--primary);
	}

	.title-group {
		display: flex;
		flex-direction: column;

		gap: var(--space-2);
	}

	.description {
		color: var(--text-secondary);
	}

	.content-row {
		display: grid;

		grid-template-columns: minmax(0, 1fr) 432px;

		align-items: stretch;

		gap: var(--space-3);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		align-items: center;

		gap: var(--space-4);
	}

	@media (max-width: 1180px) {
		.content-row {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.session-page {
			padding: 24px 16px 32px;
		}
		.actions {
			align-items: stretch;
			flex-direction: column-reverse;
		}
		.actions :global(.button) {
			width: 100% !important;
		}
	}
</style>
