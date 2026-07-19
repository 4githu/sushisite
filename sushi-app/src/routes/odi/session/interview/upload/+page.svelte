<script lang="ts">
	import { goto } from "$app/navigation";

	import Button from "$lib/odi/components/common/Button.svelte";
	import ProgressStepper from "$lib/odi/components/session/ProgressStepper.svelte";
	import InterviewUploadFileCard from "$lib/odi/components/session/InterviewUploadFileCard.svelte";
	import TipCard from "$lib/odi/components/session/TipCard.svelte";

	const steps = [
		{ label: "면접 기본 정보" },
		{ label: "자료 업로드" },
		{ label: "AI 면접관 설정" },
		{ label: "세션 확인" }
	];

	let uploadInfo = $state({
		resumeFile: null as File | null,
		portfolioFile: null as File | null,

		resumePath: "",
		portfolioPath: ""
	});

	const uploadTips = [
		{
			icon: "target" as const,
			title: "더 정확한 질문 생성",
			description: "직접 입력한 자료를 기반으로 지원자의 경험과 역량에 맞춘 정교한 질문을 생성합니다."
		},
		{
			icon: "document" as const,
			title: "다양한 형식 지원",
			description: "PDF, PPT, DOCX, TXT, 이미지 등 다양한 형식의 파일을 지원합니다."
		}
	];

	function goPrev() {
		goto("/odi/session/interview");
	}

	function goNext() {
		const sessionDraft = {
			uploadInfo: {
				resumePath: uploadInfo.resumePath,
				portfolioPath: uploadInfo.portfolioPath
			}
		};

		console.log(sessionDraft);

		goto("/odi/session/interview/AIsetup");
	}
</script>

<section class="session-page">
	<header class="page-header">
		<p class="text-caption-main eyebrow">
			Session Setup
		</p>

		<div class="title-group">
			<h1 class="text-title-main">
				자료 업로드
			</h1>

			<p class="text-caption-main description">
				면접 준비에 필요한 자료를 업로드하면 더 정교한 질문과 피드백을 받을 수 있어요.
			</p>
		</div>
	</header>

	<ProgressStepper
		{steps}
		currentStep={1}
	/>

	<div class="content-row">
		<InterviewUploadFileCard
			bind:resumeFile={uploadInfo.resumeFile}
			bind:portfolioFile={uploadInfo.portfolioFile}
		/>

		<TipCard
			title="자료 업로드 TIP"
			description="업로드된 자료는 암호화되어 안전하게 저장되며, 사용자의 동의 없이 외부로 공유되지 않습니다."
			tips={uploadTips}
		/>
	</div>

	<div class="actions">
		<Button
			variant="secondary"
			width="212px"
			onclick={goPrev}
		>
			이전 단계
		</Button>

		<Button
			width="212px"
			onclick={goNext}
		>
			다음 단계
		</Button>
	</div>
</section>

<style>
.session-page {
	width: 100%;

	display: flex;
	flex-direction: column;

	gap: var(--space-6);
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
</style>