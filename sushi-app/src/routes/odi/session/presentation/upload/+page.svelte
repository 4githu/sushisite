<!-- src/routes/odi/session/presentation/upload/+page.svelte -->

<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import { template, type OdiFileRef, type PresentationTemplate } from "$lib/odi/stores";
	import { uploadTempFile } from "$lib/odi/stores";

	import ProgressStepper from "$lib/odi/components/session/ProgressStepper.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import TipCard from "$lib/odi/components/session/TipCard.svelte";
	import PresentationUploadFileCard from "$lib/odi/components/session/PresentationUploadFileCard.svelte";

	import {
		TextSnippetIcon,
		MyLocationIcon,
		whiteright as grayright
	} from "$lib/odi/icons";

	const steps = [
		{ label: "발표 기본 정보" },
		{ label: "자료 업로드" },
		{ label: "AI 청중 설정" },
		{ label: "세션 확인" }
	];

	let ready = $state(false);

	let slideFileRef = $state(null as OdiFileRef | null);
	let paperFileRef = $state(null as OdiFileRef | null);
	let scriptText = $state("");

	let slideUploading = $state(false);
	let paperUploading = $state(false);
	let slideError = $state("");
	let paperError = $state("");

	function ensurePresentationDraft(): PresentationTemplate {
		const current = template.get();

		if (current?.type === "presentation") {
			return current;
		}

		// 새 세션 화면에서는 저장된 최근 템플릿 대신 빈 기본 draft만 사용합니다.
		template.setDefault("presentation");
		return template.get() as PresentationTemplate;
	}

	onMount(() => {
		const draft = ensurePresentationDraft();

		slideFileRef = draft.files.slide;
		paperFileRef = draft.files.paper;
		scriptText = draft.files.script_content ?? "";

		ready = true;
	});

	$effect(() => {
		if (!ready) return;

		template.patchFiles({
			script_content: scriptText
		});
	});

	const canNext = $derived(Boolean(slideFileRef?.storage_path) && !slideUploading && !paperUploading);

	async function handleSlideSelected(file: File) {
		slideUploading = true;
		slideError = "";

		try {
			const uploaded = await uploadTempFile(file, "slide");
			slideFileRef = uploaded;

			template.patchFiles({
				slide: uploaded
			});
		} catch (error) {
			slideError = error instanceof Error ? error.message : "발표 슬라이드 업로드에 실패했습니다.";
		} finally {
			slideUploading = false;
		}
	}

	async function handlePaperSelected(file: File) {
		paperUploading = true;
		paperError = "";

		try {
			const uploaded = await uploadTempFile(file, "paper");
			paperFileRef = uploaded;

			template.patchFiles({
				paper: uploaded
			});
		} catch (error) {
			paperError = error instanceof Error ? error.message : "논문 PDF 업로드에 실패했습니다.";
		} finally {
			paperUploading = false;
		}
	}

	function clearSlide() {
		slideFileRef = null;
		slideError = "";

		template.patchFiles({
			slide: null
		});
	}

	function clearPaper() {
		paperFileRef = null;
		paperError = "";

		template.patchFiles({
			paper: null
		});
	}

	function checkScript() {
		console.log("script check", scriptText);
	}
</script>

<main class="session-page">
	<header class="page-header">
		<p class="page-label text-caption-main">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">자료 업로드</h1>
			<p class="subtitle text-caption-main">발표 준비에 필요한 자료를 업로드하면 더 정교한 질문과 피드백을 받을 수 있어요.</p>
		</div>
	</header>

	<ProgressStepper {steps} currentStep={1} />

	<section class="content-grid">
		<PresentationUploadFileCard
			{slideFileRef}
			{paperFileRef}
			bind:scriptText
			{slideUploading}
			{paperUploading}
			{slideError}
			{paperError}
			onSlideSelected={handleSlideSelected}
			onPaperSelected={handlePaperSelected}
			onClearSlide={clearSlide}
			onClearPaper={clearPaper}
			onCheckScript={checkScript}
		/>

		<TipCard
			title="자료 업로드 TIP"
			description="업로드된 자료는 세션 시작 시 서버 파일 묶음으로 확정되며, 세션 파일은 일정 기간 이후 삭제할 수 있습니다."
			tips={[
				{
					icon: MyLocationIcon,
					title: "PDF 이미지 변환",
					description: "발표 슬라이드는 세션 시작 시 페이지별 이미지로 변환되어 VR 환경에서 바로 사용할 수 있습니다."
				},
				{
					icon: TextSnippetIcon,
					title: "파일명 보존",
					description: "서버 저장명은 고정되지만 원본 파일명은 기록되어 최근 세션에서 다시 확인할 수 있습니다."
				}
			]}
		/>
	</section>

	<footer class="page-actions">
		<Button
			variant="primary"
			width="212px"
			onclick={() => goto("/odi/session/presentation")}
		>
			이전 단계
		</Button>

		<Button
			variant="primary"
			width="212px"
			disabled={!canNext}
			trailingIcon={grayright}
			onclick={() => goto("/odi/session/presentation/AIsetup")}
		>
			다음 단계
		</Button>
	</footer>
</main>

<style>
	.session-page {
		width: 100%;
		min-height: 100vh;
		padding: 36px 48px 40px;
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

	.page-label {
		color: var(--primary);
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.subtitle {
		color: var(--text-secondary);
	}

	.content-grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 432px;
		gap: var(--space-5);
		align-items: stretch;
	}

	.page-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--space-4);
	}

	@media (max-width: 1280px) {
		.content-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.session-page { padding: 24px 16px 32px; }
		.page-actions { align-items: stretch; flex-direction: column-reverse; }
		.page-actions :global(.button) { width: 100% !important; }
	}
</style>
