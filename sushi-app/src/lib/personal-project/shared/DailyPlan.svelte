<script lang="ts">
	import { onMount, onDestroy, tick, untrack } from 'svelte';
	import PersonalTextEditor from '../editor/PersonalTextEditor.svelte';
	import { createDocument, createTextBlock, normalizeDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import { beforeNavigate } from '$app/navigation';
	import { request } from './api';
	import { privateCacheUser } from './auth';
	import {
		readTaskMode,
		saveTaskMode,
		isolatedProject,
		taskGroups,
		type CalendarProject,
		eventCategories,
		taskDeadline,
		taskWaiting,
		taskTiming
	} from './planner';
	import type { CalendarEvent } from './types';
	let {
		date,
		tasks,
		projects,
		pendingTasks = [],
		onedit,
		oncomplete,
		ondirty
	}: {
		date: string;
		tasks: CalendarEvent[];
		projects: CalendarProject[];
		pendingTasks?: number[];
		ondirty: (dirty: boolean) => void;
		onedit: (event: CalendarEvent) => void;
		oncomplete: (event: CalendarEvent) => void;
	} = $props();
	let note = $state(''),
		saved = $state(''),
		drawing = $state(''),
		savedDrawing = $state(''),
		inheritedFrom = $state<string | null>(null),
		loadedDate = $state(''),
		error = $state(''),
		loading = $state(true),
		saving = $state(false);
	let conflict = $state(false);
	let revision = 0,
		serverRevision = 0,
		firstDirtyAt = 0;
	const recoveryKey = (day: string) => `ondo-private:${privateCacheUser()}:note:${day}`;
	$effect(() => {
		const payload = {
			content: note,
			drawing,
			rich_document: richContent,
			revision: serverRevision
		};
		if (!loading && loadedDate === date && dirty) {
			try {
				if (privateCacheUser())
					localStorage.setItem(recoveryKey(loadedDate), JSON.stringify(payload));
			} catch {
				/* Saving to the server remains available. */
			}
			if (!firstDirtyAt) firstDirtyAt = Date.now();
			if (!saving && !error) {
				const timer = setTimeout(
					() => void saveNote(),
					Math.max(0, Math.min(500, 2000 - (Date.now() - firstDirtyAt)))
				);
				return () => clearTimeout(timer);
			}
		} else if (!dirty) firstDirtyAt = 0;
	});
	let inkCanvas: HTMLCanvasElement;
	let penActive = false;
	let activePointer: number | null = null;
	let penPoint: { x: number; y: number } | null = null;
	let retry = $state(0);
	onDestroy(() => ondirty(false));
	let editing = $state(true);
	let richInitial = $state<EditorDocument | null>(null),
		richLive = $state<EditorDocument | null>(null);
	let foldedBlocks = $state<Record<string, boolean>>({}),
		inkOpen = $state(true);
	let richChecks = $state<Record<string, boolean>>({}),
		savedRich = $state('');
	const richContent = $derived(
		richLive
			? JSON.stringify({
					document: { ...richLive, updatedAt: richInitial?.updatedAt || richLive.updatedAt },
					checks: richChecks,
					folds: foldedBlocks
				})
			: ''
	);
	function useRich() {
		const doc = createDocument();
		const checks: Record<string, boolean> = {};
		doc.blocks = note.split('\n').map((line) => {
			const block = createTextBlock('paragraph', line.replace(/^\s*- \[[ xX]\]\s*/, ''));
			if (/^\s*- \[[xX]\]/.test(line)) checks[block.id] = true;
			return block;
		});
		richChecks = checks;
		richInitial = richLive = doc;
		editing = true;
	}
	function richChanged(doc: EditorDocument) {
		richLive = doc;
		note = doc.blocks
			.map((block) =>
				block.type === 'table'
					? block.rows
							.map((row) =>
								row
									.map((cell) =>
										cell.blocks.map((b) => b.children.map((c) => c.text).join('')).join(' ')
									)
									.join('\t')
							)
							.join('\n')
					: `${richChecks[block.id] ? '- [x] ' : '- [ ] '}${block.children.map((c) => c.text).join('')}`
			)
			.join('\n');
	}
	let taskMode = $state<'time' | 'theme'>('time');
	onMount(() => {
		taskMode = readTaskMode();
		try {
			inkOpen = localStorage.getItem('ondo.ink-open') !== 'false';
		} catch {
			/* optional preference */
		}
	});
	let penOnly = $state(true);
	let penColor = $state('#25262b');
	let erasing = $state(false);
	let hardwareEraser = false;
	let noteInput = $state<HTMLTextAreaElement>();
	const isolated = $derived(tasks.filter((e) => isolatedProject(e, projects)));
	const ordinary = $derived(tasks.filter((e) => !isolatedProject(e, projects)));
	function noteBeforeInput(event: InputEvent) {
		if (event.isComposing || event.inputType !== 'insertLineBreak') return;
		const el = event.currentTarget as HTMLTextAreaElement;
		const start = el.selectionStart,
			end = el.selectionEnd;
		const lineStart = note.lastIndexOf('\n', start - 1) + 1;
		const line = note.slice(lineStart, start);
		const match = line.match(/^(\s*)- \[[ xX]\] (.*)$/);
		if (!match) return;
		event.preventDefault();
		const from = !match[2].trim() ? lineStart : start;
		const inserted = !match[2].trim() ? '\n' : '\n' + match[1] + '- [ ] ';
		note = note.slice(0, from) + inserted + note.slice(end);
		void tick().then(() => el.setSelectionRange(from + inserted.length, from + inserted.length));
	}
	async function addCheckbox() {
		editing = true;
		await tick();
		if (!noteInput) return;
		const pos = noteInput.selectionStart;
		const start = note.lastIndexOf('\n', pos - 1) + 1;
		note = note.slice(0, start) + '- [ ] ' + note.slice(start);
		await tick();
		noteInput.focus();
		noteInput.setSelectionRange(pos + 6, pos + 6);
	}
	const dirty = $derived(note !== saved || drawing !== savedDrawing || richContent !== savedRich);
	$effect(() => {
		ondirty(dirty);
	});
	beforeNavigate(({ cancel }) => {
		if (dirty && !confirm('저장하지 않은 메모가 있습니다. 이동할까요?')) cancel();
	});
	const horizon = $derived(+new Date(date + 'T00:00:00') + 7 * 86400000);
	const available = $derived(
		ordinary.filter((e) => !taskWaiting(e, Math.min(Date.now(), +new Date(date + 'T23:59:59'))))
	);
	const soon = $derived(available.filter((e) => +new Date(taskDeadline(e)) < horizon));
	const later = $derived(available.filter((e) => +new Date(taskDeadline(e)) >= horizon));
	const waiting = $derived(ordinary.filter((e) => !available.includes(e)));
	const categories = $derived([...new Set(soon.flatMap(eventCategories))]);
	$effect(() => {
		const day = date;
		retry;
		untrack(() => {
			if (loadedDate && loadedDate !== day && dirty && !loading && !saving) void saveNote();
		});
		note = saved = '';
		const current = ++revision;
		loading = true;
		error = '';
		void request<{
			content: string;
			drawing: string;
			richDocument?: string;
			inheritedFrom: string | null;
			revision: number;
		}>(`/calendar/daily-notes/${day}`)
			.then((data) => {
				if (current !== revision) return;
				serverRevision = data.revision;
				conflict = false;
				const richData = data.richDocument ? JSON.parse(data.richDocument) : null;
				richInitial = richLive = richData ? normalizeDocument(richData.document) : null;
				richChecks = richData?.checks || {};
				foldedBlocks = richData?.folds || {};
				savedRich = richLive
					? JSON.stringify({ document: richLive, checks: richChecks, folds: foldedBlocks })
					: '';
				note = data.content || '';
				saved = note;
				if (!richLive) {
					useRich();
					savedRich = JSON.stringify({
						document: richLive,
						checks: richChecks,
						folds: foldedBlocks
					});
				}
				drawing = data.drawing || '';
				savedDrawing = drawing;
				inheritedFrom = data.inheritedFrom;
				loadedDate = day;
				try {
					const local = privateCacheUser() && localStorage.getItem(recoveryKey(day));
					if (local) {
						const recovery = JSON.parse(local);
						if (
							recovery.content !== data.content ||
							recovery.rich_document !== data.richDocument ||
							recovery.drawing !== data.drawing
						) {
							note = recovery.content;
							drawing = recovery.drawing;
							const r = recovery.rich_document ? JSON.parse(recovery.rich_document) : null;
							if (r) {
								richInitial = richLive = normalizeDocument(r.document);
								richChecks = r.checks || {};
								foldedBlocks = r.folds || {};
							}
							if (recovery.revision !== serverRevision) {
								conflict = true;
								error =
									'다른 화면의 저장 내용과 충돌합니다. 복구한 내용을 복사한 후 최신 메모를 불러와주세요.';
							}
						}
					}
				} catch {
					/* Ignore an invalid local recovery record. */
				}
				editing = true;
				requestAnimationFrame(restoreDrawing);
			})
			.catch((e) => {
				if (current === revision) error = e.message;
			})
			.finally(() => {
				if (current === revision) loading = false;
			});
	});
	async function saveNote() {
		if (loading || saving || !loadedDate || conflict) return;
		const content = note,
			day = loadedDate,
			ink = drawing,
			rich = richContent,
			expectedRevision = serverRevision,
			scope = revision;
		saving = true;
		error = '';
		try {
			const result = await request<{ revision: number }>(`/calendar/daily-notes/${day}`, {
				method: 'PUT',
				body: { content, drawing: ink, rich_document: rich, revision: expectedRevision }
			});
			if (loadedDate === day && scope === revision) {
				serverRevision = result.revision;
				saved = content;
				savedDrawing = ink;
				savedRich = rich;
				inheritedFrom = null;
				if (note === content && drawing === ink && richContent === rich) {
					try {
						localStorage.removeItem(recoveryKey(day));
					} catch {}
				}
			}
		} catch (e) {
			if (scope === revision) {
				if ((e as { status?: number }).status === 409) conflict = true;
				error = e instanceof Error ? e.message : '메모를 저장하지 못했습니다.';
			}
		} finally {
			saving = false;
		}
	}
	async function preserveConflict() {
		const day = loadedDate,
			scope = revision;
		try {
			await request(`/documents/note-conflict:${day}:${crypto.randomUUID()}`, {
				method: 'PUT',
				body: { revision: 0, data: { day, content: note, drawing, rich_document: richContent } }
			});
			if (scope !== revision) return;
			localStorage.removeItem(recoveryKey(day));
			conflict = false;
			retry++;
		} catch (e) {
			error = String(e);
		}
	}
	function context() {
		const ctx = inkCanvas?.getContext('2d');
		if (!ctx) return null;
		ctx.lineCap = 'round';
		ctx.lineJoin = 'round';
		ctx.lineWidth = erasing || hardwareEraser ? 20 : 2.5;
		ctx.strokeStyle = penColor;
		ctx.globalCompositeOperation = erasing || hardwareEraser ? 'destination-out' : 'source-over';
		return ctx;
	}
	function point(event: PointerEvent) {
		const rect = inkCanvas.getBoundingClientRect();
		return {
			x: (event.clientX - rect.left) * (inkCanvas.width / rect.width),
			y: (event.clientY - rect.top) * (inkCanvas.height / rect.height)
		};
	}
	function startPen(event: PointerEvent) {
		if (
			!inkCanvas ||
			loading ||
			loadedDate !== date ||
			activePointer !== null ||
			(penOnly && event.pointerType === 'touch')
		)
			return;
		event.preventDefault();
		activePointer = event.pointerId;
		hardwareEraser =
			event.button === 5 ||
			(event.buttons & 32) !== 0 ||
			(event.pointerType === 'pen' && (event.buttons & 2) !== 0);
		penActive = true;
		penPoint = point(event);
		inkCanvas.setPointerCapture(event.pointerId);
		const ctx = context();
		if (ctx) {
			ctx.beginPath();
			ctx.moveTo(penPoint.x, penPoint.y);
			ctx.lineTo(penPoint.x + 0.01, penPoint.y + 0.01);
			ctx.stroke();
		}
	}
	function drawPen(event: PointerEvent) {
		if (!penActive || !penPoint || event.pointerId !== activePointer) return;
		hardwareEraser =
			(event.buttons & 32) !== 0 || (event.pointerType === 'pen' && (event.buttons & 2) !== 0);
		const next = point(event);
		const ctx = context();
		if (!ctx) return;
		ctx.beginPath();
		ctx.moveTo(penPoint.x, penPoint.y);
		ctx.lineTo(next.x, next.y);
		ctx.stroke();
		penPoint = next;
	}
	function finishPen(event: PointerEvent) {
		if (!penActive || event.pointerId !== activePointer) return;
		activePointer = null;
		penActive = false;
		penPoint = null;
		hardwareEraser = false;
		if (inkCanvas.hasPointerCapture(event.pointerId))
			inkCanvas.releasePointerCapture(event.pointerId);
		drawing = inkCanvas.toDataURL('image/png');
	}
	function clearDrawing() {
		const ctx = context();
		if (!ctx) return;
		ctx.clearRect(0, 0, inkCanvas.width, inkCanvas.height);
		drawing = '';
	}
	function restoreDrawing() {
		const ctx = context();
		if (!ctx) return;
		ctx.clearRect(0, 0, inkCanvas.width, inkCanvas.height);
		if (!drawing) return;
		const image = new Image();
		const current = revision;
		image.onload = () => {
			if (current !== revision) return;
			ctx.save();
			ctx.globalCompositeOperation = 'source-over';
			ctx.drawImage(image, 0, 0, inkCanvas.width, inkCanvas.height);
			ctx.restore();
		};
		image.src = drawing;
	}
	function checkLine(index: number) {
		note = note
			.split('\n')
			.map((line, i) =>
				i === index
					? line.replace(
							/^(\s*- \[)([ xX])(\])/,
							(_, a, mark, b) => a + (mark === ' ' ? 'x' : ' ') + b
						)
					: line
			)
			.join('\n');
	}
</script>

<svelte:window
	onbeforeunload={(event) => {
		if (dirty) event.preventDefault();
	}}
/>
<aside class="daily-plan">
	<header>
		<div>
			<h2>오늘의 계획</h2>
		</div>
		<span>{date}</span>
	</header>
	<section class="plan-notes">
		<div class="note-heading">
			<strong>메모와 체크리스트</strong><button
				onclick={() => (editing = !editing)}
				disabled={loading}>{editing ? '미리보기' : '메모 편집'}</button
			>
		</div>
		<p>
			체크박스 버튼으로 할 일을 추가하세요. 서식 편집기의 토글 목록으로 제목 아래 내용을 접고 펼칠
			수 있습니다.
		</p>
		{#if inheritedFrom}<p class="note-carry">
				{inheritedFrom} 메모를 이어서 표시 중입니다. 저장하면 오늘 메모가 됩니다.
			</p>{/if}
		{#if !richLive}<button disabled={loading || loadedDate !== date} onclick={addCheckbox}
				>체크박스 추가</button
			><button disabled={loading || loadedDate !== date} onclick={useRich}>서식 편집기 사용</button
			>{:else}<button
				disabled={loading}
				onclick={() => {
					if (confirm('서식을 지우고 텍스트로 편집할까요?')) {
						richInitial = richLive = null;
						richChecks = {};
					}
				}}>텍스트로 편집</button
			>{/if}
		{#if richLive && richInitial}{#key loadedDate}<PersonalTextEditor
					initialValue={richInitial}
					readonly={loading || !editing}
					compact
					allowFolding
					{foldedBlocks}
					onfoldchange={(id, closed) => (foldedBlocks = { ...foldedBlocks, [id]: closed })}
					checkLabel="완료"
					questionChecks={richChecks}
					onquestionchange={(id, checked) => {
						richChecks = { ...richChecks, [id]: checked };
						if (richLive) richChanged(richLive);
					}}
					onchange={richChanged}
				/>{/key}
		{:else if editing}<textarea
				bind:this={noteInput}
				onbeforeinput={(e) => noteBeforeInput(e as InputEvent)}
				aria-label="메모와 체크리스트"
				id="daily-note"
				bind:value={note}
				disabled={loading || loadedDate !== date}
				placeholder={'# 프로젝트 이름\n- [ ] 세부 할 일\n\n오늘 기억할 내용'}
				rows="7"
			></textarea>{:else}<div class="note-preview">
				{#each note.split('\n') as line, index}{#if /^\s*- \[[ xX]\]/.test(line)}<label
							class="note-check"
							><input
								type="checkbox"
								checked={/^\s*- \[[xX]\]/.test(line)}
								onchange={() => checkLine(index)}
							/>{line.replace(/^\s*- \[[ xX]\]\s*/, '')}</label
						>{:else if /^#{1,3} /.test(line)}<h4>{line.replace(/^#{1,3} /, '')}</h4>{:else}<p>
							{line || '\u00a0'}
						</p>{/if}{/each}
			</div>{/if}
		<div class="note-save">
			<span role="status"
				>{loading
					? '불러오는 중…'
					: saving
						? '저장 중…'
						: dirty
							? '변경 내용 저장 대기'
							: '저장됨'}</span
			><button disabled={!dirty || saving || loading || conflict} onclick={saveNote}
				>{saving ? '저장 중…' : '지금 저장'}</button
			>
		</div>
		<details
			class="ink-note"
			open={inkOpen}
			ontoggle={(e) => {
				inkOpen = e.currentTarget.open;
				try {
					localStorage.setItem('ondo.ink-open', String(inkOpen));
				} catch {
					/* optional preference */
				}
			}}
		>
			<summary>펜 메모 · 접기/펼치기</summary>
			<div class="note-heading">
				<strong>펜 메모</strong><button
					type="button"
					disabled={loading}
					onclick={() => {
						if (confirm('펜 메모 전체를 지울까요?')) clearDrawing();
					}}>전체 지우기</button
				>
			</div>
			<details class="pen-tools">
				<summary>펜 도구</summary>
				<div class="pen-controls">
					<label><input type="checkbox" bind:checked={penOnly} />손가락 그리기 방지</label><label
						>펜 색 <input type="color" bind:value={penColor} aria-label="펜 색" /></label
					><button aria-pressed={!erasing} onclick={() => (erasing = false)}>펜</button><button
						aria-pressed={erasing}
						onclick={() => (erasing = true)}>지우개</button
					><small>Surface 펜 뒷면·S펜 버튼을 누르면 지우개로 전환됩니다.</small>
				</div>
			</details>
			<canvas
				bind:this={inkCanvas}
				width="640"
				height="220"
				aria-label="펜으로 작성하는 메모"
				onpointerdown={startPen}
				onpointermove={drawPen}
				onpointerup={finishPen}
				onpointercancel={finishPen}
				onlostpointercapture={finishPen}
				oncontextmenu={(e) => e.preventDefault()}
			></canvas>
		</details>
		{#if error}<p role="alert">{error}</p>
			{#if conflict}<button onclick={preserveConflict}
					>복구본을 별도 보존하고 최신 메모 불러오기</button
				>{/if}
			{#if loadedDate !== date}<button onclick={() => retry++}>메모 다시 불러오기</button>{/if}{/if}
	</section>
	<section>
		<h3>앞으로 7일 <small>기한이 지난 할 일 포함</small></h3>
		<label
			>보기 <select
				aria-label="일별 할 일 보기 방식"
				bind:value={taskMode}
				onchange={() => saveTaskMode(taskMode)}
				><option value="time">시간순</option><option value="theme">테마별</option></select
			></label
		>
		{#each taskGroups(soon, projects, taskMode) as group}<div class="plan-group">
				<h4>{group.name}</h4>
				{#each group.tasks as event (event.id)}{@render taskRow(event)}{/each}
			</div>{:else}<p class="plan-empty">일주일 안에 마감할 일이 없습니다.</p>{/each}
	</section>
	<details>
		<summary>그 이후의 할 일 <span>{later.length}</span></summary
		>{#each later as event (event.id)}{@render taskRow(event)}{:else}<p class="plan-empty">
				예정된 할 일이 없습니다.
			</p>{/each}
	</details>
	<details>
		<summary>아직 시작할 수 없는 할 일 <span>{waiting.length}</span></summary>
		{#each waiting as event (event.id)}{@render taskRow(event)}{/each}
	</details>
	{#each taskGroups(isolated, projects, 'time') as group}<details>
			<summary>{group.name} · {group.tasks.length}</summary
			>{#each group.tasks as event (event.id)}{@render taskRow(event)}{/each}
		</details>{/each}
</aside>
{#snippet taskRow(event: CalendarEvent)}
	<div class="cw-task" class:done={event.status === 'done'}>
		{#if event.completionSource !== 'external'}<input
				type="checkbox"
				aria-label={`${event.title} 완료`}
				checked={event.status === 'done'}
				disabled={pendingTasks.includes(event.id) || event.canEdit === false || taskWaiting(event)}
				onchange={() => oncomplete(event)}
			/>{:else}<span aria-label={event.status === 'done' ? '완료' : '연결된 서비스에서 완료'}
				>{event.status === 'done' ? '✓' : '·'}</span
			>{/if}
		<button onclick={() => onedit(event)}
			><small>{projects.find((p) => p.id === event.projectId)?.name || '내 일정'}</small><strong
				>{event.title}</strong
			>{#if event.description}<span class="task-detail">{event.description}</span>{/if}<small
				>{taskTiming(event)}</small
			></button
		>
	</div>
{/snippet}
