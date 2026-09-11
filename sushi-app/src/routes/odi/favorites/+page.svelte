<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { API_BASE as API } from '$lib/config/api';
	import { odiuser, session, template, type OdiSession, type OdiTemplate } from '$lib/odi/stores';
	import {
		figmaChevronDown,
		figmaClose,
		figmaDescription,
		figmaGroup,
		figmaModalClose,
		figmaPdf,
		figmaPlus,
		figmaSafetyGoggles,
		figmaSchedule,
		figmaSearch,
		figmaStylus,
		figmaTemplateInterview,
		figmaTemplatePresentation,
		figmaTemplateSeminar
	} from '$lib/odi/icons';

	type StoredTemplate = {
		template_id: string;
		template: OdiTemplate;
		created_at: string;
		updated_at: string;
	};
	type TemplateCard = StoredTemplate & {
		title: string;
		typeLabel: '발표' | '면접';
		placeLabel: string;
		durationLabel: string;
		audienceLabel: string;
		tags: string[];
		usedCount: number;
		lastUsedAt: string | null;
	};
	const PAGE_SIZE = 5;
	let templates = $state<StoredTemplate[]>([]),
		sessions = $state<OdiSession[]>([]);
	let loading = $state(true),
		errorMessage = $state(''),
		query = $state('');
	let typeFilter = $state<'all' | 'presentation' | 'interview'>('all'),
		sortOrder = $state<'recent' | 'used'>('recent'),
		currentPage = $state(1);
	let selected = $state<TemplateCard | null>(null),
		starting = $state(false),
		savingFavorite = $state<string | null>(null);

	const favoriteIds = $derived<string[]>(
		Array.isArray($odiuser?.config?.favorite_template_ids)
			? $odiuser.config.favorite_template_ids.filter(
					(value: unknown): value is string => typeof value === 'string'
				)
			: Array.isArray($odiuser?.config?.favorite_templates)
				? $odiuser.config.favorite_templates.filter(
						(value: unknown): value is string => typeof value === 'string'
					)
				: []
	);

	function dateText(value: string | null) {
		if (!value) return '사용 기록 없음';
		const parsed = new Date(value);
		return Number.isNaN(parsed.getTime())
			? '사용 기록 없음'
			: `마지막 사용 ${parsed.getFullYear()}.${parsed.getMonth() + 1}.${parsed.getDate()}`;
	}
	function makeCard(row: StoredTemplate): TemplateCard {
		const value = row.template;
		const related = sessions.filter(
			(item) => item.template_id === row.template_id && item.state === 'completed' && item.feedback
		);
		const lastUsedAt = related[0]?.ended_at ?? related[0]?.created_at ?? null;
		if (value.type === 'presentation') {
			const env = value.environment,
				audience = value.audience;
			return {
				...row,
				title: env.title || '제목 없는 발표 템플릿',
				typeLabel: '발표',
				placeLabel: env.place || '발표 환경 미설정',
				durationLabel: `발표 ${env.duration_minutes || 0}분 · Q&A ${env.question_count || 0}개`,
				audienceLabel: `청중 ${audience.audience_count || 0}인`,
				tags: [env.place, env.purpose]
					.filter((tag): tag is string => Boolean(tag?.trim()))
					.slice(0, 3),
				usedCount: related.length,
				lastUsedAt
			};
		}
		const env = value.environment;
		return {
			...row,
			title: env.position || env.company_name || '제목 없는 면접 템플릿',
			typeLabel: '면접',
			placeLabel: env.interview_context || '면접 환경 미설정',
			durationLabel: `소요 시간 ${env.duration_minutes || 0}분`,
			audienceLabel: `면접관 ${env.interviewer_count || 0}인`,
			tags: [env.company_name, env.position, env.interview_context]
				.filter((tag): tag is string => Boolean(tag?.trim()))
				.slice(0, 3),
			usedCount: related.length,
			lastUsedAt
		};
	}
	const allCards = $derived(templates.map(makeCard));
	const visibleCards = $derived.by(() => {
		const q = query.trim().toLowerCase();
		return [...allCards]
			.filter((item) => favoriteIds.includes(item.template_id))
			.filter((item) => typeFilter === 'all' || item.template.type === typeFilter)
			.filter((item) => !q || [item.title, ...item.tags].join(' ').toLowerCase().includes(q))
			.sort((a, b) =>
				sortOrder === 'used'
					? b.usedCount - a.usedCount || b.updated_at.localeCompare(a.updated_at)
					: (b.lastUsedAt ?? b.updated_at).localeCompare(a.lastUsedAt ?? a.updated_at)
			);
	});
	const pageCount = $derived(Math.max(1, Math.ceil(visibleCards.length / PAGE_SIZE)));
	const pagedCards = $derived(
		visibleCards.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
	);
	$effect(() => {
		typeFilter;
		query;
		sortOrder;
		currentPage = 1;
	});
	function iconFor(card: TemplateCard) {
		if (card.template.type === 'interview') return figmaTemplateInterview;
		if (card.placeLabel.includes('세미나') || card.placeLabel.includes('강의'))
			return figmaTemplateSeminar;
		return figmaTemplatePresentation;
	}
	async function load() {
		try {
			const user = await odiuser.requireUser();
			const [res, saved] = await Promise.all([
				fetch(`${API}/odi/db/users/${user.user_id}/templates`, { credentials: 'include' }),
				session.listMySessions(200)
			]);
			if (!res.ok) throw new Error('저장한 템플릿을 불러오지 못했습니다.');
			const data = await res.json();
			templates = Array.isArray(data.templates) ? data.templates : [];
			sessions = saved;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '즐겨찾기를 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}
	async function removeFavorite(card: TemplateCard) {
		const user = odiuser.get();
		if (!user || savingFavorite) return;
		savingFavorite = card.template_id;
		try {
			await odiuser.updateConfig({
				...user.config,
				favorite_template_ids: favoriteIds.filter((id) => id !== card.template_id)
			});
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '즐겨찾기 저장에 실패했습니다.';
		} finally {
			savingFavorite = null;
		}
	}
	async function useSelected(edit = false) {
		if (!selected || starting) return;
		starting = true;
		try {
			template.set(selected.template);
			await template.saveToRecent();
			await goto(`/odi/session/${selected.template.type}${edit ? '' : '/confirm'}`);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '템플릿을 불러오지 못했습니다.';
		} finally {
			starting = false;
		}
	}
	onMount(load);
</script>

<main class="favorites-page">
	<header class="page-header">
		<div>
			<p class="eyebrow">Favorites</p>
			<h1>즐겨찾는 템플릿</h1>
			<p class="subtitle">
				자주 사용하는 발표·면접 템플릿을 저장하고, 빠르게 불러와 연습을 시작해보세요.
			</p>
		</div>
		<button class="new-template" type="button" onclick={() => goto('/odi')}
			><span class="icon-26"><img src={figmaPlus} alt="" /></span><span>새 템플릿 만들기</span
			></button
		>
	</header>
	<div class="list-toolbar">
		<div class="type-tabs" role="tablist" aria-label="템플릿 종류">
			{#each [['all', '전체'], ['presentation', '발표'], ['interview', '면접']] as [value, label]}<button
					role="tab"
					aria-selected={typeFilter === value}
					class:active={typeFilter === value}
					type="button"
					onclick={() => (typeFilter = value as typeof typeFilter)}>{label}</button
				>{/each}
		</div>
		<div class="tools">
			<label class="sort-box"
				><span class="sr-only">정렬</span><select bind:value={sortOrder}
					><option value="recent">최신순</option><option value="used">사용 많은 순</option></select
				><span class="icon-24"><img src={figmaChevronDown} alt="" /></span></label
			><label class="search-box"
				><span class="sr-only">템플릿 검색</span><input
					bind:value={query}
					placeholder="템플릿 이름 또는 태그 검색"
				/><span class="icon-24"><img src={figmaSearch} alt="" /></span></label
			>
		</div>
	</div>
	{#if loading}<div class="state">템플릿을 불러오는 중입니다.</div>{:else if errorMessage}<div
			class="state error"
		>
			{errorMessage}<button type="button" onclick={load}>다시 시도</button>
		</div>{:else if visibleCards.length === 0}<div class="state">
			<strong>즐겨찾는 템플릿이 없습니다.</strong>
			<p>자주 쓰는 템플릿을 즐겨찾기에 추가해보세요.</p>
		</div>{:else}
		<section class="template-list" aria-label="즐겨찾는 템플릿 목록">
			{#each pagedCards as card (card.template_id)}<article class="template-row">
					<div class="identity">
						<span class="template-icon"><img src={iconFor(card)} alt="" /></span>
						<div class="identity-copy">
							<div class="title-line">
								<span class:interview={card.typeLabel === '면접'} class="type-chip"
									>{card.typeLabel}</span
								>
								<h2>{card.title}</h2>
							</div>
							<div class="tags">
								{#each card.tags as tag}<span>#{tag}</span>{/each}
							</div>
						</div>
					</div>
					<div class="session-info">
						<span
							><span class="icon-18"><img src={figmaSchedule} alt="" /></span
							>{card.durationLabel}</span
						><span
							><span class="icon-18"><img src={figmaGroup} alt="" /></span
							>{card.audienceLabel}</span
						>
					</div>
					<div class="usage">
						<span>{dateText(card.lastUsedAt)}</span><span>총 사용 {card.usedCount}회</span>
					</div>
					<div class="row-actions">
						<button class="start" type="button" onclick={() => (selected = card)}>바로 시작</button
						><button
							class="edit"
							type="button"
							onclick={() => {
								selected = card;
								void useSelected(true);
							}}>수정</button
						><button
							class="remove"
							type="button"
							aria-label={`${card.title} 즐겨찾기 해제`}
							disabled={savingFavorite === card.template_id}
							onclick={() => void removeFavorite(card)}
							><span class="icon-24"><img src={figmaClose} alt="" /></span></button
						>
					</div>
				</article>{/each}
		</section>{/if}
	<footer class="list-footer">
		<p>총 {visibleCards.length}개 템플릿</p>
		{#if pageCount > 1}<nav class="pagination" aria-label="페이지 이동">
				{#each Array(pageCount) as _, index}<button
						class:active={currentPage === index + 1}
						type="button"
						onclick={() => (currentPage = index + 1)}>{index + 1}</button
					>{/each}
			</nav>{/if}
	</footer>
	{#if selected}<div
			class="modal-backdrop"
			role="presentation"
			onclick={(event) => {
				if (event.target === event.currentTarget) selected = null;
			}}
		>
			<div
				class="template-modal"
				role="dialog"
				aria-modal="true"
				aria-labelledby="template-modal-title"
			>
				<button
					type="button"
					class="modal-close"
					aria-label="닫기"
					onclick={() => (selected = null)}
					><span class="icon-24"><img src={figmaModalClose} alt="" /></span></button
				>
				<div class="modal-title">
					<p>{selected.title}</p>
					<h2 id="template-modal-title">이전에 사용한 설정을 불러올까요?</h2>
				</div>
				<div class="modal-cards">
					<article>
						<h3>자료 업로드</h3>
						<div class="file-box">
							<img src={figmaPdf} alt="" /><span
								>{selected.template.files.slide?.original_name ?? '발표 슬라이드.pdf'}<small
									>2026. 06. 24 업로드</small
								></span
							>
						</div>
						<div class="file-box">
							<img src={figmaDescription} alt="" /><span
								>{selected.template.files.script?.original_name ?? '발표 스크립트.txt'}<small
									>2026. 06. 24 업로드</small
								></span
							>
						</div>
					</article>
					<article>
						<h3>청중 설정</h3>
						<dl>
							<div>
								<dt>유형</dt>
								<dd>혼합</dd>
							</div>
							<div>
								<dt>규모</dt>
								<dd>{selected.audienceLabel.replace(/[^0-9]/g, '') || '50'}명</dd>
							</div>
							<div>
								<dt>전문성</dt>
								<dd>보통</dd>
							</div>
							<div>
								<dt>관심도</dt>
								<dd>높음</dd>
							</div>
						</dl>
					</article>
				</div>
				<button class="modal-edit" type="button" onclick={() => void useSelected(true)}
					><span class="icon-24"><img src={figmaStylus} alt="" /></span>수정하기</button
				>
				<div class="modal-actions">
					<button type="button" onclick={() => (selected = null)}>취소하기</button><button
						class="primary"
						type="button"
						disabled={starting}
						onclick={() => void useSelected(false)}
						><span class="icon-30"><img src={figmaSafetyGoggles} alt="" /></span>{starting
							? '불러오는 중...'
							: '시작하기'}</button
					>
				</div>
			</div>
		</div>{/if}
</main>

<style>
	:global(*) {
		box-sizing: border-box;
	}
	.favorites-page {
		min-height: 100vh;
		width: 100%;
		padding: 36px 45px 40px 51px;
		background: #fff;
		color: #030812;
	}
	p,
	h1,
	h2,
	h3,
	dl,
	dd {
		margin: 0;
	}
	.page-header {
		display: flex;
		min-height: 140px;
		align-items: flex-start;
		justify-content: space-between;
	}
	.eyebrow {
		color: #03f;
		font-size: 20px;
		font-weight: 500;
		letter-spacing: -0.2px;
		line-height: 1.2;
	}
	h1 {
		margin-top: 24px;
		font-size: 42px;
		font-weight: 700;
		letter-spacing: -0.42px;
		line-height: 1.2;
	}
	.subtitle {
		margin-top: 8px;
		color: #81838f;
		font-size: 20px;
		font-weight: 500;
		letter-spacing: -0.2px;
	}
	.new-template {
		display: inline-flex;
		width: 212px;
		height: 50px;
		margin-top: 48px;
		align-items: center;
		justify-content: space-between;
		padding: 0 16px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
		color: #81838f;
		font: inherit;
		font-size: 18px;
		cursor: pointer;
	}
	.list-toolbar {
		position: relative;
		display: flex;
		min-height: 66px;
		align-items: flex-start;
		justify-content: space-between;
		border-bottom: 1px solid #d4d6e2;
	}
	.type-tabs {
		display: flex;
		gap: 4px;
		align-self: end;
	}
	.type-tabs button {
		width: 80px;
		height: 35px;
		padding: 0 0 12px;
		border: 0;
		border-bottom: 2px solid transparent;
		background: transparent;
		color: #81838f;
		font: inherit;
		font-size: 18px;
		font-weight: 500;
		cursor: pointer;
	}
	.type-tabs button.active {
		border-bottom-color: #03f;
		color: #03f;
		font-weight: 700;
	}
	.tools {
		display: flex;
		gap: 8px;
		padding-bottom: 16px;
	}
	.sort-box,
	.search-box {
		position: relative;
		display: flex;
		height: 50px;
		align-items: center;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
	}
	.sort-box {
		width: 142px;
	}
	.search-box {
		width: 280px;
	}
	select,
	input {
		width: 100%;
		height: 100%;
		border: 0;
		outline: 0;
		background: transparent;
		color: #81838f;
		font: inherit;
		font-size: 18px;
		letter-spacing: -0.18px;
		appearance: none;
	}
	select {
		padding: 0 48px 0 20px;
	}
	input {
		padding: 0 52px 0 20px;
	}
	.sort-box > .icon-24,
	.search-box > .icon-24 {
		position: absolute;
		right: 16px;
		pointer-events: none;
	}
	.template-list {
		display: grid;
		gap: 12px;
		padding-top: 16px;
	}
	.template-row {
		display: grid;
		width: 100%;
		min-height: 128px;
		grid-template-columns: minmax(430px, 1.25fr) minmax(240px, 0.85fr) minmax(175px, 0.52fr) auto;
		align-items: center;
		gap: 20px;
		padding: 24px 30px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
	}
	.identity {
		display: flex;
		min-width: 0;
		align-items: center;
		gap: 22px;
	}
	.template-icon {
		width: 48px;
		height: 48px;
		flex: 0 0 48px;
	}
	.template-icon img {
		width: 100%;
		height: 100%;
		display: block;
	}
	.identity-copy {
		min-width: 0;
		display: grid;
		gap: 8px;
	}
	.title-line {
		display: flex;
		min-width: 0;
		align-items: center;
		gap: 8px;
	}
	.title-line h2 {
		overflow: hidden;
		font-size: 22px;
		font-weight: 700;
		line-height: 1.35;
		letter-spacing: -0.22px;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.type-chip {
		flex: none;
		padding: 2px 9px;
		border-radius: 999px;
		background: rgba(128, 125, 254, 0.15);
		color: #4522c4;
		font-size: 18px;
		font-weight: 500;
	}
	.type-chip.interview {
		background: rgba(207, 255, 94, 0.28);
		color: #466700;
	}
	.tags {
		display: flex;
		gap: 4px;
		overflow: hidden;
	}
	.tags span {
		padding: 3px 8px;
		border: 1px solid #81838f;
		border-radius: 999px;
		color: #81838f;
		font-size: 14px;
		white-space: nowrap;
	}
	.session-info,
	.usage {
		display: flex;
		flex-direction: column;
		gap: 8px;
		color: #81838f;
		font-size: 14px;
	}
	.session-info > span {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.row-actions {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.row-actions > button {
		height: 42px;
		border-radius: 8px;
		font: inherit;
		font-size: 16px;
		font-weight: 500;
		cursor: pointer;
	}
	.row-actions .start {
		width: 96px;
		border: 1px solid #03f;
		background: #03f;
		color: #fff;
	}
	.row-actions .edit {
		width: 96px;
		border: 1px solid #d4d6e2;
		background: #fff;
		color: #81838f;
	}
	.row-actions .remove {
		display: grid;
		width: 32px;
		place-items: center;
		border: 0;
		background: transparent;
	}
	.list-footer {
		position: relative;
		min-height: 62px;
		padding-top: 20px;
		color: #81838f;
		font-size: 18px;
	}
	.pagination {
		position: absolute;
		top: 17px;
		left: 50%;
		display: flex;
		gap: 6px;
		transform: translateX(-50%);
	}
	.pagination button {
		width: 30px;
		height: 30px;
		border: 0;
		border-radius: 6px;
		background: transparent;
		color: #81838f;
		font: inherit;
		cursor: pointer;
	}
	.pagination button.active {
		background: #03f;
		color: #fff;
	}
	.state {
		min-height: 400px;
		display: grid;
		place-content: center;
		gap: 10px;
		color: #81838f;
		text-align: center;
	}
	.state button {
		justify-self: center;
		height: 40px;
		padding: 0 16px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
	}
	.state.error {
		color: #b44343;
	}
	.modal-backdrop {
		position: fixed;
		z-index: 50;
		inset: 0;
		display: grid;
		place-items: center;
		padding: 24px;
		background: rgba(0, 0, 0, 0.35);
	}
	.template-modal {
		position: relative;
		width: 536px;
		height: 500px;
		padding: 38px 18px 20px;
		border-radius: 16px;
		background: #fff;
		box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
	}
	.modal-close {
		position: absolute;
		top: 20px;
		right: 20px;
		display: grid;
		width: 24px;
		height: 24px;
		padding: 0;
		place-items: center;
		border: 0;
		background: transparent;
		cursor: pointer;
	}
	.modal-title {
		display: grid;
		justify-items: center;
		gap: 4px;
		line-height: 1.35;
		text-align: center;
	}
	.modal-title p {
		color: #03f;
		font-size: 18px;
		font-weight: 500;
	}
	.modal-title h2 {
		font-size: 24px;
		font-weight: 700;
		letter-spacing: -0.24px;
	}
	.modal-cards {
		display: grid;
		grid-template-columns: 244px 244px;
		gap: 12px;
		margin-top: 35px;
	}
	.modal-cards article {
		height: 228px;
		padding: 20px 11px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
	}
	.modal-cards h3 {
		margin: 0 8px 16px;
		font-size: 18px;
	}
	.file-box {
		height: 72px;
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 0 19px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		color: #81838f;
		font-size: 14px;
	}
	.file-box + .file-box {
		margin-top: 8px;
	}
	.file-box img {
		width: 36px;
		height: 36px;
		flex: none;
	}
	.file-box span {
		display: grid;
		gap: 4px;
	}
	.file-box small {
		color: #81838f;
		font-size: 12px;
	}
	dl {
		display: grid;
		gap: 10px;
	}
	dl > div {
		display: grid;
		grid-template-columns: 70px 1fr;
		align-items: center;
		color: #81838f;
		font-size: 14px;
	}
	dt {
		padding-left: 8px;
		border-left: 2px solid #d4d6e2;
	}
	dd {
		color: #030812;
	}
	.modal-edit {
		width: 500px;
		height: 50px;
		margin-top: 12px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		border: 0;
		border-radius: 8px;
		background: rgba(0, 51, 255, 0.1);
		color: #03f;
		font: inherit;
		font-size: 18px;
		cursor: pointer;
	}
	.modal-actions {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		margin-top: 12px;
	}
	.modal-actions button {
		height: 50px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
		color: #81838f;
		font: inherit;
		font-size: 18px;
		cursor: pointer;
	}
	.modal-actions .primary {
		border-color: #03f;
		background: #03f;
		color: #fff;
	}
	.icon-18,
	.icon-24,
	.icon-26,
	.icon-30 {
		display: inline-grid;
		flex: 0 0 auto;
		place-items: center;
	}
	.icon-18 {
		width: 18px;
		height: 18px;
	}
	.icon-24 {
		width: 24px;
		height: 24px;
	}
	.icon-26 {
		width: 26px;
		height: 26px;
	}
	.icon-30 {
		width: 30px;
		height: 30px;
	}
	.icon-18 img,
	.icon-24 img,
	.icon-26 img,
	.icon-30 img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
	}
	@media (max-width: 1200px) {
		.template-row {
			grid-template-columns: minmax(300px, 1fr) minmax(200px, 0.6fr) auto;
		}
		.usage {
			display: none;
		}
	}
	@media (max-width: 760px) {
		.favorites-page {
			padding: 26px 20px 40px;
		}
		.page-header {
			min-height: 190px;
			display: block;
		}
		.new-template {
			margin-top: 20px;
		}
		.subtitle {
			font-size: 16px;
			line-height: 1.5;
		}
		.list-toolbar {
			display: block;
		}
		.tools {
			padding-top: 14px;
		}
		.sort-box {
			width: 120px;
		}
		.search-box {
			flex: 1;
		}
		.template-row {
			grid-template-columns: 1fr;
			padding: 20px;
		}
		.session-info,
		.usage {
			display: flex;
		}
		.row-actions {
			justify-content: flex-end;
		}
		.template-modal {
			width: min(536px, 100%);
			height: auto;
		}
		.modal-cards {
			grid-template-columns: 1fr;
		}
		.modal-cards article {
			height: auto;
		}
		.modal-edit {
			width: 100%;
		}
	}
</style>
