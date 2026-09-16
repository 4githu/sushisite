<script lang="ts">
	import { goto } from '$app/navigation';

	import Button from '$lib/odi/components/common/Button.svelte';
	import ProgressStepper from '$lib/odi/components/session/ProgressStepper.svelte';
	import UploadSection from '$lib/odi/components/session/UploadSection.svelte';
	import SurfaceCard from '$lib/odi/components/common/SurfaceCard.svelte';
	import { template, uploadTempFile } from '$lib/odi/stores';
	import TipCard from '$lib/odi/components/session/TipCard.svelte';

	const steps = [
		{ label: '면접 기본 정보' },
		{ label: '자료 업로드' },
		{ label: 'AI 면접관 설정' },
		{ label: '세션 확인' }
	];

	let uploading = $state(''),
		error = $state('');
	async function upload(file: File, role: 'paper' | 'slide') {
		if (uploading) return;
		uploading = role;
		error = '';
		try {
			template.patchFiles({ [role]: await uploadTempFile(file, role) });
		} catch (e) {
			error = e instanceof Error ? e.message : '업로드 실패';
		} finally {
			uploading = '';
		}
	}

	const uploadTips = [
		{
			icon: 'target' as const,
			title: '더 정확한 질문 생성',
			description:
				'직접 입력한 자료를 기반으로 지원자의 경험과 역량에 맞춘 정교한 질문을 생성합니다.'
		},
		{
			icon: 'document' as const,
			title: '다양한 형식 지원',
			description: '이력서와 포트폴리오는 PDF 파일로 업로드해 주세요.'
		}
	];

	function goPrev() {
		goto('/odi/session/interview');
	}

	function goNext() {
		void goto('/odi/session/interview/AIsetup');
	}
</script>

<section class="session-page">
	<header class="page-header">
		<p class="text-caption-main eyebrow">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">자료 업로드</h1>

			<p class="text-caption-main description">
				면접 준비에 필요한 자료를 업로드하면 더 정교한 질문과 피드백을 받을 수 있어요.
			</p>
		</div>
	</header>

	<ProgressStepper {steps} currentStep={1} />

	<div class="content-row">
		<SurfaceCard padding="32px">
			<UploadSection
				title="이력서 / 자기소개서 PDF"
				required
				fileRef={$template?.files.paper}
				uploading={!!uploading}
				onFileSelected={(file) => upload(file, 'paper')}
				onClear={() => template.patchFiles({ paper: null })}
			/>
			<UploadSection
				title="포트폴리오 PDF"
				fileRef={$template?.files.slide}
				uploading={!!uploading}
				onFileSelected={(file) => upload(file, 'slide')}
				onClear={() => template.patchFiles({ slide: null })}
			/>
			{#if error}<p role="alert">{error}</p>{/if}
		</SurfaceCard>

		<TipCard
			title="자료 업로드 TIP"
			description="저장한 템플릿에서 자료를 다시 사용할 수 있습니다."
			tips={uploadTips}
		/>
	</div>

	<div class="actions">
		<Button variant="secondary" width="212px" onclick={goPrev}>이전 단계</Button>

		<Button width="212px" onclick={goNext} disabled={!!uploading || !$template?.files.paper}
			>다음 단계</Button
		>
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
