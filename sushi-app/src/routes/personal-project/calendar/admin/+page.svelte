<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	import '$lib/personal-project/student/student.css';
	type Data = {
		total: number;
		page: number;
		users: { id: number; name: string; email: string }[];
		boards: { id: number; name: string; restricted: number }[];
		permissions: { user_id: number; scope: string; action: string; allowed: number }[];
		audit: { id: number; actor: number; action: string; target: string; created_at: string }[];
	};
	let data = $state<Data | null>(null),
		memberPage = $state(1),
		q = $state(''),
		error = $state(''),
		busy = $state(false),
		selected = $state<number>(),
		boardId = $state<number>(),
		action = $state('read'),
		allowed = $state('allow');
	async function load() {
		data = await request<Data>(`/admin/workspace?q=${encodeURIComponent(q)}&page=${memberPage}`);
		boardId ??= data.boards[0]?.id;
	}
	async function run(fn: () => Promise<void>) {
		busy = true;
		error = '';
		try {
			await fn();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	onMount(() => {
		void run(load);
	});
</script>

<svelte:head><title>워크스페이스 관리 · NETAQ</title></svelte:head>
<div class="student-page">
	<h1>워크스페이스 관리</h1>
	<p>게시판 공개 범위, 회원별 접근 권한, 변경 기록을 관리합니다.</p>
	{#if error}<p role="alert">{error}</p>{/if}
	{#if data}<section>
			<h2>게시판 공개 범위</h2>
			<p>
				제한 게시판은 해당 게시판의 읽기 권한을 부여받은 회원과 관리자만 열람합니다.
				글·댓글·첨부파일에도 같은 제한이 적용됩니다.
			</p>
			{#each data.boards as b}<div class="row">
					<a href={`/personal-project/calendar/boards?board=${b.id}`}>{b.name}</a><label
						><input
							type="checkbox"
							checked={!!b.restricted}
							disabled={busy}
							onchange={(e) => {
								const restricted = e.currentTarget.checked;
								void run(async () => {
									await request(`/admin/boards/${b.id}/restriction`, {
										method: 'PUT',
										body: { restricted }
									});
									await load();
								});
							}}
						/>권한 있는 회원만</label
					>
				</div>{/each}
		</section>
		<section>
			<h2>회원별 권한</h2>
			<form
				onsubmit={(e) => {
					e.preventDefault();
					memberPage = 1;
					void run(load);
				}}
			>
				<input
					aria-label="회원 검색"
					bind:value={q}
					placeholder="공란으로 검색하면 전체 회원"
				/><button disabled={busy}>회원 검색</button>
			</form>
			{#each data.users as u}<button
					class:selected={selected === u.id}
					onclick={() => (selected = u.id)}>{u.name} · {u.email}</button
				>{/each}
			<nav aria-label="회원 목록 페이지">
				<button
					disabled={busy || memberPage === 1}
					onclick={() => {
						memberPage--;
						void run(load);
					}}>이전</button
				><span>{memberPage} / {Math.max(1, Math.ceil(data.total / 30))} · {data.total}명</span
				><button
					disabled={busy || memberPage * 30 >= data.total}
					onclick={() => {
						memberPage++;
						void run(load);
					}}>다음</button
				>
			</nav>
			{#if selected}<form
					onsubmit={(e) => {
						e.preventDefault();
						void run(async () => {
							await request('/boards/permissions', {
								method: 'PUT',
								body: {
									user_id: selected,
									scope: `board:${boardId}`,
									action,
									allowed: allowed === 'default' ? null : allowed === 'allow'
								}
							});
							await load();
						});
					}}
				>
					<p>선택 회원 #{selected}</p>
					<select aria-label="대상 게시판" bind:value={boardId}
						>{#each data.boards as b}<option value={b.id}>{b.name}</option>{/each}</select
					><select aria-label="권한 동작" bind:value={action}
						><option value="read">읽기</option><option value="post">글쓰기</option><option
							value="comment">댓글</option
						><option value="manage">게시판 관리</option></select
					><select aria-label="허용 여부" bind:value={allowed}
						><option value="allow">허용</option><option value="deny">거부</option><option
							value="default">기본값 복원</option
						></select
					><button disabled={busy}>권한 저장</button>
				</form>{/if}
			{#each data.permissions.filter((p) => p.user_id === selected) as p}<p>
					{p.scope} · {p.action} · {p.allowed ? '허용' : '거부'}
				</p>{/each}
		</section>
		<section>
			<h2>최근 관리 기록</h2>
			{#each data.audit as a}<p>
					{a.created_at} · 관리자 #{a.actor} · {a.action} · {a.target}
				</p>{:else}<p>아직 변경 기록이 없습니다.</p>{/each}
		</section>
		<p>
			글 공지·삭제·복구는 각 게시판에서, 연동 토큰 발급·폐기는 게시판 아래 자동 등록 API에서
			관리합니다.
		</p>
	{:else if busy}<p role="status">관리 정보를 불러오는 중…</p>{/if}
</div>

<style>
	section {
		padding: 20px 0;
		border-bottom: 1px solid #8884;
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: 15px;
		padding: 10px 0;
	}
	form {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 12px 0;
	}
	.selected {
		outline: 2px solid currentColor;
	}
	button {
		margin: 3px;
	}
	input,
	select,
	button {
		max-width: 100%;
	}
	p {
		overflow-wrap: anywhere;
	}
</style>
