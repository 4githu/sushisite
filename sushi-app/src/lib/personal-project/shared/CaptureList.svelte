<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import {
		readCaptures,
		updateCapture,
		deleteCapture,
		moveCapture,
		localDay,
		type Capture
	} from './capture';
	let {
		todayOnly = false,
		tasksOnly = false,
		day = localDay()
	}: { todayOnly?: boolean; tasksOnly?: boolean; day?: string } = $props();
	let items = $state<Capture[]>([]),
		error = $state(''),
		busy = $state(false),
		loading = $state(true);
	let view = $state<'inbox' | 'task' | 'note'>('inbox');
	let editing = $state<string | null>(null),
		draft = $state('');
	beforeNavigate(({ cancel }) => {
		if (busy) cancel();
		else if (
			editing &&
			draft !== items.find((i) => i.id === editing)?.text &&
			!confirm('수정 중인 기록을 두고 이동할까요?')
		)
			cancel();
	});
	const visible = $derived(
		items.filter((i) => (todayOnly ? i.today === day : i.kind === (tasksOnly ? 'task' : view)))
	);
	async function load() {
		try {
			items = await readCaptures();
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : '불러오지 못했어요';
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		void load();
		window.addEventListener('netaq-captures-changed', load);
		return () => window.removeEventListener('netaq-captures-changed', load);
	});
	async function update(id: string, patch: Parameters<typeof updateCapture>[1]) {
		if (busy) return;
		busy = true;
		try {
			items = await updateCapture(id, patch);
			if (patch.text !== undefined) editing = null;
			error = '';
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	async function remove(id: string) {
		if (busy || !confirm('기록을 삭제할까요? 삭제한 기록은 되돌릴 수 없어요.')) return;
		busy = true;
		try {
			items = await deleteCapture(id);
			error = '';
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	async function move(id: string, d: -1 | 1) {
		busy = true;
		try {
			items = await moveCapture(id, d, day);
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
</script>

<section
	class="capture-list"
	aria-label={todayOnly ? '오늘 선택한 할 일' : tasksOnly ? '빠른 기록에서 고른 할 일' : '정리함'}
>
	<p class="save-progress" role="status">{busy ? '변경 저장 중…' : ''}</p>
	<header>
		<h2>{todayOnly ? '오늘 선택한 할 일' : tasksOnly ? '날짜 없이 기록한 할 일' : '정리함'}</h2>
		{#if todayOnly || tasksOnly}<a href="/personal-project/calendar/inbox"
				>{todayOnly ? '할 일 고르기' : '정리함 보기'}</a
			>{/if}
	</header>
	{#if !todayOnly && !tasksOnly}<nav aria-label="기록 분류">
			{#each [{ id: 'inbox', label: '정리 전' }, { id: 'task', label: '할 일' }, { id: 'note', label: '보관한 메모' }] as tab}<button
					aria-pressed={view === tab.id}
					onclick={() => (view = tab.id as typeof view)}>{tab.label}</button
				>{/each}
		</nav>{/if}
	{#if error}<p role="alert">{error} <button onclick={load}>다시 불러오기</button></p>{/if}
	{#if loading}<p role="status">기록을 불러오는 중…</p>{/if}
	{#each visible as item (item.id)}<article class:done={item.done}>
			<div class="record">
				<input
					type="checkbox"
					aria-label={`${item.text} 완료`}
					checked={item.done}
					disabled={busy}
					onchange={() => update(item.id, { done: !item.done })}
				/>
				{#if editing === item.id}
					<form
						class="record-edit"
						onsubmit={(e) => {
							e.preventDefault();
							void update(item.id, { text: draft });
						}}
					>
						<textarea
							aria-label="기록 수정 내용"
							bind:value={draft}
							maxlength={2000}
							disabled={busy}
							rows="3"
						></textarea>
						<button disabled={busy || !draft.trim()} type="submit">수정 저장</button>
						<button disabled={busy} type="button" onclick={() => (editing = null)}>취소</button>
					</form>
				{:else}<p>{item.text}</p>{/if}
				<details class="record-menu">
					<summary aria-label={`${item.text} 옵션`}>⋯</summary>
					<div>
						<button
							disabled={busy}
							onclick={(e) => {
								editing = item.id;
								draft = item.text;
								e.currentTarget.closest('details')!.open = false;
							}}>수정</button
						>
						<button disabled={busy} onclick={() => remove(item.id)}>삭제</button>
					</div>
				</details>
			</div>
			<div class="actions">
				{#if todayOnly}<button
						disabled={busy || item.done}
						aria-label={`${item.text} 위로`}
						onclick={() => move(item.id, -1)}>↑</button
					><button
						disabled={busy || item.done}
						aria-label={`${item.text} 아래로`}
						onclick={() => move(item.id, 1)}>↓</button
					><button disabled={busy} onclick={() => update(item.id, { today: null })}
						>오늘 목록에서 빼기</button
					>{:else}<button
						disabled={busy}
						onclick={() => update(item.id, { kind: 'task', today: day })}>오늘 할 일</button
					><button disabled={busy} onclick={() => update(item.id, { kind: 'task', today: null })}
						>나중에 할 일</button
					><button disabled={busy} onclick={() => update(item.id, { kind: 'note', today: null })}
						>메모로 보관</button
					>{/if}
			</div>
		</article>{:else}{#if !loading}<p class="empty">
				{todayOnly
					? '오늘 할 일을 정리함에서 골라보세요.'
					: view === 'inbox'
						? '정리할 기록이 없어요. 빠른 기록으로 적어보세요.'
						: '아직 기록이 없어요.'}
			</p>{/if}{/each}
</section>

<style>
	.save-progress {
		height: 20px;
		margin: 0;
		font-size: 12px;
		color: var(--ondo-muted);
	}
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
	}
	h2 {
		font-size: 19px;
		margin: 0;
	}
	a {
		font-size: 14px;
		color: var(--ondo-muted);
	}
	nav {
		display: flex;
		gap: 8px;
		margin: 20px 0;
	}
	button {
		font: inherit;
		font-size: 13px;
		min-height: 44px;
		border: 1px solid var(--ondo-line);
		background: white;
		border-radius: 7px;
		padding: 8px 12px;
		color: inherit;
		cursor: pointer;
	}
	button[aria-pressed='true'] {
		color: var(--ondo-accent);
		background: #faeee9;
		border-color: #faeee9;
	}
	article {
		border-bottom: 1px solid var(--ondo-line);
		padding: 16px 0;
	}
	.record {
		display: flex;
		align-items: flex-start;
		gap: 12px;
	}
	.record p {
		flex: 1;
		margin: 4px 0;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 16px;
	}
	.record input {
		width: 20px;
		height: 20px;
		margin: 6px 0;
		accent-color: var(--ondo-accent);
		flex-shrink: 0;
	}
	.record-edit {
		flex: 1;
		min-width: 0;
	}
	.record-edit textarea {
		width: 100%;
		box-sizing: border-box;
		border: 1px solid var(--ondo-line);
		padding: 10px;
		font: inherit;
		font-size: 16px;
		border-radius: 6px;
		resize: vertical;
	}
	.record-menu {
		position: relative;
		margin-left: auto;
		flex-shrink: 0;
	}
	.record-menu summary {
		list-style: none;
		cursor: pointer;
		min-width: 44px;
		min-height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 24px;
	}
	.record-menu summary::-webkit-details-marker {
		display: none;
	}
	.record-menu > div {
		position: absolute;
		right: 0;
		top: 44px;
		background: white;
		z-index: 2;
		padding: 4px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		box-shadow: 0 4px 16px #0001;
		min-width: 90px;
	}
	.record-menu button {
		display: block;
		width: 100%;
		border: 0;
		text-align: left;
	}
	.done .record p {
		text-decoration: line-through;
		color: var(--ondo-muted);
	}
	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin: 8px 0 0 32px;
	}
	.actions button {
		background: transparent;
	}
	.empty {
		padding: 20px 0;
		color: var(--ondo-muted);
		font-size: 14px;
	}
	p[role='alert'] {
		color: #b33625;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
</style>
