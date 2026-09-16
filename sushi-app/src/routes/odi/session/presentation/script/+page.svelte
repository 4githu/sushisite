<script lang="ts">
	import { onMount } from 'svelte';
	import { template } from '$lib/odi/stores';
	import { API_BASE } from '$lib/config/api';
	import Button from '$lib/odi/components/common/Button.svelte';
	import SuggestionPanel from '$lib/odi/components/script/SuggestionPanel.svelte';
	import {
		applySuggestions,
		type ScriptAnalysis,
		type ScriptSection
	} from '$lib/odi/domain/scriptAnalysis';
	let text = $state(''),
		sections = $state<ScriptSection[]>([]),
		manual = $state(false),
		busy = $state(false),
		error = $state(''),
		notice = $state(''),
		version = $state(0),
		analysis = $state<ScriptAnalysis | null>(null),
		ready = $state(false),
		requestNumber = 0;
	const pageCount = $derived($template?.files.slide?.page_count ?? analysis?.page_count ?? 0);
	onMount(() => {
		text = $template?.files.script_content ?? '';
		sections = $template?.files.script_sections ?? [{ slide: 1, text }];
		manual = Boolean($template?.files.script_sections?.length);
		ready = true;
		if (text.trim()) void check();
	});
	function persist() {
		template.patchFiles({ script_content: text, script_sections: manual ? sections : undefined });
		version++;
	}
	function wholeChanged(value: string) {
		text = value.slice(0, 10000);
		sections = [{ slide: null, text }];
		manual = false;
		persist();
	}
	function sectionChanged(index: number, value: string) {
		const next = sections.map((s, i) => (i === index ? { ...s, text: value } : s));
		if (next.reduce((n, s) => n + s.text.length, 0) > 10000) {
			error = '스크립트는 최대 10,000자입니다.';
			return;
		}
		sections = next;
		text = sections.map((s) => s.text).join('');
		persist();
	}
	function move(i: number, delta: number) {
		const next = [...sections];
		[next[i], next[i + delta]] = [next[i + delta], next[i]];
		sections = next;
		text = sections.map((s) => s.text).join('');
		persist();
	}
	function useManual() {
		manual = true;
		if (!sections.length) sections = [{ slide: 1, text }];
		persist();
	}
	async function check() {
		if (!text.trim() || busy) return;
		const n = ++requestNumber,
			sent = text,
			sentVersion = version;
		busy = true;
		error = '';
		try {
			const res = await fetch(`${API_BASE}/odi/coaching/script/check`, {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					text: sent,
					version: sentVersion,
					slide_path: $template?.files.slide?.storage_path,
					sections: manual ? sections : null
				})
			});
			const data = await res.json();
			if (!res.ok)
				throw new Error(typeof data.detail === 'string' ? data.detail : '검사에 실패했습니다.');
			if (n !== requestNumber) return;
			analysis = data;
			if (text === sent && version === sentVersion) {
				sections = data.sections;
				template.patchFiles({ script_sections: sections });
			}
			notice = data.mapping_available
				? '슬라이드 자동 분배를 확인하고 필요하면 수정해 주세요.'
				: 'PDF 페이지를 읽을 수 없어 전체 스크립트를 검사했어요. 직접 슬라이드를 지정할 수 있습니다.';
		} catch (e) {
			error = e instanceof Error ? e.message : '검사 실패';
		} finally {
			if (n === requestNumber) busy = false;
		}
	}
	function apply(ids: string[]) {
		if (!analysis) return;
		try {
			if (analysis.version !== version)
				throw new Error('원문 또는 슬라이드 구성이 변경되었습니다. 다시 검사해 주세요.');
			sections = applySuggestions(analysis, ids, text);
			manual = true;
			text = sections.map((s) => s.text).join('');
			persist();
			analysis = null;
			notice = '제안을 적용했어요. 필요하면 다시 검사해 주세요.';
		} catch (e) {
			error = e instanceof Error ? e.message : '적용 실패';
		}
	}
	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
			notice = '스크립트를 복사했어요.';
		} catch {
			error = '클립보드에 복사하지 못했습니다.';
		}
	}
</script>

