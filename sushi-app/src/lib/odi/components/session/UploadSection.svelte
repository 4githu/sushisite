<!-- src/lib/odi/components/session/UploadSection.svelte -->

<script lang="ts">
	import {
		DocumentIcon,
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

	<button
		type="button"
		class={["upload-box", "clickable", fileRef && "has-file", uploading && "uploading", error && "has-error"]}
		onclick={openFileDialog}
		ondragover={handleDragOver}
		ondrop={handleDrop}
		disabled={uploading}
	>
		<input
			bind:this={input}
			class="file-input"
			type="file"
			{accept}
			onchange={handleChange}
		/>

		<div class="upload-content">
			<img class="upload-icon" src={Cloud} alt="" />

			{#if uploading}
				<p class="text-body file-name">업로드 중...</p>
				<p class="text-body helper">파일을 서버에 저장하고 있습니다</p>
			{:else if fileRef}
				<p class="text-body file-name">
					{fileRef.original_name}
				</p>

				<p class="text-body helper">
					{formatSize(fileRef.size_bytes)}
					{#if fileRef.page_count}
						· {fileRef.page_count}페이지
					{/if}
				</p>

				<p class="text-body helper">
					다른 파일로 변경하려면 클릭해주세요
				</p>
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

	{#if fileRef && onClear}
		<div class="file-actions">
			<button type="button" class="clear-button clickable text-caption-medium" onclick={onClear}>
				파일 선택 해제
			</button>
		</div>
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

	.upload-box.has-file {
		border-color: var(--primary);
	}

	.upload-box.uploading {
		opacity: 0.72;
	}

	.upload-box.has-error {
		border-color: var(--accent);
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

	.file-actions {
		display: flex;
		justify-content: flex-end;
		margin-top: calc(var(--space-6) * -1 + var(--space-2));
	}

	.clear-button {
		color: var(--text-secondary);
	}

	.clear-button:hover {
		color: var(--accent);
	}

	.error {
		color: var(--accent);
	}
</style>