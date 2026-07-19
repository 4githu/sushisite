<!-- src/lib/odi/components/session/PresentationUploadFileCard.svelte -->

<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import UploadSection from "$lib/odi/components/session/UploadSection.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import { DocumentIcon } from "$lib/odi/icons";

	import type { OdiFileRef } from "$lib/odi/stores/template";

	let {
		slideFileRef = null,
		paperFileRef = null,
		scriptText = $bindable(""),
		slideUploading = false,
		paperUploading = false,
		slideError = "",
		paperError = "",
		onSlideSelected,
		onPaperSelected,
		onClearSlide,
		onClearPaper,
		onCheckScript
	}: {
		slideFileRef?: OdiFileRef | null;
		paperFileRef?: OdiFileRef | null;
		scriptText?: string;
		slideUploading?: boolean;
		paperUploading?: boolean;
		slideError?: string;
		paperError?: string;
		onSlideSelected?: (file: File) => void | Promise<void>;
		onPaperSelected?: (file: File) => void | Promise<void>;
		onClearSlide?: () => void;
		onClearPaper?: () => void;
		onCheckScript?: () => void;
	} = $props();

	const maxScriptLength = 10000;
	const scriptLength = $derived(scriptText.length);

	function handleScriptInput(event: Event) {
		const target = event.currentTarget as HTMLTextAreaElement;
		scriptText = target.value.slice(0, maxScriptLength);
	}
</script>

<SurfaceCard padding="43px 36px" minHeight="609px">
	<div class="upload-card-content">
		<UploadSection
			title="발표 슬라이드 PDF"
			required
			accept=".pdf"
			maxSizeMB={300}
			fileRef={slideFileRef}
			uploading={slideUploading}
			error={slideError}
			onFileSelected={onSlideSelected}
			onClear={onClearSlide}
		/>

		<UploadSection
			title="논문 PDF"
			accept=".pdf"
			maxSizeMB={300}
			fileRef={paperFileRef}
			uploading={paperUploading}
			error={paperError}
			onFileSelected={onPaperSelected}
			onClear={onClearPaper}
		/>

		<section class="script-section">
			<div class="section-title">
				<div class="title-icon" aria-hidden="true">
					<img src={DocumentIcon} alt="" />
				</div>

				<h2 class="text-title-middle">발표 스크립트</h2>
				<span class="required text-title-middle">*</span>
			</div>

			<textarea
				class="script-input text-body"
				value={scriptText}
				maxlength={maxScriptLength}
				placeholder="발표 스크립트 텍스트를 입력해주세요."
				oninput={handleScriptInput}
			></textarea>

			<div class="script-footer">
				<p class="counter text-caption">{scriptLength}/ {maxScriptLength.toLocaleString()}</p>

				<Button
					variant="outline"
					width="228px"
					onclick={onCheckScript}
				>
					스크립트 검사하기
				</Button>
			</div>
		</section>
	</div>
</SurfaceCard>

<style>
	.upload-card-content {
		display: flex;
		flex-direction: column;
		gap: 40px;
	}

	.script-section {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.section-title {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.title-icon {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: rgba(0, 80, 255, 0.15);
	}

	.title-icon img {
		width: 24px;
		height: 24px;
		display: block;
	}

	.required {
		color: var(--purple);
	}

	.script-input {
		width: 100%;
		height: 104px;
		padding: var(--space-5);
		resize: none;
		border: 1.4px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-primary);
	}

	.script-input::placeholder {
		color: var(--text-disabled);
	}

	.script-input:focus {
		border-color: var(--primary);
	}

	.script-footer {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: var(--space-5);
	}

	.counter {
		color: var(--text-disabled);
	}
</style>