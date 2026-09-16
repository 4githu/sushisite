<script lang="ts">
	import type { StoredTemplate } from '$lib/odi/domain/templates';
	import { templateTitle } from '$lib/odi/domain/templates';
	import { figmaTemplatePresentation, figmaTemplateInterview, kid_star } from '$lib/odi/icons';
	import Button from '../common/Button.svelte';
	let {
		row,
		favorite = false,
		busy = false,
		onfavorite,
		onselect,
		onedit
	}: {
		row: StoredTemplate;
		favorite?: boolean;
		busy?: boolean;
		onfavorite: () => void;
		onselect: () => void;
		onedit: () => void;
	} = $props();
</script>

<article class="surface template-card">
	<img
		class="type-icon"
		src={row.template.type === 'presentation' ? figmaTemplatePresentation : figmaTemplateInterview}
		alt=""
	/>
	<div class="identity">
		<span class="chip">{row.template.type === 'presentation' ? '발표' : '면접'}</span>
		<h3>{templateTitle(row.template)}</h3>
		<p class="muted">
			{row.template.environment.duration_minutes}분 · {row.template.type === 'presentation'
				? `${row.template.audience.audience_count}인 · ${row.template.environment.place}`
				: `${row.template.environment.interviewer_count}인`}
		</p>
	</div>
	<div class="muted usage">
		<p>
			{row.last_used_at
				? `최근 사용 ${new Date(row.last_used_at).toLocaleDateString('ko-KR')}`
				: '아직 사용하지 않은 환경'}
		</p>
		<span>총 사용 {row.use_count ?? 0}회</span>
	</div>
	<div class="actions">
		<Button size="sm" onclick={onselect}>이 환경으로 시작</Button><Button
			size="sm"
			variant="outline"
			onclick={onedit}>수정</Button
		><button
			class:favorite
			onclick={onfavorite}
			disabled={busy}
			aria-pressed={favorite}
			aria-label={`${templateTitle(row.template)} 즐겨찾기 ${favorite ? '해제' : '추가'}`}
			><img src={kid_star} alt="" /></button
		>
	</div>
</article>

<style>
	.template-card {
		display: flex;
		gap: 20px;
		align-items: center;
	}
	.type-icon {
		width: 46px;
		height: 46px;
	}
	.identity {
		flex: 1;
		min-width: 150px;
	}
	h3 {
		margin-top: 8px !important;
	}
	p {
		margin: 6px 0;
		font-size: 14px;
	}
	.usage {
		font-size: 13px;
	}
	.actions > button {
		border: 1px solid #dce0ea;
		background: white;
		border-radius: 8px;
		padding: 10px;
	}
	.actions > button.favorite {
		background: #cfff5e;
	}
	.actions > button img {
		width: 22px;
		height: 22px;
	}
	@media (max-width: 1100px) {
		.template-card {
			flex-wrap: wrap;
		}
		.usage {
			width: 100%;
		}
	}
</style>
