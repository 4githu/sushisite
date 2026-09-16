<script lang="ts">
	import type { ScriptAnalysis } from '$lib/odi/domain/scriptAnalysis';
	import Button from '../common/Button.svelte';
	let {
		analysis,
		stale = false,
		onapply
	}: { analysis: ScriptAnalysis; stale?: boolean; onapply: (ids: string[]) => void } = $props();
	const categories = [
		{ id: 'length', label: '문장 길이 줄이기' },
		{ id: 'structure', label: '두괄식 구조 개선' },
		{ id: 'terms', label: '직관적 용어 사용' },
		{ id: 'rhythm', label: '구어체 리듬 보완' }
	];
	let category = $state('length'),
		selected = $derived.by<string[]>(() => {
			analysis;
			return [];
		});

	const visible = $derived(analysis.suggestions.filter((s) => s.category === category));
</script>

<section class="surface suggestions">
	<h2>수정 제안 <span class="chip">{analysis.suggestions.length}문장</span></h2>
	<div class="categories">
		{#each categories as item, rowIndex0 (rowIndex0)}<button
				class:active={category === item.id}
				onclick={() => (category = item.id)}
				><strong>{item.label}</strong><small
					>{analysis.suggestions.filter((s) => s.category === item.id).length}문장</small
				></button
			>{/each}
	</div>
	<div class="toolbar">
		<h3>{categories.find((c) => c.id === category)?.label}</h3>
		<div class="actions">
			<Button
				size="sm"
				variant="outline"
				disabled={stale || !selected.length}
				onclick={() => onapply(selected)}>선택 항목 적용하기</Button
			><Button
				size="sm"
				disabled={stale || !analysis.suggestions.length}
				onclick={() => onapply(analysis.suggestions.map((s) => s.id))}>모두 적용하기</Button
			>
		</div>
	</div>
	{#if stale}<p role="status" class="error">
			원문이 변경되었어요. 다시 검사해 주세요.
		</p>{/if}{#each visible as suggestion (suggestion.id)}<article>
			<label
				><input
					type="checkbox"
					checked={selected.includes(suggestion.id)}
					onchange={() =>
						(selected = selected.includes(suggestion.id)
							? selected.filter((id) => id !== suggestion.id)
							: [...selected, suggestion.id])}
					disabled={stale}
				/> 수정 제안 선택</label
			>
			<div class="original">
				<span>원문</span>
				<p>{suggestion.original}</p>
			</div>
			<div class="replacement">
				<span>제안</span>
				<p>{suggestion.replacement}</p>
			</div>
		</article>{:else}<p class="state">이 항목에 수정 제안이 없어요.</p>{/each}
</section>

<style>
	.categories {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 8px;
	}
	.categories button {
		background: white;
		border: 1px solid #dce0ea;
		border-radius: 8px;
		padding: 22px 8px;
		color: #596174;
		font-size: 13px;
	}
	.categories button.active {
		border-color: #03f;
		background: #f5f6ff;
	}
	.categories small {
		display: block;
		margin-top: 10px;
	}
	article {
		margin: 20px 0;
	}
	label {
		font-size: 12px;
		color: #7a8499;
	}
	.original,
	.replacement {
		display: flex;
		align-items: stretch;
		gap: 12px;
		margin: 10px 0;
		border-radius: 8px;
		background: #f7f8fa;
	}
	.replacement {
		background: #f0f3ff;
		color: #03f;
	}
	.original > span,
	.replacement > span {
		writing-mode: vertical-rl;
		padding: 14px 7px;
		background: #e9ecf3;
		border-radius: 8px;
		font-size: 11px;
	}
	p {
		padding: 12px;
		font-size: 14px;
		white-space: pre-wrap;
		margin: 0;
	}
	.replacement > span {
		background: #dce3ff;
	}
	@media (max-width: 700px) {
		.categories {
			grid-template-columns: 1fr 1fr;
		}
	}
</style>