<svelte:head><title>스크립트 검사 | Re:hear</title></svelte:head>
<main class="odi-workspace">
	<header>
		<a href="/odi/session/presentation/upload">‹ 자료 업로드로 돌아가기</a>
		<h1>스크립트 검사하기</h1>
	</header>
	{#if ready}<div class="script-grid">
			<section class="surface editor">
				<div class="section-head">
					<h2>내 스크립트</h2>
					<Button variant="ghost" size="sm" onclick={copy}>복사</Button>
				</div>
				<div class="tabs">
					<button
						class:active={!manual}
						onclick={() => {
							manual = false;
							persist();
						}}>전체 입력</button
					><button class:active={manual} onclick={useManual}>슬라이드별 입력</button>
				</div>
				{#if manual}{#each sections as section, i (i)}<div class="section-editor">
							<div class="actions">
								<label
									>슬라이드 <input
										type="number"
										min="1"
										max={pageCount || 999}
										value={section.slide ?? i + 1}
										oninput={(e) => {
											sections = sections.map((s, j) =>
												j === i
													? {
															...s,
															slide: Math.max(
																1,
																Math.min(pageCount || 999, Number(e.currentTarget.value))
															)
														}
													: s
											);
											persist();
										}}
									/></label
								><button disabled={i === 0} onclick={() => move(i, -1)}>위로</button><button
									disabled={i === sections.length - 1}
									onclick={() => move(i, 1)}>아래로</button
								>
							</div>
							<textarea
								aria-label={`슬라이드 ${i + 1} 스크립트`}
								value={section.text}
								oninput={(e) => sectionChanged(i, e.currentTarget.value)}
								rows="6"
							></textarea>
						</div>{/each}<Button
						size="sm"
						variant="outline"
						onclick={() => {
							sections = [
								...sections,
								{ slide: Math.min(pageCount || 999, sections.length + 1), text: '' }
							];
							persist();
						}}>슬라이드 구간 추가</Button
					>{:else}<textarea
						class="whole"
						value={text}
						oninput={(e) => wholeChanged(e.currentTarget.value)}
						maxlength="10000"
						aria-label="전체 스크립트"
						placeholder="발표 스크립트를 입력하세요. PDF에 맞춰 슬라이드별로 자동 분배해 드려요."
					></textarea>{/if}
				<footer>
					<p>
						총 {text.length.toLocaleString()}자 · 예상 발표 시간 약 {Math.max(
							1,
							Math.round(text.replace(/\s/g, '').length / 320)
						)}분
					</p>
					<Button disabled={busy || !text.trim()} onclick={check}
						>{busy ? '검사 중…' : '다시 검사하기'}</Button
					>
				</footer>
			</section>
			{#if analysis}<SuggestionPanel
					{analysis}
					stale={analysis.source_text !== text || analysis.version !== version}
					onapply={apply}
				/>{:else}<section class="surface">
					<h2>{busy ? '스크립트를 분석하고 있어요' : '더 자연스러운 발표를 준비하세요'}</h2>
					<p class="muted">
						문장 길이, 두괄식 구조, 용어와 구어체 리듬을 살펴봅니다. 제안을 적용하기 전 원문과
						비교해 보세요.
					</p>
					{#if notice}<p role="status">{notice}</p>{/if}
				</section>{/if}
		</div>
		{#if error}<p class="error" role="alert">{error}</p>{/if}{/if}
</main>

<style>
	.script-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 24px;
		align-items: start;
	}
	.editor textarea {
		width: 100%;
		resize: vertical;
		line-height: 1.7;
		font-size: 15px;
	}
	.whole {
		min-height: 560px;
		margin: 18px 0;
	}
	.section-editor {
		margin: 18px 0;
	}
	.section-editor input {
		width: 75px;
	}
	.section-editor .actions {
		margin-bottom: 8px;
	}
	.section-editor button {
		background: none;
		border: 1px solid #dce0ea;
		padding: 6px 10px;
		border-radius: 6px;
	}
	footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px;
		margin-top: 20px;
	}
	footer p {
		font-size: 13px;
		color: #03f;
	}
	@media (max-width: 1100px) {
		.script-grid {
			grid-template-columns: 1fr;
		}
		.whole {
			min-height: 300px;
		}
	}
</style>
