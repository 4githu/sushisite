<script lang="ts">
	import { tick, onMount, onDestroy, getContext, untrack } from 'svelte';
	import type { MemoBridge } from './memo-context';
	import { privateCacheUser } from './auth';
	import { verifiedPrivateOwner, samePrivateOwner } from './private-owner';
	import { request, PersonalApiError } from './api';
	import { readCaptures, localDay } from './capture';
	import { memoMeta, memoText, mergeMemoCaptures, memoRichDocument } from './memo-document';
	const bridge = getContext<MemoBridge | undefined>('netaq-memo');
	let edited = $state(false);
	type Note = {
		content: string;
		drawing: string;
		richDocument?: string;
		inheritedFrom: string | null;
		revision: number;
	};
	type Recovery = { text: string; revision: number; ids: string[] };
	let dialog: HTMLDialogElement, input: HTMLTextAreaElement;
	let date = $state(localDay()),
		text = $state(''),
		saved = $state(''),
		error = $state(''),
		status = $state(''),
		loading = $state(false),
		saving = $state(false),
		ready = $state(false),
		visible = $state(false),
		inherited = $state<string | null>(null),
		latest = $state<Note | null>(null);
	let canSave = $state(false);
	let revision = 0,
		originalRich = '',
		drawing = '',
		ids: string[] = [],
		owner = '',
		serial = 0;
	const dirty = $derived(ready && (text !== saved || !canSave));
	const key = (day: string) => `ondo-private:${owner}:memo:${day}`;
	function keepDraft() {
		if (!owner || !ready || String(privateCacheUser()) !== owner) return;
		try {
			if (text !== saved || !canSave)
				localStorage.setItem(key(date), JSON.stringify({ text, revision, ids }));
			else localStorage.removeItem(key(date));
		} catch {
			/* Server saving remains available. */
		}
	}
	$effect(() => {
		void text;
		void saved;
		void ready;
		keepDraft();
	});
	async function load(day: string) {
		keepDraft();
		date = day;
		const generation = ++serial;
		let account = '';
		loading = true;
 edited=false;
		canSave = false;
		ready = false;
		text = '';
		saved = '';
		inherited = null;
		originalRich = '';
		drawing = '';
		ids = [];
		error = '';
		status = '';
		latest = null;
		try {
			account = await verifiedPrivateOwner();
			if (generation !== serial) return;
			owner = account;
			const [note, captures] = await Promise.all([
				request<Note>(`/calendar/daily-notes/${day}`),
				readCaptures()
			]);
			if (generation !== serial) return;
			if (!(await samePrivateOwner(account)))
				throw new Error('계정이 바뀌었어요. 메모를 다시 열어주세요.');
			originalRich = note.richDocument || '';
			drawing = note.drawing || '';
			revision = note.revision;
			inherited = note.inheritedFrom;
			saved = memoText(note.content || '');
			const merged = mergeMemoCaptures(saved, memoMeta(originalRich), captures, day);
			text = merged.text;
			ids = merged.ids;
			let recovered: Recovery | null = null;
			try {
				recovered = JSON.parse(localStorage.getItem(key(day)) || 'null');
			} catch {
				/* Ignore malformed drafts. */
			}
			if (recovered && typeof recovered.text === 'string') {
				const recoveredMerged = mergeMemoCaptures(
					recovered.text,
					{ includedCaptureIds: recovered.ids || [] },
					captures,
					day
				);
				text = recoveredMerged.text;
				ids = recoveredMerged.ids;
				if (recovered.revision !== note.revision) {
					latest = note;
					revision = recovered.revision;
					error = '다른 화면에서 메모가 바뀌었어요. 작성하던 내용은 그대로 보관했어요.';
				} else status = '작성하던 내용을 불러왔어요';
			}
			if (day === localDay())
				try {
					const draft = JSON.parse(localStorage.getItem(`ondo-private:${owner}:capture`) || 'null');
					if (draft?.text && !captures.some((c) => c.id === draft.id) && !text.includes(draft.text))
						text = [text, draft.text].filter(Boolean).join('\n\n');
				} catch {}
			ready = true;
			canSave = true;
		} catch (e) {
			if (generation === serial) {
				error = e instanceof Error ? e.message : '메모를 불러오지 못했어요.';
				try {
					const recovery =
						account && (await samePrivateOwner(account))
							? JSON.parse(localStorage.getItem(key(day)) || 'null')
							: null;
					if (recovery && typeof recovery.text === 'string') {
						text = recovery.text;
						saved = '';
						revision = recovery.revision;
						ids = recovery.ids || [];
						ready = true;
						status = '기기에 보관한 입력을 표시하고 있어요';
					}
				} catch {}
			}
		} finally {
			if (generation === serial) {
				loading = false;
				await tick();
				if (visible && ready) input?.focus();
			}
		}
	}
	async function open(day = localDay()) {
		if (visible || saving) return;
		visible = true;
		dialog.showModal();
		await load(day);
	}
	function close() {
		if (saving) return;
		keepDraft();
		visible = false;
		dialog.close();
	}
	async function save(event?: SubmitEvent) {
		event?.preventDefault();
		if (!ready || !canSave || saving || loading || !dirty || latest) return;
		const account = owner,
			day = date,
			content = text,
			expected = revision,
			generation = serial,
			rich = memoRichDocument(content, originalRich, ids);
		saving = true;
		error = '';
		status = '';
		try {
			if (!(await samePrivateOwner(account)))
				throw new Error('계정이 바뀌었어요. 메모를 다시 열어주세요.');
			const response = await request<{ revision: number }>(`/calendar/daily-notes/${day}`, {
				method: 'PUT',
				body: { revision: expected, content, drawing, rich_document: rich }
			});
			if (generation !== serial) return;
			if (!(await samePrivateOwner(account)))
				throw new Error('계정이 바뀌었어요. 메모를 다시 열어주세요.');
			revision = response.revision;
			originalRich = rich;
			saved = content;
			if (text === content) edited = false;
			inherited = null;
			status = text === content ? '저장됨' : '추가 변경사항이 있어요';
			try {
				if (text === content) localStorage.removeItem(key(day));
				if (day === localDay()) localStorage.removeItem(`ondo-private:${owner}:capture`);
			} catch {}
			window.dispatchEvent(new Event('netaq-memo-changed'));
		} catch (e) {
			if (generation === serial) {
				error = e instanceof Error ? e.message : '저장하지 못했어요. 입력한 내용은 유지돼요.';
				if (e instanceof PersonalApiError && e.status === 409) {
					try {
						latest = await request<Note>(`/calendar/daily-notes/${day}`);
					} catch {
						/* Keep the local recovery. */
					}
				}
			}
		} finally {
			saving = false;
			keepDraft();
		}
	}
	function appendToLatest() {
		if (!latest) return;
		const local = text;
		const remote = memoText(latest.content || '');
		text = remote === local ? local : [remote, local].filter(Boolean).join('\n\n');
		saved = remote;
		revision = latest.revision;
		drawing = latest.drawing || '';
		const remoteIds = memoMeta(latest.richDocument || '').includedCaptureIds || [];
		ids = [...new Set([...ids, ...remoteIds])];
		originalRich = latest.richDocument || originalRich;
		latest = null;
		error = '';
		status = '두 내용을 합쳤어요. 확인한 뒤 저장하세요';
	}
	async function changeDate(day: string) {
		if (
			saving ||
			!/^\d{4}-\d{2}-\d{2}$/.test(day) ||
			!Number.isFinite(+new Date(day + 'T12:00:00'))
		)
			return;
		await load(day);
	}
	onMount(() => {
		const handler = (event: Event) => {
			const day = (event as CustomEvent<{ date?: string }>).detail?.date;
			void open(day || localDay());
		};
		const shortcut=(e:KeyboardEvent)=>{if((e.ctrlKey||e.metaKey)&&e.shiftKey&&e.key.toLowerCase()==='m'){e.preventDefault();void open();}};
        window.addEventListener('keydown',shortcut);
        window.addEventListener('netaq-open-memo', handler);
		if (location.hash === '#daily-note') void open();
		return () => {window.removeEventListener('netaq-open-memo', handler);window.removeEventListener('keydown',shortcut);};
	});
	onDestroy(() => {
		keepDraft();
		serial++;
	});
	$effect(() => {
		if (bridge) {
			bridge.render = memoForm;
			bridge.modalOpen = visible;
		}
	});
	$effect(() => {
		const day = bridge?.day;
		if (day && !visible) untrack(() => void load(day));
	});
	$effect(() => {
		void text;
		if (
			bridge?.day &&
			!visible &&
			edited &&
			dirty &&
			ready &&
			canSave &&
			!saving &&
			!error &&
			!latest
		) {
			const timer = setTimeout(() => void save(), 700);
			return () => clearTimeout(timer);
		}
	});
