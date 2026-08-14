<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import { API_BASE as API } from "$lib/config/api";
	import { odiuser, session, template, type OdiSession, type OdiTemplate } from "$lib/odi/stores";
	import { chair_alt, podium, school, voice_selection } from "$lib/odi/icons";

	type StoredTemplate = {
		template_id: string;
		template: OdiTemplate;
		created_at: string;
		updated_at: string;
	};

	type TemplateCard = StoredTemplate & {
		title: string;
		typeLabel: "발표" | "면접";
		placeLabel: string;
		durationLabel: string;
		audienceLabel: string;
		tags: string[];
		usedCount: number;
		lastUsedAt: string | null;
	};

	let templates = $state<StoredTemplate[]>([]);
	let sessions = $state<OdiSession[]>([]);
	let loading = $state(true);
	let errorMessage = $state("");
	let query = $state("");
	let typeFilter = $state<"all" | "presentation" | "interview">("all");
	let sortOrder = $state<"recent" | "used">("recent");
	let selected = $state<TemplateCard | null>(null);
	let starting = $state(false);
	let savingFavorite = $state<string | null>(null);

	const favoriteIds = $derived<string[]>(
		Array.isArray($odiuser?.config?.favorite_template_ids)
			? $odiuser.config.favorite_template_ids.filter((value: unknown): value is string => typeof value === "string")
			: Array.isArray($odiuser?.config?.favorite_templates)
				? $odiuser.config.favorite_templates.filter((value: unknown): value is string => typeof value === "string")
				: []
	);

	function dateText(value: string | null) {
		if (!value) return "사용 기록 없음";
		const parsed = new Date(value);
		return Number.isNaN(parsed.getTime())
			? "사용 기록 없음"
			: `마지막 사용 ${parsed.getFullYear()}.${parsed.getMonth() + 1}.${parsed.getDate()}`;
	}

	function makeCard(row: StoredTemplate): TemplateCard {
		const value = row.template;
		const relatedSessions = sessions.filter((item) => item.template_id === row.template_id);
		const lastUsedAt = relatedSessions[0]?.ended_at ?? relatedSessions[0]?.created_at ?? null;

		if (value.type === "presentation") {
			const environment = value.environment;
			const audience = value.audience;
			const tags = [environment.place, environment.purpose]
				.filter((tag): tag is string => Boolean(tag?.trim()))
				.slice(0, 3);
			return {
				...row,
				title: environment.title || "제목 없는 발표 템플릿",
				typeLabel: "발표",
				placeLabel: environment.place || "발표 환경 미설정",
				durationLabel: `발표 ${environment.duration_minutes || 0}분 · Q&A ${environment.question_count || 0}개`,
				audienceLabel: `청중 ${audience.audience_count || 0}인`,
				tags,
				usedCount: relatedSessions.length,
				lastUsedAt
			};
		}

		const environment = value.environment;
		const tags = [environment.company_name, environment.position, environment.interview_context]
			.filter((tag): tag is string => Boolean(tag?.trim()))
			.slice(0, 3);
		return {
			...row,
			title: environment.position || environment.company_name || "제목 없는 면접 템플릿",
			typeLabel: "면접",
			placeLabel: environment.interview_context || "면접 환경 미설정",
			durationLabel: `소요 시간 ${environment.duration_minutes || 0}분`,
			audienceLabel: `면접관 ${environment.interviewer_count || 0}인`,
			tags,
			usedCount: relatedSessions.length,
			lastUsedAt
		};
	}

	const allCards = $derived(templates.map(makeCard));
	const favoriteCards = $derived(allCards.filter((item) => favoriteIds.includes(item.template_id)));
	const visibleCards = $derived.by(() => {
		const normalized = query.trim().toLowerCase();
		return [...favoriteCards]
			.filter((item) => typeFilter === "all" || item.template.type === typeFilter)
			.filter((item) => !normalized || [item.title, ...item.tags].join(" ").toLowerCase().includes(normalized))
			.sort((left, right) => sortOrder === "used"
				? right.usedCount - left.usedCount || right.updated_at.localeCompare(left.updated_at)
				: (right.lastUsedAt ?? right.updated_at).localeCompare(left.lastUsedAt ?? left.updated_at));
	});

	function iconFor(card: TemplateCard) {
		if (card.template.type === "interview") return voice_selection;
		if (card.placeLabel.includes("학회")) return school;
		if (card.placeLabel.includes("강의")) return chair_alt;
		return podium;
	}

	async function load() {
		const user = odiuser.get();
		if (!user) {
			loading = false;
			errorMessage = "로그인 정보를 불러오지 못했습니다.";
			return;
		}

		try {
			const [templateResponse, savedSessions] = await Promise.all([
				fetch(`${API}/odi/db/users/${user.user_id}/templates`, { credentials: "include" }),
				session.listMySessions(200)
			]);
			if (!templateResponse.ok) throw new Error("저장한 템플릿을 불러오지 못했습니다.");
			const data = await templateResponse.json();
			templates = Array.isArray(data.templates) ? data.templates : [];
			sessions = savedSessions;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "즐겨찾기를 불러오지 못했습니다.";
		} finally {
			loading = false;
		}
	}

	async function toggleFavorite(card: TemplateCard) {
		const user = odiuser.get();
		if (!user || savingFavorite) return;
		savingFavorite = card.template_id;
		try {
			const next = favoriteIds.includes(card.template_id)
				? favoriteIds.filter((id) => id !== card.template_id)
				: [...favoriteIds, card.template_id];
			await odiuser.updateConfig({ ...user.config, favorite_template_ids: next });
			if (selected?.template_id === card.template_id && !next.includes(card.template_id)) selected = null;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "즐겨찾기 저장에 실패했습니다.";
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
			await goto(`/odi/session/${selected.template.type}${edit ? "" : "/confirm"}`);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "템플릿을 불러오지 못했습니다.";
		} finally {
			starting = false;
		}
	}

	async function addRecentTemplate() {
		const recent = odiuser.get()?.recent_template as OdiTemplate | null;
		if (!recent) return;
		template.set(recent);
		await goto(`/odi/session/${recent.type}`);
	}

	onMount(load);
