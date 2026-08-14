<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import Button from "$lib/odi/components/common/Button.svelte";
	import { template, type InterviewTemplate } from "$lib/odi/stores";
	import ProgressStepper from "$lib/odi/components/session/ProgressStepper.svelte";
    const steps = [
		{ label: "면접 기본 정보" },
		{ label: "자료 업로드" },
		{ label: "AI 면접관 설정" },
		{ label: "세션 확인" }
	];
	import SessionBasicInfoCard from "$lib/odi/components/session/InterviewSessionBasicInfoCard.svelte";

	let basicInfo = $state({
		company: "",
		department: "",
		position: "",
		jobDetail: "",

		interviewTime: 0,
		interviewSituation: "",
		language: "",
		interviewerCount: "0",
		answerOrder: ""
	});


	function ensureInterviewDraft(): InterviewTemplate {
		const current = template.get();

		if (current?.type === "interview") {
			return current;
		}

		return template.loadOrCreate("interview") as InterviewTemplate;
	}

	let ready = $state(false);

	onMount(() => {
		const draft = ensureInterviewDraft();

		basicInfo.company = draft.environment.company_name;
		basicInfo.department = draft.environment.department;
		basicInfo.position = draft.environment.position;
		basicInfo.jobDetail = draft.environment.job_detail;
		basicInfo.language = draft.environment.language;
		basicInfo.interviewTime = draft.environment.duration_minutes;
		basicInfo.interviewSituation = draft.environment.interview_context;
		basicInfo.interviewerCount = String(draft.environment.interviewer_count);
		basicInfo.answerOrder = draft.environment.answer_order;

		ready = true;
	});

	$effect(() => {
		if (!ready) return; 
		template.patchEnvironment({
			company_name: basicInfo.company,
			department: basicInfo.department,
			position: basicInfo.position,
			job_detail: basicInfo.jobDetail,
			language: basicInfo.language,
			duration_minutes: basicInfo.interviewTime,
			interview_context: basicInfo.interviewSituation,
			interviewer_count: Number(basicInfo.interviewerCount),
			answer_order: basicInfo.answerOrder
		});
	});

	function goPrev() {
		goto("/odi");
	}

	function goNext() {

		goto("/odi/session/interview/upload");
	}

	const canNext = $derived(
		basicInfo.company.trim().length > 0 &&
		basicInfo.department.trim().length > 0 &&
		basicInfo.position.trim().length > 0 &&
		basicInfo.interviewTime > 0 &&
		basicInfo.interviewSituation.length > 0 &&
		basicInfo.language.length > 0 &&
		Number(basicInfo.interviewerCount) > 0 &&
		basicInfo.answerOrder.length > 0
	);
</script>

<section class="session-page">
	<header class="page-header">
		<p class="text-caption-main eyebrow">
			Session Setup
		</p>

		<div class="title-group">
			<h1 class="text-title-main">
				면접 기본 정보
			</h1>

			<p class="text-caption-main description">
				실전과 같은 환경을 설정하고, AI 면접관과 함께 연습을 시작해요.
			</p>
		</div>
	</header>

	<ProgressStepper
			steps={steps}
			currentStep={0}
		/>

	<SessionBasicInfoCard
		bind:company={basicInfo.company}
		bind:department={basicInfo.department}
		bind:position={basicInfo.position}
		bind:jobDetail={basicInfo.jobDetail}
		bind:interviewTime={basicInfo.interviewTime}
		bind:interviewSituation={basicInfo.interviewSituation}
		bind:language={basicInfo.language}
		bind:interviewerCount={basicInfo.interviewerCount}
		bind:answerOrder={basicInfo.answerOrder}
	/>

	<div class="actions">
		<Button
			variant="secondary"
			width="212px"
			disabled
		>
			이전 단계
		</Button>

		<Button
			width="212px"
			disabled={!canNext}
			onclick={goNext}
		>
			다음 단계
		</Button>
	</div>
</section>

<style>
.session-page {
	width: 100%;
	min-height: 100vh;
	padding: 36px 48px 40px;

	display: flex;
	flex-direction: column;

	gap: var(--space-6);
}

@media (max-width: 640px) {
	.session-page { padding: 24px 16px 32px; }
	.actions { align-items: stretch; flex-direction: column-reverse; }
	.actions :global(.button) { width: 100% !important; }
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

.actions {
	display: flex;
	justify-content: flex-end;
	align-items: center;

	gap: var(--space-4);
}
</style>
