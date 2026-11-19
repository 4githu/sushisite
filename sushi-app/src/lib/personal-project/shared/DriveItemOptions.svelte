<script lang="ts">
	import { request } from './api';
	let {
		item,
		folders,
		currentFolder = null,
		onchanged
	}: {
		item: { id: string; name: string };
		folders: { id: string; name: string; parent_id: string | null }[];
		currentFolder?: string | null;
		onchanged: () => Promise<void>;
	} = $props();
	let name = $state(''),
		target = $state(''),
		error = $state(''),
		status = $state(''),
		busy = $state(false),
		link = $state(''),
		days = $state(7);
	let dialog: HTMLDialogElement;
	async function run(fn: () => Promise<void>) {
		if (busy) return;
		busy = true;
		error = '';
		status = '';
		try {
			await fn();
		} catch (e) {
			error = e instanceof Error ? e.message : '처리하지 못했어요';
		} finally {
			busy = false;
		}
	}
	function path(id: string): string {
		const item = folders.find((f) => f.id === id);
		return item ? (item.parent_id ? path(item.parent_id) + ' / ' : '') + item.name : '';
	}
	async function copy() {
		try {
			await navigator.clipboard.writeText(link);
			status = '링크를 복사했어요';
		} catch {
			status = '아래 링크를 선택해 복사해주세요';
		}
	}
</script>

<button
	class="options-trigger"
	onclick={() => {
		name = item.name;
		target = currentFolder || '';
		dialog.showModal();
	}}>이름·이동·공유</button
>
<dialog
	bind:this={dialog}
	aria-labelledby="file-options-heading"
	oncancel={(e) => {
		if (busy) e.preventDefault();
	}}
>
	<header>
		<h2 id="file-options-heading">파일 관리</h2>
		<button aria-label="파일 관리 닫기" disabled={busy} onclick={() => dialog.close()}>×</button>
	</header>
	<form
		onsubmit={(e) => {
			e.preventDefault();
			void run(async () => {
				await request(`/drive/items/${item.id}/organization`, {
					method: 'PUT',
					body: { name, folder_id: target || null }
				});
				await onchanged();
				status = '파일 정보를 저장했어요';
			});
		}}
	>
		<label>파일 이름<input bind:value={name} required maxlength="200" disabled={busy} /></label>
		<label
			>폴더<select bind:value={target} disabled={busy}
				><option value="">전체 파일</option>{#each folders as folder}<option value={folder.id}
						>{path(folder.id)}</option
					>{/each}</select
			></label
		>
		<button class="primary" disabled={busy || !name.trim()}>변경 저장</button>
	</form>
	<section>
		<h3>링크 공유</h3>
		<p>링크를 가진 사람이 파일을 다운로드할 수 있어요.</p>
		<label
			>유효 기간<select bind:value={days} disabled={busy}
				><option value={1}>1일</option><option value={7}>7일</option><option value={30}>30일</option
				></select
			></label
		>
		<div class="actions">
			<button
				disabled={busy}
				onclick={() =>
					run(async () => {
						const result = await request<{ token: string; expiresAt: string }>(
							`/drive/items/${item.id}/share`,
							{ method: 'POST', body: { days } }
						);
						link = `${window.location.origin}/share/${result.token}`;
						status = `${new Date(result.expiresAt).toLocaleString('ko-KR')}까지 공유해요`;
						await onchanged();
					})}>공유 링크 만들기</button
			><button
				disabled={busy}
				onclick={() =>
					run(async () => {
						await request(`/drive/items/${item.id}/share`, { method: 'DELETE' });
						link = '';
						status = '이 파일의 공유 링크를 모두 해제했어요';
						await onchanged();
					})}>링크 공유 해제</button
			>
		</div>
		{#if link}<div class="link">
				<input
					aria-label="공유 링크"
					value={link}
					readonly
					onclick={(e) => e.currentTarget.select()}
				/><button onclick={copy}>복사</button>
			</div>{/if}
	</section>
	<p class="feedback" role="status">{busy ? '처리 중…' : status}</p>
	{#if error}<p role="alert">{error}</p>{/if}
</dialog>

<style>
	button,
	input,
	select {
		font: inherit;
		font-size: 14px;
		min-height: 44px;
		box-sizing: border-box;
	}
	button {
		padding: 8px 12px;
		background: white;
		color: var(--ondo-ink);
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	dialog {
		padding: 24px;
		border: 1px solid var(--ondo-line);
		border-radius: 16px;
		width: min(500px, calc(100vw - 32px));
		box-sizing: border-box;
		color: var(--ondo-ink);
	}
	dialog::backdrop {
		background: #18191c66;
	}
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 20px;
	}
	h2 {
		font-size: 22px;
		margin: 0;
	}
	header button {
		border: 0;
		font-size: 24px;
	}
	form,
	label {
		display: grid;
		gap: 8px;
	}
	form {
		gap: 16px;
	}
	label {
		font-size: 13px;
		color: var(--ondo-muted);
	}
	input,
	select {
		width: 100%;
		padding: 10px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		background: white;
		color: var(--ondo-ink);
	}
	.primary {
		background: var(--ondo-accent);
		border-color: var(--ondo-accent);
		color: white;
		justify-self: end;
	}
	section {
		border-top: 1px solid var(--ondo-line);
		margin-top: 24px;
		padding-top: 12px;
	}
	h3 {
		font-size: 16px;
	}
	p {
		font-size: 13px;
		line-height: 1.6;
		color: var(--ondo-muted);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 12px;
	}
	.link {
		display: flex;
		gap: 8px;
		margin-top: 12px;
	}
	.link input {
		min-width: 0;
	}
	.feedback {
		min-height: 24px;
		margin-bottom: 0;
	}
	p[role='alert'] {
		color: #b33625;
	}
	@media (max-width: 760px) {
		input,
		select {
			font-size: 16px;
		}
	}
</style>