</script>

<main class="favorites-page">
	<header class="page-header">
		<p class="eyebrow">Favorites</p>
		<div>
			<h1>즐겨찾는 템플릿</h1>
			<p>자주 사용하는 발표·면접 템플릿을 저장하고, 빠르게 불러와 연습을 시작해보세요.</p>
		</div>
		<button class="new-template" type="button" onclick={() => goto("/odi")}>＋ 새 템플릿 만들기</button>
	</header>

	<div class="toolbar">
		<div class="filter-tabs" aria-label="템플릿 종류">
			{#each [["all", "전체"], ["presentation", "발표"], ["interview", "면접"]] as [value, label]}
				<button type="button" class:active={typeFilter === value} onclick={() => typeFilter = value as typeof typeFilter}>{label}</button>
			{/each}
		</div>
		<label class="search"><span class="sr-only">템플릿 검색</span><input bind:value={query} placeholder="템플릿 이름 또는 태그 검색" /></label>
		<select bind:value={sortOrder} aria-label="정렬"><option value="recent">최신순</option><option value="used">사용 많은 순</option></select>
	</div>

	{#if loading}
		<div class="empty-state">즐겨찾는 템플릿을 불러오는 중입니다.</div>
	{:else if errorMessage}
		<div class="empty-state error">{errorMessage}<button type="button" onclick={load}>다시 시도</button></div>
	{:else if visibleCards.length === 0}
		<div class="empty-state">
			<strong>{favoriteCards.length ? "조건에 맞는 템플릿이 없습니다." : "아직 즐겨찾는 템플릿이 없습니다."}</strong>
			<p>저장된 템플릿의 별표를 눌러 이곳에 모아둘 수 있습니다.</p>
			{#if odiuser.get()?.recent_template}
				<button class="recent-button" type="button" onclick={addRecentTemplate}>최근 사용 설정 열기</button>
			{/if}
		</div>
	{:else}
		<p class="count">총 {visibleCards.length}개 템플릿</p>
		<section class="template-grid">
			{#each visibleCards as card (card.template_id)}
				<article class="template-card">
					<button class="card-main" type="button" onclick={() => selected = card}>
						<div class="card-heading"><img src={iconFor(card)} alt="" /><div><span class="type-chip">{card.typeLabel}</span><h2>{card.title}</h2></div></div>
						<div class="tags">{#each card.tags as tag}<span>#{tag}</span>{/each}</div>
						<div class="details"><span>{card.durationLabel}</span><span>{card.audienceLabel}</span></div>
						<div class="usage"><span>{dateText(card.lastUsedAt)}</span><span>총 사용 {card.usedCount}회</span></div>
					</button>
					<button class="favorite-button" class:marked={favoriteIds.includes(card.template_id)} type="button" aria-label="즐겨찾기 해제" disabled={savingFavorite === card.template_id} onclick={() => toggleFavorite(card)}>★</button>
					<div class="card-actions"><button type="button" onclick={() => selected = card}>바로 시작</button><button type="button" onclick={() => { selected = card; useSelected(true); }}>수정</button></div>
				</article>
			{/each}
		</section>
	{/if}

	{#if selected}
		<div class="modal-backdrop" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) selected = null; }}>
			<div class="template-modal" role="dialog" aria-modal="true" aria-labelledby="template-modal-title">
				<button type="button" class="close" aria-label="닫기" onclick={() => selected = null}>×</button>
				<p class="modal-label">{selected.typeLabel} 템플릿</p>
				<h2 id="template-modal-title">{selected.title}</h2>
				<p class="modal-copy">이전에 사용한 설정을 불러올까요?</p>
				<div class="modal-info"><div><b>자료 업로드</b><span>{selected.template.files.slide?.original_name ?? "발표 자료 없음"}</span><span>{selected.template.files.script?.original_name ?? "스크립트 없음"}</span></div><div><b>환경</b><span>{selected.placeLabel}</span><span>{selected.durationLabel}</span><span>{selected.audienceLabel}</span></div></div>
				<div class="modal-actions"><button type="button" onclick={() => useSelected(true)}>수정하기</button><button type="button" onclick={() => selected = null}>취소하기</button><button class="primary" type="button" disabled={starting} onclick={() => useSelected(false)}>{starting ? "불러오는 중..." : "시작하기"}</button></div>
			</div>
		</div>
	{/if}
</main>

<style>
	.favorites-page { width: 100%; min-height: 100vh; padding: 42px 52px 64px; color: var(--text-primary); background: var(--surface); }
	.page-header { display:grid; grid-template-columns: 1fr auto; gap: 16px 28px; align-items:end; padding-bottom: 30px; border-bottom:1px solid var(--cool-grey-light-active); }
	.eyebrow { grid-column:1/-1; margin:0; color:var(--primary); font-size:14px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
	h1,h2,p { margin:0; } h1 { font-size:30px; } .page-header div p { margin-top:9px; color:var(--text-secondary); }
	.new-template,.recent-button,.modal-actions button,.card-actions button,.empty-state button { border:1px solid var(--cool-grey-light-active); border-radius:10px; background:var(--surface); color:var(--text-primary); font:inherit; font-weight:600; cursor:pointer; }
	.new-template { height:44px; padding:0 18px; }
	.toolbar { display:flex; align-items:center; gap:12px; padding:26px 0; }
	.filter-tabs { display:flex; gap:4px; padding:4px; border-radius:10px; background:#f3f5f8; }
	.filter-tabs button { border:0; padding:8px 17px; border-radius:7px; color:var(--text-secondary); background:transparent; font:inherit; cursor:pointer; }.filter-tabs button.active { background:white; color:var(--primary); font-weight:700; box-shadow:0 1px 3px #0001; }
	.search { flex:1; min-width:180px; }.search input,select { box-sizing:border-box; width:100%; height:40px; padding:0 13px; border:1px solid var(--cool-grey-light-active); border-radius:8px; background:white; font:inherit; }.toolbar select { width:110px; }
	.count { margin-bottom:16px; color:var(--text-secondary); font-size:14px; }
	.template-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(310px,1fr)); gap:18px; }.template-card { position:relative; display:flex; flex-direction:column; min-height:270px; border:1px solid var(--cool-grey-light-active); border-radius:14px; background:white; overflow:hidden; box-shadow:0 2px 8px #0b12200a; }.card-main { flex:1; padding:22px; border:0; background:transparent; text-align:left; cursor:pointer; }.card-heading { display:flex; gap:14px; align-items:start; }.card-heading img { width:44px; height:44px; padding:8px; border-radius:8px; background:#eeeeff; }.type-chip { display:inline-block; color:#5426c7; font-size:13px; font-weight:700; }.card-heading h2 { margin-top:4px; font-size:19px; }.tags { display:flex; flex-wrap:wrap; gap:6px; min-height:26px; margin:16px 0; }.tags span { padding:5px 8px; border-radius:999px; background:#f2f4f7; color:var(--text-secondary); font-size:12px; }.details,.usage { display:flex; flex-wrap:wrap; gap:8px 14px; color:var(--text-secondary); font-size:13px; }.usage { justify-content:space-between; margin-top:20px; font-size:12px; }.favorite-button { position:absolute; top:15px; right:14px; border:0; background:none; color:#b2b6bd; font-size:25px; cursor:pointer; }.favorite-button.marked { color:#f2b640; }.card-actions { display:flex; gap:8px; padding:0 18px 18px; }.card-actions button { flex:1; height:38px; }.card-actions button:first-child,.modal-actions .primary { border-color:var(--primary); background:var(--primary); color:white; }
	.empty-state { display:flex; min-height:260px; flex-direction:column; align-items:center; justify-content:center; gap:11px; border:1px dashed var(--cool-grey-light-active); border-radius:14px; color:var(--text-secondary); text-align:center; }.empty-state.error { color:#b44343; }.empty-state button { padding:9px 14px; }.modal-backdrop { position:fixed; z-index:20; inset:0; display:grid; place-items:center; padding:24px; background:#07102280; }.template-modal { position:relative; width:min(660px,100%); padding:38px; border-radius:16px; background:white; box-shadow:0 20px 80px #0004; }.close { position:absolute; top:16px; right:18px; border:0; background:none; font-size:28px; cursor:pointer; }.modal-label { color:var(--primary); font-size:14px; font-weight:700; }.template-modal h2 { margin-top:8px; font-size:27px; }.modal-copy { margin-top:8px; color:var(--text-secondary); }.modal-info { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:26px; }.modal-info div { display:flex; flex-direction:column; gap:8px; padding:16px; border-radius:10px; background:#f7f8fa; }.modal-info span { color:var(--text-secondary); font-size:14px; }.modal-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:28px; }.modal-actions button { min-height:40px; padding:0 14px; }.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }
	@media (max-width:720px) { .favorites-page{padding:28px 20px 48px}.page-header{grid-template-columns:1fr}.new-template{justify-self:start}.toolbar{align-items:stretch; flex-wrap:wrap}.filter-tabs{width:100%}.search{order:2; width:100%}.toolbar select{order:2; width:auto}.modal-info{grid-template-columns:1fr}.modal-actions{flex-wrap:wrap}.modal-actions .primary{flex:1}.template-modal{padding:30px 20px 20px} }
</style>
