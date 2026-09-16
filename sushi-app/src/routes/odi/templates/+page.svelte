<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { API_BASE } from '$lib/config/api';
	import { odiuser, template } from '$lib/odi/stores';
	import TemplateCard from '$lib/odi/components/templates/TemplateCard.svelte';
	import TemplateDetailModal from '$lib/odi/components/templates/TemplateDetailModal.svelte';
	import Button from '$lib/odi/components/common/Button.svelte';
	import { templateTitle, type StoredTemplate } from '$lib/odi/domain/templates';
	let rows = $state<StoredTemplate[]>([]),
		loading = $state(true),
		error = $state(''),
		query = $state(''),
		favoritesOnly = $state(false),
		kind = $state('all'),
		sort = $state('recent'),
		page = $derived.by(() => {
			query;
			favoritesOnly;
			kind;
			sort;
			count;
			return 1;
		}),
		busy = $state(''),
		selected = $state<StoredTemplate | null>(null);
	const favoriteIds = $derived<string[]>(
		$odiuser?.config?.favorite_template_ids ?? $odiuser?.config?.favorite_templates ?? []
	);
	const filtered = $derived(
		rows
			.filter(
				(r) =>
					(!favoritesOnly || favoriteIds.includes(r.template_id)) &&
					(kind === 'all' || r.template.type === kind) &&
					templateTitle(r.template).toLowerCase().includes(query.toLowerCase())
			)
			.toSorted((a, b) =>
				sort === 'used'
					? b.use_count - a.use_count ||
						(b.last_used_at ?? b.updated_at).localeCompare(a.last_used_at ?? a.updated_at)
					: (b.last_used_at ?? b.updated_at).localeCompare(a.last_used_at ?? a.updated_at)
			)
	);
	const count = $derived(Math.max(1, Math.ceil(filtered.length / 5)));
	async function load() {
		loading = true;
		error = '';
		try {
			const user = await odiuser.requireUser();
			const res = await fetch(`${API_BASE}/odi/db/users/${user.user_id}/templates`, {
				credentials: 'include'
			});
			if (!res.ok) throw new Error('템플릿을 불러오지 못했습니다.');
			rows = (await res.json()).templates;
		} catch (e) {
			error = e instanceof Error ? e.message : '불러오기 실패';
		} finally {
			loading = false;
		}
	}
	async function toggle(row: StoredTemplate) {
		if (busy) return;
		busy = row.template_id;
		try {
			await odiuser.updateConfig({
				...$odiuser?.config,
				favorite_template_ids: favoriteIds.includes(row.template_id)
					? favoriteIds.filter((id) => id !== row.template_id)
					: [...favoriteIds, row.template_id]
			});
		} catch (e) {
			error = e instanceof Error ? e.message : '즐겨찾기 저장 실패';
		} finally {
			busy = '';
		}
	}
	function use(row: StoredTemplate, edit = false) {
		template.loadSaved({ ...row.template, id: row.template_id, version: row.version });
		void goto(`/odi/session/${row.template.type}${edit ? '' : '/confirm'}`);
	}
	function create() {
		template.setDefault('presentation');
		void goto('/odi/session/presentation');
	}
	onMount(load);
</script>

<svelte:head><title>템플릿 | Re:hear</title></svelte:head>
<main class="odi-workspace">
	<header class="section-head">
		<div>
			<p class="eyebrow">Templates</p>
			<h1>나의 환경 템플릿</h1>
			<p class="muted">사용했던 환경을 모아 보고, 나에게 맞는 설정으로 바로 시작하세요.</p>
		</div>
		<Button onclick={create}>새 환경 만들기</Button>
	</header>
	<div class="toolbar">
		<div class="tabs">
			<button class:active={!favoritesOnly} onclick={() => (favoritesOnly = false)}
				>전체 템플릿</button
			><button class:active={favoritesOnly} onclick={() => (favoritesOnly = true)}>즐겨찾기</button>
		</div>
		<div class="actions">
			<select bind:value={kind} aria-label="템플릿 종류"
				><option value="all">전체 종류</option><option value="presentation">발표</option><option
					value="interview">면접</option
				></select
			><input bind:value={query} placeholder="템플릿 이름 검색" aria-label="템플릿 검색" /><select
				bind:value={sort}
				aria-label="정렬"
				><option value="recent">최근 사용순</option><option value="used">사용 횟수순</option
				></select
			>
		</div>
	</div>
	{#if error}<p role="alert" class="error">{error}</p>
		<Button onclick={load}>다시 시도</Button>{/if}
	{#if loading}<p class="state">환경을 불러오는 중…</p>{:else if !filtered.length}<div
			class="state"
		>
			<h2>{favoritesOnly ? '즐겨찾는 환경이 없어요' : '표시할 환경이 없어요'}</h2>
			<p>새 환경을 만들거나 검색 조건을 바꿔 보세요.</p>
		</div>{:else}<div class="list">
			{#each filtered.slice((page - 1) * 5, page * 5) as row (row.template_id)}<TemplateCard
					{row}
					favorite={favoriteIds.includes(row.template_id)}
					busy={busy === row.template_id}
					onfavorite={() => toggle(row)}
					onselect={() => (selected = row)}
					onedit={() => use(row, true)}
				/>{/each}
		</div>{/if}
	<footer class="pagination">
		{#each Array(count) as _, i (i)}<button
				class:active={page === i + 1}
				onclick={() => (page = i + 1)}>{i + 1}</button
			>{/each}
	</footer>
	<p class="muted">총 {filtered.length}개 템플릿</p>
	{#if selected}<TemplateDetailModal
			row={selected}
			onclose={() => (selected = null)}
			onedit={() => selected && use(selected, true)}
			onstart={() => selected && use(selected)}
		/>{/if}
</main>
