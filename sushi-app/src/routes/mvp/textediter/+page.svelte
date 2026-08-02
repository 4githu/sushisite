<script lang="ts">
	import { TextEditorCard, type EditorDocument } from '$lib/textediter';

	let result = $state<EditorDocument>();
	let editor: TextEditorCard;
	let copied = $state(false);
	let fileInput: HTMLInputElement;
	let importMessage = $state('');

	async function copyJSON() {
		if (!result) return;
		await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}

	function saveJSON() {
		const document = editor?.getJSON() ?? result;
		if (!document) return;
		const blob = new Blob([JSON.stringify(document, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = `textediter-${new Date().toISOString().slice(0, 10)}.json`;
		anchor.click();
		URL.revokeObjectURL(url);
	}

	async function loadJSON(event: Event) {
		const file = (event.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		try {
			const parsed = JSON.parse(await file.text());
			editor?.setJSON(parsed);
			importMessage = `${file.name} 불러옴`;
		} catch {
			importMessage = 'JSON 파일을 읽지 못했습니다';
		} finally {
			if (fileInput) fileInput.value = '';
			setTimeout(() => (importMessage = ''), 1800);
		}
	}
</script>

<svelte:head><title>리치 텍스트 에디터 MVP</title></svelte:head>

<main class="demo-page">
	<h1>리치 텍스트 에디터</h1>
	<div class="demo-actions">
		<button onclick={saveJSON} disabled={!result}>JSON 저장</button>
		<button onclick={() => fileInput.click()}>JSON 불러오기</button>
		<input bind:this={fileInput} type="file" accept="application/json,.json" onchange={loadJSON} />
		{#if importMessage}<span>{importMessage}</span>{/if}
	</div>
	<TextEditorCard
		bind:this={editor}
		placeholder="문서를 작성해 보세요…"
		onchange={(value) => (result = value)}
	/>
	<section class="preview" aria-label="JSON 미리보기">
		<header>
			<h2>저장 JSON</h2>
			<button onclick={copyJSON} disabled={!result}>{copied ? '복사됨 ✓' : 'JSON 복사'}</button>
		</header>
		<pre>{JSON.stringify(result, null, 2)}</pre>
	</section>
</main>

<style>
	.demo-page {
		width: min(100% - 32px, 980px);
		margin: 40px auto;
		color: #172033;
	}
	h1 {
		margin-bottom: 20px;
		font-size: 28px;
	}
	.demo-actions {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 16px;
	}
	.demo-actions input {
		display: none;
	}
	.demo-actions button,
	.preview button {
		border: 0;
		border-radius: 7px;
		padding: 8px 12px;
		background: #6557d9;
		color: white;
		cursor: pointer;
	}
	.demo-actions button:disabled,
	.preview button:disabled {
		opacity: 0.5;
	}
	.demo-actions span {
		color: #475569;
		font-size: 13px;
	}
	.preview {
		margin-top: 24px;
		border: 1px solid #d8dee9;
		border-radius: 12px;
		overflow: hidden;
	}
	.preview header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 12px 16px;
		background: #f8fafc;
	}
	.preview h2 {
		margin: 0;
		font-size: 16px;
	}
	pre {
		min-height: 180px;
		max-height: 420px;
		margin: 0;
		overflow: auto;
		padding: 16px;
		background: #101827;
		color: #dbeafe;
		font-size: 12px;
	}
</style>