</script>

{#snippet memoForm(inline: boolean)}
	<form class:memo-inline-form={inline} onsubmit={save}>
		<header>
			<h2 id="memo-title">{inline ? '메모' : date === localDay() ? '오늘 메모' : '메모'}</h2>
			{#if !inline}<button type="button" onclick={close} disabled={saving} aria-label="메모 닫기"
					>×</button
				>{/if}
		</header>
		<div class="memo-date" class:inline-date={inline}>
			<label
				><span class="memo-date-label">메모 날짜</span><span aria-hidden="true"
					>{new Date(date + 'T12:00:00').toLocaleDateString('ko-KR', {
						month: 'long',
						day: 'numeric',
						weekday: 'long'
					})}</span
				><input
					type="date"
					aria-label="메모 날짜"
					value={date}
					disabled={saving || loading}
					onchange={(e) => void changeDate(e.currentTarget.value)}
				/></label
			>{#if inherited}<button
					type="button"
					disabled={saving || loading}
					onclick={() => inherited && void changeDate(inherited)}
					>{inherited.slice(5).replace('-', '/')}에서 이어짐</button
				>{/if}
		</div>
		<textarea
			bind:this={input}
			bind:value={text}
			aria-label="메모 내용"
			placeholder={loading ? '불러오는 중…' : '떠오른 생각을 자유롭게 적어두세요'}
			disabled={loading || !ready}
			maxlength="100000"
			oninput={() => {
				status = '';
				edited = true;
			}}
		></textarea>
		{#if error}<div class="memo-error">
				<p role="alert">{error}</p>
				{#if !canSave}<button type="button" onclick={() => void load(date)}>다시 불러오기</button
					>{/if}
			</div>{/if}
		{#if latest}<details class="memo-conflict">
				<summary>최신 메모와 비교</summary>
				<pre>{memoText(latest.content || '')}</pre>
				<button type="button" onclick={appendToLatest}>최신 메모 뒤에 내 내용 추가</button>
			</details>{/if}
		<footer>
			<p role="status">
				{saving ? '저장 중…' : status || (dirty ? '저장할 내용이 있어요' : ready ? '저장됨' : '')}
			</p>
			<button class="memo-save" disabled={saving || loading || !canSave || !dirty || !!latest}
				>{saving ? '저장 중…' : '저장'}</button
			>
		</footer>
	</form>
{/snippet}

<button class="capture-trigger" onclick={() => void open()}>빠른 기록</button>
<dialog
	class="memo-dialog"
	bind:this={dialog}
	aria-labelledby="memo-title"
	oncancel={(e) => {
		e.preventDefault();
		close();
	}}
>
	{#if visible}{@render memoForm(false)}{/if}
</dialog>

<style>
	.capture-trigger,
	.memo-save {
		border: 0;
		background: var(--ondo-accent, #c4412c);
		color: white;
		border-radius: 8px;
		padding: 12px 20px;
		font: inherit;
		font-size: 15px;
		font-weight: 700;
		cursor: pointer;
		min-height: 44px;
	}
	.capture-trigger {
		min-width: 144px;
	}
	.memo-dialog {
		position: fixed;
		inset: 0;
		margin: auto;
		box-sizing: border-box;
		width: min(680px, calc(100vw - 32px));
		height: 540px;
		max-height: calc(100dvh - 32px);
		padding: 24px;
		border: 1px solid var(--ondo-line, #e2e3e7);
		border-radius: 16px;
		color: var(--ondo-ink, #242529);
		background: white;
		overflow: hidden;
	}
	.memo-dialog::backdrop {
		background: #14151959;
	}
	.memo-dialog[open] {
		display: flex;
	}
	.memo-dialog form {
		display: flex;
		flex-direction: column;
		width: 100%;
		min-height: 0;
		gap: 16px;
	}
	.memo-dialog header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-shrink: 0;
		min-height: 44px;
	}
	.memo-dialog h2 {
		font-size: 22px;
		font-weight: 700;
		margin: 0;
	}
	.memo-dialog header button {
		background: none;
		border: 0;
		color: var(--ondo-muted);
		font: inherit;
		font-size: 26px;
		min-width: 44px;
		min-height: 44px;
		cursor: pointer;
	}
	.memo-date {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-shrink: 0;
		min-height: 28px;
		font-size: 14px;
		color: var(--ondo-muted);
	}
	.memo-date label {
		position: relative;
		display: flex;
		align-items: center;
		min-height: 32px;
		cursor: pointer;
	}
	.memo-date label:focus-within {
		outline: 2px solid var(--ondo-accent);
		outline-offset: 3px;
	}
	.memo-date-label {
		position: absolute;
		width: 1px;
		height: 1px;
		clip-path: inset(50%);
		overflow: hidden;
	}
	.memo-date input {
		position: absolute;
		inset: 0;
		opacity: 0;
		width: 100%;
		cursor: pointer;
		font: inherit;
		font-size: 14px;
		color: var(--ondo-muted);
		background: white;
		border: 0;
		padding: 0;
		max-width: 180px;
		min-height: 32px;
	}
	.memo-date button {
		font: inherit;
		font-size: 12px;
		color: var(--ondo-muted);
		border: 0;
		border-bottom: 1px solid var(--ondo-line);
		background: white;
		padding: 4px;
		cursor: pointer;
	}
	.memo-dialog textarea {
		flex: 1;
		min-height: 100px;
		box-sizing: border-box;
		width: 100%;
		border: 0;
		border-radius: 0;
		padding: 0 2px;
		resize: none;
		font: inherit;
		font-size: 16px;
		line-height: 1.8;
		color: var(--ondo-ink);
		background: white;
		outline: none;
	}
	.memo-dialog textarea:focus {
		box-shadow: none;
		--tw-ring-shadow: 0 0 #0000;
		--tw-ring-offset-shadow: 0 0 #0000;
		border-color: transparent;
		outline: none;
	}
	.memo-dialog textarea:focus-visible {
		outline: none;
	}
	.memo-dialog textarea:disabled {
		opacity: 0.65;
	}
	.memo-dialog footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-shrink: 0;
		min-height: 48px;
	}
	.memo-dialog footer p {
		margin: 0;
		font-size: 12px;
		color: var(--ondo-muted);
		line-height: 1.5;
	}
	.memo-save {
		min-width: 112px;
		flex-shrink: 0;
	}
	.memo-dialog button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.memo-error {
		font-size: 13px;
		color: #b33625;
		flex-shrink: 0;
	}
	.memo-error p {
		margin: 0;
	}
	.memo-error button,
	.memo-conflict button {
		min-height: 36px;
		border: 1px solid var(--ondo-line);
		border-radius: 6px;
		background: white;
		font: inherit;
		font-size: 13px;
		padding: 6px 10px;
		margin-top: 8px;
	}
	.memo-conflict {
		max-height: 160px;
		overflow: auto;
		font-size: 13px;
		flex-shrink: 0;
	}
	.memo-conflict pre {
		font: inherit;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		background: #f4f5f7;
		padding: 12px;
	}
	.memo-conflict summary {
		cursor: pointer;
		min-height: 32px;
	}
	@media (max-width: 760px) {
		.capture-trigger {
			min-width: 116px;
			font-size: 14px;
			padding: 10px 16px;
		}
		.memo-dialog {
			padding: 20px;
			width: calc(100vw - 32px);
			height: 540px;
		}
		.memo-dialog h2 {
			font-size: 22px;
		}
		.memo-dialog form {
			gap: 16px;
		}
		.memo-date {
			font-size: 12px;
			flex-wrap: wrap;
			gap: 4px;
		}
		.memo-date input {
			font-size: 14px;
		}
		.memo-dialog textarea {
			font-size: 16px;
		}
	}

	.memo-inline-form {
		height: 100%;
		min-height: 420px;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.memo-inline-form header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 36px;
	}
	.memo-inline-form h2 {
		font-size: 18px;
		margin: 0;
	}
	.memo-inline-form .inline-date {
		display: none;
	}
	.memo-inline-form textarea {
		width: 100%;
		flex: 1;
		min-height: 320px;
		border: 0;
		background: white;
		resize: none;
		padding: 0;
		font: inherit;
		font-size: 16px;
		line-height: 1.8;
		color: var(--ondo-ink);
		box-sizing: border-box;
	}
	.memo-inline-form textarea:focus {
		outline: 0;
		box-shadow: none;
		border-color: transparent;
	}
	.memo-inline-form footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.memo-inline-form footer p {
		font-size: 12px;
		color: var(--ondo-muted);
	}
	.memo-inline-form .memo-save {
		min-height: 36px;
		min-width: 64px;
		padding: 6px 12px;
		font-size: 13px;
	}
	.memo-inline-form .memo-error {
		font-size: 13px;
		color: #b33625;
	}
</style>
