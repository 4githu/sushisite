<!-- src/lib/odi/components/session/UploadSection.svelte -->

<script lang="ts">
	import {
		DocumentIcon,
		PdfIcon,
		Cloud
	} from "$lib/odi/icons";

	import type { OdiFileRef } from "$lib/odi/stores/template";

	let {
		title,
		required = false,
		fileRef = null,
		accept = ".pdf",
		maxSizeMB = 300,
		uploading = false,
		error = "",
		onFileSelected,
		onClear
	}: {
		title: string;
		required?: boolean;
		fileRef?: OdiFileRef | null;
		accept?: string;
		maxSizeMB?: number;
		uploading?: boolean;
		error?: string;
		onFileSelected?: (file: File) => void | Promise<void>;
		onClear?: () => void;
	} = $props();

	let input: HTMLInputElement;

	function openFileDialog() {
		if (uploading) return;
		input.click();
	}

	async function setFile(selectedFile: File | undefined) {
		if (!selectedFile || uploading) return;

		const maxSize = maxSizeMB * 1024 * 1024;

		if (selectedFile.size > maxSize) {
			alert(`최대 ${maxSizeMB}MB까지 업로드할 수 있습니다.`);
			return;
		}

		await onFileSelected?.(selectedFile);

		if (input) {
			input.value = "";
		}
	}

	function handleChange(event: Event) {
		const target = event.currentTarget as HTMLInputElement;
		setFile(target.files?.[0]);
	}

	function handleDragOver(event: DragEvent) {
		event.preventDefault();
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		setFile(event.dataTransfer?.files[0]);
	}

	function formatSize(size: number | null | undefined) {
		if (!size) return "";

		const mb = size / 1024 / 1024;

		if (mb >= 1) {
			return `${mb.toFixed(1)}MB`;
		}

		return `${Math.ceil(size / 1024)}KB`;
	}
</script>

<section class="upload-section">
	<div class="section-title">
		<div class="title-icon" aria-hidden="true">
			<img src={DocumentIcon} alt="" />
		</div>

		<h2 class="text-title-middle">
			{title}
		</h2>

		{#if required}
			<span class="required text-title-middle">*</span>
		{/if}
	</div>

	<input
		bind:this={input}
		class="file-input"
		type="file"
		{accept}
		onchange={handleChange}
	/>

	{#if fileRef && !uploading}
		<div class="uploaded-card" class:has-error={Boolean(error)}>
			<button type="button" class="uploaded-main clickable" onclick={openFileDialog} aria-label="다른 파일로 변경">
				<div class="pdf-icon" aria-hidden="true">
					<img src={PdfIcon} alt="" />
				</div>

				<span class="file-copy">
					<strong>{fileRef.original_name}</strong>
					<small>
						{formatSize(fileRef.size_bytes) || "크기 정보 없음"}
						{#if fileRef.page_count}
							· {fileRef.page_count}페이지
						{/if}
					</small>
				</span>
			</button>

			<div class="upload-status" aria-label="업로드 완료">
				<span class="status-check">✓</span>
				<span>업로드 완료</span>
			</div>

			{#if onClear}
				<button type="button" class="clear-icon clickable" aria-label="파일 선택 해제" onclick={onClear}>×</button>
			{/if}
		</div>
	{:else}
		<button
			type="button"
			class={["upload-box", "clickable", uploading && "uploading", error && "has-error"]}
			onclick={openFileDialog}
			ondragover={handleDragOver}
			ondrop={handleDrop}
			disabled={uploading}
		>
			<div class="upload-content">
				<img class="upload-icon" src={Cloud} alt="" />

				{#if uploading}
				<p class="text-body file-name">업로드 중...</p>
				<p class="text-body helper">파일을 서버에 저장하고 있습니다</p>
				{:else}
				<p class="text-body helper">
					PDF 파일을 드래그하거나 클릭하여 업로드 해주세요
				</p>

				<p class="text-body helper">
					최대 {maxSizeMB}MB
				</p>
				{/if}
			</div>
		</button>
	{/if}

	{#if error}
		<p class="error text-caption-medium">{error}</p>
	{/if}
</section>

<style>
	.upload-section {
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
	}

	.section-title {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.required {
		color: var(--purple);
	}

	.upload-box {
		width: 100%;
		height: 156px;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 11px var(--space-3) 11px var(--space-5);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-disabled);
	}

	.upload-box:hover {
		border-color: var(--primary);
		background: var(--blue-light);
	}

	.upload-box.uploading {
		opacity: 0.72;
	}

	.upload-box.has-error {
		border-color: var(--accent);
	}

	.uploaded-card {
		width: 100%;
		min-height: 88px;
		padding: 11px;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto 36px;
		align-items: center;
		gap: 10px;
		border: 1.4px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.uploaded-card.has-error {
		border-color: var(--accent);
	}

	.uploaded-main {
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 20px;
		text-align: left;
	}

	.pdf-icon {
		width: 52px;
		height: 52px;
		flex: 0 0 52px;
		border-radius: 8px;
		overflow: hidden;
	}

	.pdf-icon img {
		width: 100%;
		height: 100%;
		display: block;
		object-fit: cover;
	}

	.file-copy {
		min-width: 0;
		display: grid;
		gap: 4px;
	}

	.file-copy strong {
		overflow: hidden;
		color: var(--brand-black);
		font-size: 18px;
		font-weight: var(--font-medium);
		line-height: 1.35;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.file-copy small {
		color: var(--text-disabled);
		font-size: 14px;
	}

	.upload-status {
		display: flex;
		align-items: center;
		gap: 5px;
		color: #44c699;
		font-size: 14px;
		font-weight: var(--font-medium);
		white-space: nowrap;
	}

	.status-check {
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.clear-icon {
		width: 36px;
		height: 36px;
		border-radius: 8px;
		color: var(--text-secondary);
		font-size: 25px;
		line-height: 1;
	}

	.clear-icon:hover {
		background: var(--cool-grey-light);
		color: var(--accent);
	}

	.file-input {
		display: none;
	}

	.upload-content {
		width: 363px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 14px;
		text-align: center;
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

	.upload-icon {
		width: 36px;
		height: 36px;
		display: block;
	}

	.helper {
		color: var(--text-disabled);
	}

	.file-name {
		max-width: 100%;
		overflow: hidden;
		color: var(--primary);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.error {
		color: var(--accent);
	}

	@media (max-width: 640px) {
		.uploaded-card {
			grid-template-columns: minmax(0, 1fr) 36px;
		}

		.upload-status {
			grid-column: 1;
			padding-left: 72px;
		}

		.clear-icon {
			grid-column: 2;
			grid-row: 1 / span 2;
		}

		.uploaded-main {
			gap: 12px;
		}

		.file-copy strong {
			font-size: 15px;
		}
	}
</style>
