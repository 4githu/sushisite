<script lang="ts">
	import type { StoredTemplate } from '$lib/odi/domain/templates';
	import { templateTitle } from '$lib/odi/domain/templates';
	import Button from '../common/Button.svelte';
	let {
		row,
		onclose,
		onedit,
		onstart
	}: { row: StoredTemplate; onclose: () => void; onedit: () => void; onstart: () => void } =
		$props();
	function openDialog(node: HTMLDialogElement) {
		node.showModal();
	}
</script>

<dialog {@attach openDialog} {onclose} aria-labelledby="template-detail-title">
	<h2 id="template-detail-title">{templateTitle(row.template)}</h2>
	<p>저장된 기본 환경을 불러옵니다. 이번 세션에서만 수정할 수도 있어요.</p>
	<div class="details">
		<section>
			<h3>발표 자료와 스크립트</h3>
			<p>{row.template.files.slide?.original_name ?? '등록된 발표 자료 없음'}</p>
			<p>{row.template.files.paper?.original_name ?? '참고 자료 없음'}</p>
			<p>스크립트 {row.template.files.script_content?.length ?? 0}자</p>
		</section>
		<section>
			<h3>환경 설정</h3>
			{#each Object.entries(row.template.environment) as [key, value], rowIndex0 (rowIndex0)}{#if value}<p
					>
						<span
							>{(
								{
									title: '주제',
									purpose: '목적',
									language: '언어',
									place: '장소',
									duration_minutes: '시간(분)',
									question_count: '질문 수',
									company_name: '회사',
									position: '직무',
									department: '부서',
									interviewer_count: '면접관 수',
									job_detail: '직무 내용',
									interview_context: '면접 상황',
									answer_order: '답변 순서'
								} as Record<string, string>
							)[key] ?? key}</span
						>
						{String(value)}
					</p>{/if}{/each}{#if row.template.type === 'presentation'}<p>
					청중 {row.template.audience.audience_count}명 · {row.template.audience.audience_type}
				</p>
				<p>
					전문성 {row.template.audience.expertise_level} · 관심도 {row.template.audience
						.interest_level}
				</p>{/if}
		</section>
	</div>
	<div class="actions">
		<Button variant="ghost" onclick={onclose}>닫기</Button><Button
			variant="outline"
			onclick={onedit}>이번 세션 설정 수정</Button
		><Button onclick={onstart}>이 환경으로 세션 시작</Button>
	</div>
</dialog>

<style>
	dialog {
		border: 1px solid #dce0ea;
		border-radius: 20px;
		width: min(760px, 90vw);
		padding: 32px;
		color: var(--text-primary);
		max-height: 85vh;
	}
	dialog::backdrop {
		background: #05063288;
	}
	h2 {
		font-size: 26px;
	}
	p {
		color: var(--text-secondary);
		font-size: 14px;
	}
	.details {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
		margin: 24px 0;
	}
	.details section {
		background: #f6f7fc;
		padding: 18px;
		border-radius: 10px;
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		flex-wrap: wrap;
	}
	@media (max-width: 600px) {
		.details {
			grid-template-columns: 1fr;
		}
	}
</style>
