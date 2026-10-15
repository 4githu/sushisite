<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '../shared/api';
	import RuleFields from './RuleFields.svelte';
	import PersonalTextEditor from '../editor/PersonalTextEditor.svelte';
	import { createDocument, createTextBlock } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	let {
		ruleId,
		official,
		track,
		onselect
	}: { ruleId: string; official: any; track: string; onselect: (rule: any) => void } = $props();
	let edition = $state('official'),
		revision = $state(0),
		custom = $state<any>(null),
		editing = $state(false),
		error = $state(''),
		busy = $state(false),
		history = $state<{ revision: number; data: any; created_at: string }[]>([]),
		draft = $state<any>(null),
		notes = $state<EditorDocument>(createDocument()),
		notesInitial = $state<EditorDocument>(createDocument());
	const key = () => `rule:${ruleId}`;
	onMount(() => {
		void load();
	});
	async function load() {
		try {
			const [r, p] = await Promise.all([
				request<{ data: any; revision: number }>(`/student/rules/${ruleId}/versions`),
				request<{ data: any; revision: number }>(`/documents/rule-choice:${ruleId}`)
			]);
			custom = r.data;
			revision = r.revision;
			if (p.data?.edition === 'custom' && custom) {
				edition = 'custom';
				onselect(custom);
			}
		} catch (e) {
			error = String(e);
		}
	}
	async function choose(next: string) {
		edition = next;
		onselect(next === 'custom' ? custom : official);
		try {
			const p = await request<{ revision: number }>(`/documents/rule-choice:${ruleId}`);
			await request(`/documents/rule-choice:${ruleId}`, {
				method: 'PUT',
				body: { revision: p.revision, data: { edition } }
			});
		} catch (e) {
			error = String(e);
		}
	}
	function edit() {
		draft = structuredClone($state.snapshot(edition === 'custom' ? custom : official));
		notes = draft.notes_document || createDocument();
		if (!draft.notes_document)
			notes.blocks = (draft.notes || []).map((n: string) => createTextBlock('paragraph', n));
		notesInitial = notes;
		editing = true;
	}
	async function save() {
		busy = true;
		error = '';
		try {
			draft.notes = notes.blocks.flatMap((b) =>
				b.type === 'table' ? [] : [b.children.map((c) => c.text).join('')]
			);
			draft.notes_document = notes;
			const result = await request<{ revision: number }>(`/student/rules/${ruleId}/versions`, {
				method: 'PUT',
				body: { revision, data: draft }
			});
			revision = result.revision;
			custom = draft;
			editing = false;
			await choose('custom');
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
</script>

<div class="rule-versions">
	<div class="actions">
		<label
			>계산에 사용할 규정 <select value={edition} onchange={(e) => choose(e.currentTarget.value)}
				><option value="official">공식 데이터</option>{#if custom}<option value="custom"
						>사용자 수정본 · {revision}판</option
					>{/if}</select
			></label
		><button onclick={edit}>기존 규정 편집</button><button
			onclick={async () => {
				try {
					history = await request(`/student/rules/${ruleId}/history`);
				} catch (e) {
					error = String(e);
				}
			}}>변경 이력</button
		>
	</div>
	{#if error}<p role="alert">{error}</p>{/if}
	{#if editing && draft}<section>
			<h3>사용자 규정 수정본</h3>
			<p>수정본은 다른 회원도 조회할 수 있습니다. 공식 데이터는 보존됩니다.</p>
			<RuleFields
				label="졸업 총학점"
				value={draft.total_credits}
				onchange={(v) => (draft = { ...draft, total_credits: v })}
			/>{#each draft.tracks as t, i}{#if t.key === track}<RuleFields
						label={t.name}
						value={t}
						onchange={(v) =>
							(draft = {
								...draft,
								tracks: draft.tracks.map((x: any, j: number) => (i === j ? v : x))
							})}
					/>{#if !t.required}<button
							onclick={() =>
								(draft = {
									...draft,
									tracks: draft.tracks.map((x: any, j: number) =>
										i === j
											? { ...x, required: { all: [], pool: [], min_courses: 0, min_credits: 0 } }
											: x
									)
								})}>필수·선택 과목 조건 추가</button
						>{/if}{/if}{/each}
			<h4>규정 설명</h4>
			<PersonalTextEditor initialValue={notesInitial} onchange={(v) => (notes = v)} /><button
				disabled={busy}
				onclick={save}>새 판본 저장하고 계산에 적용</button
			><button onclick={() => (editing = false)}>취소</button>
		</section>{/if}
	{#each history as h}<p>
			{h.revision}판 · {h.created_at}<button
				onclick={() => {
					draft = h.data;
					notes = draft.notes_document || createDocument();
					notesInitial = notes;
					editing = true;
				}}>이 판본으로 복원해 편집</button
			>
		</p>{/each}
</div>

<style>
	.rule-versions {
		border-block: 1px solid #8884;
		padding: 16px 0;
		margin: 20px 0;
	}
	.actions {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
		align-items: center;
	}
	section {
		margin: 16px 0;
	}
	button {
		margin: 6px 6px 6px 0;
	}
</style>
