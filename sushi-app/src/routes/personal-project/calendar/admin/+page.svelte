<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	import KakaoBoardRelay from '$lib/personal-project/KakaoBoardRelay.svelte';
	import ApiKeys from '$lib/personal-project/boards/ApiKeys.svelte';
	import '$lib/personal-project/student/student.css';
	type Board = {
		id: number;
		name: string;
		parent_id: number | null;
		sort_order: number;
		restricted: number;
		school: string;
		department: string;
	};
	type Member = {
		id: number;
		name: string;
		email: string;
		member: boolean;
		isAdmin: boolean;
		profile?: { school: string; department: string };
		effective: Record<string, Record<string, boolean>>;
	};
	type Data = {
		users: Member[];
		total: number;
		boards: Board[];
		permissions: { user_id: number; scope: string; action: string; allowed: number }[];
		audit: { id: number; actor: number; action: string; target: string; created_at: string }[];
	};
	let data = $state<Data | null>(null),
		tab = $state('members'),
		q = $state(''),
		membership = $state('members'),
		page = $state(1),
		selected = $state<number>(),
		boardId = $state<number>(),
		busy = $state(false),
		error = $state(''),
		notice = $state('');
	let roleConfirm = $state(false);
	let permissionDraft = $state<Record<string, string>>({}),
		editBoard = $state<Board | null>(null);
	const actions = [
		['read', '열람'],
		['post', '글쓰기'],
		['comment', '댓글'],
		['manage', '게시판 관리']
	];
	const member = $derived(data?.users.find((u) => u.id === selected));
	function resetPermissions() {
		roleConfirm = false;
		permissionDraft = Object.fromEntries(
			actions.map(([a]) => {
				const p = data?.permissions.find(
					(p) => p.user_id === selected && p.scope === `board:${boardId}` && p.action === a
				);
				return [a, p ? String(p.allowed) : 'default'];
			})
		);
	}
	async function load() {
		data = await request(
			`/admin/workspace?q=${encodeURIComponent(q)}&page=${page}&membership=${membership}`
		);
		boardId ??= data?.boards[0]?.id;
		resetPermissions();
	}
	async function run(fn: () => Promise<void>) {
		busy = true;
		error = '';
		notice = '';
		try {
			await fn();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	async function savePermissions() {
		const target = selected,
			scope = `board:${boardId}`;
		for (const [action, value] of Object.entries(permissionDraft)) {
			const old = data?.permissions.find(
				(p) => p.user_id === target && p.scope === scope && p.action === action
			);
			if ((old ? String(old.allowed) : 'default') === value) continue;
			await request('/boards/permissions', {
				method: 'PUT',
				body: {
					user_id: target,
					scope,
					action,
					allowed: value === 'default' ? null : value === '1'
				}
			});
		}
		await load();
		notice = '권한 변경을 저장했습니다.';
	}
	onMount(() => {
		void run(load);
	});
</script>

<svelte:head><title>관리자 · NETAQ</title></svelte:head>
<div class="student-page">
	<h1>NETAQ 관리</h1>
	<nav class="tabs" aria-label="관리 메뉴">
		{#each [['members', '회원·권한'], ['boards', '게시판 구성'], ['integrations', '연동·API'], ['audit', '변경 기록']] as [id, label]}<button
				class:active={tab === id}
				onclick={() => (tab = id)}>{label}</button
			>{/each}
	</nav>
	{#if error}<p role="alert">{error}</p>{/if}{#if notice}<p role="status">{notice}</p>{/if}
	{#if data}
		{#if tab === 'members'}
			<form
				onsubmit={(e) => {
					e.preventDefault();
					page = 1;
					selected = undefined;
					void run(load);
				}}
			>
				<select aria-label="서비스 이용 구분" bind:value={membership}
					><option value="members">NETAQ 이용자</option><option value="nonmembers"
						>초밥 계정만 있는 회원</option
					><option value="all">전체 계정</option></select
				><input
					aria-label="회원 검색"
					bind:value={q}
					placeholder="이름·이메일 (공란은 전체)"
				/><button disabled={busy}>조회</button>
			</form>
			<p>
				초밥 계정은 공통 로그인 정보입니다. NETAQ 이용자는 서비스 방문 또는 기존 이용 기록이 있는
				계정으로 구분합니다.
			</p>
			<div class="table-scroll">
				<table>
					<thead
						><tr><th>회원</th><th>서비스</th><th>역할</th><th>학교·학과</th><th></th></tr></thead
					><tbody
						>{#each data.users as u}<tr
								><td>{u.name}<small>{u.email}</small></td><td
									>{u.member ? 'NETAQ 이용' : '미이용'}</td
								><td>{u.isAdmin ? '관리자' : '일반 회원'}</td><td
									>{u.profile?.school || '—'}<small>{u.profile?.department || ''}</small></td
								><td
									><button
										disabled={!u.member || busy}
										onclick={() => {
											selected = u.id;
											resetPermissions();
										}}>권한 보기</button
									></td
								></tr
							>{:else}<tr><td colspan="5">조건에 맞는 회원이 없습니다.</td></tr>{/each}</tbody
					>
				</table>
			</div>
			<nav>
				<button
					disabled={busy || page === 1}
					onclick={() => {
						page--;
						selected = undefined;
						void run(load);
					}}>이전</button
				>
				{page} / {Math.max(1, Math.ceil(data.total / 30))} · {data.total}명
				<button
					disabled={busy || page * 30 >= data.total}
					onclick={() => {
						page++;
						selected = undefined;
						void run(load);
					}}>다음</button
				>
			</nav>
			{#if member}<section>
					<h2>{member.name}님의 권한</h2>
					<p>
						{member.isAdmin
							? '관리자입니다. 명시적 거부가 있으면 관리자도 해당 권한이 차단됩니다.'
							: '기본 규칙과 게시판별 설정을 함께 적용합니다.'}
					</p>
					<p>
						현재 역할: {member.isAdmin ? '관리자' : '일반 회원'}
						<button onclick={() => (roleConfirm = !roleConfirm)}>역할 변경</button>
					</p>
					{#if roleConfirm}<p>
							{member.name}님을 {member.isAdmin ? '일반 회원으로 변경' : '관리자로 지정'}합니다.
							관리자는 회원 정보와 게시판 권한을 관리할 수 있습니다.
						</p>
						<button
							disabled={busy}
							onclick={() =>
								void run(async () => {
									await request(`/admin/members/${member.id}/role`, {
										method: 'PUT',
										body: { enabled: !member.isAdmin }
									});
									await load();
									notice = '역할 변경을 저장했습니다.';
								})}>역할 변경 확인</button
						><button onclick={() => (roleConfirm = false)}>취소</button>{/if}
					<select aria-label="대상 게시판" bind:value={boardId} onchange={resetPermissions}
						>{#each data.boards as b}<option value={b.id}>{b.name}</option>{/each}</select
					>
					<table>
						<thead><tr><th>권한</th><th>현재 적용</th><th>개별 설정 변경</th></tr></thead><tbody
							>{#each actions as [a, label]}<tr
									><td>{label}</td><td
										>{member.effective[String(boardId)]?.[a] ? '허용' : '차단'}</td
									><td
										><select aria-label={`${label} 설정`} bind:value={permissionDraft[a]}
											><option value="default">기본 규칙</option><option value="1">개별 허용</option
											><option value="0">개별 거부</option></select
										></td
									></tr
								>{/each}</tbody
						>
					</table>
					<p>
						상위 게시판·학과 제한·전체 범위 거부가 우선할 수 있습니다. 저장 후 현재 적용 권한을 다시
						확인합니다.
					</p>
					<button disabled={busy} onclick={() => void run(savePermissions)}>변경 사항 저장</button>
					{#each data.permissions.filter((p) => p.user_id === selected && !p.scope.startsWith('board:')) as p}
						<p>{p.scope === 'main' ? '메인 게시판 범위' : '기타 게시판 전체 범위'} · {actions.find(([a]) => a === p.action)?.[1] || '게시판 생성'} · {p.allowed ? '개별 허용' : '개별 거부'}
							<button disabled={busy} onclick={() => void run(async () => {
								await request('/boards/permissions', {method:'PUT',body:{user_id:p.user_id,scope:p.scope,action:p.action,allowed:null}});
								await load(); notice='전체 범위 예외를 기본 규칙으로 복원했습니다.';
							})}>이 범위 설정 해제</button>
						</p>
					{/each}
				</section>{/if}
		{:else if tab === 'boards'}<h2>게시판 구성</h2>
			<p>표시 순서가 작은 게시판부터 나옵니다. 학과 게시판은 해당 학교·학과 회원에게만 보입니다.</p>
			{#each data.boards as b}<div class="board-row">
					<span
						>{b.parent_id ? '↳ ' : ''}{b.name}<small
							>{b.school
								? `${b.school} · ${b.department}`
								: b.restricted
									? '제한 공개'
									: '회원 공개'} · 순서 {b.sort_order}</small
						></span
					><button onclick={() => (editBoard = { ...b })}>설정</button>
				</div>{/each}
			{#if editBoard}<form
					class="edit-board"
					onsubmit={(e) => {
						e.preventDefault();
						void run(async () => {
							const b = { ...editBoard! };
							await request(`/admin/boards/${b.id}`, {
								method: 'PUT',
								body: { name: b.name, parent_id: b.parent_id || null, sort_order: b.sort_order }
							});
							await request(`/admin/boards/${b.id}/restriction`, {
								method: 'PUT',
								body: { restricted: !!b.restricted }
							});
							editBoard = null;
							await load();
							notice = '게시판 구성을 저장했습니다.';
						});
					}}
				>
					<label>이름<input bind:value={editBoard.name} required maxlength="80" /></label><label
						>상위 게시판<select bind:value={editBoard.parent_id}
							><option value={null}>최상위</option
							>{#each data.boards.filter((b) => b.id !== editBoard?.id) as b}<option value={b.id}
									>{b.name}</option
								>{/each}</select
						></label
					><label>표시 순서<input type="number" bind:value={editBoard.sort_order} /></label><label
						><input
							type="checkbox"
							checked={!!editBoard.restricted}
							onchange={(e) => {
								if (editBoard) editBoard.restricted = Number(e.currentTarget.checked);
							}}
						/>권한을 지정한 회원만 열람</label
					><button disabled={busy}>구성 저장</button><button
						type="button"
						onclick={() => (editBoard = null)}>취소</button
					>
				</form>{/if}
		{:else if tab === 'integrations'}<h2>게시판 연동</h2>
			<KakaoBoardRelay boards={data.boards} /><label
				>API 대상 게시판<select bind:value={boardId}
					>{#each data.boards as b}<option value={b.id}>{b.name}</option>{/each}</select
				></label
			>{#if boardId}{#key boardId}<ApiKeys
						{boardId}
						boardName={data.boards.find((b) => b.id === boardId)?.name || ''}
					/>{/key}{/if}
		{:else}<h2>변경 기록</h2>
			{#each data.audit as a}<p>
					{a.created_at} · 관리자 #{a.actor} · {a.action} · {a.target}
				</p>{:else}<p>변경 기록이 없습니다.</p>{/each}{/if}
	{:else}<p role="status">{busy ? '불러오는 중…' : '관리 정보를 불러오지 못했습니다.'}</p>{/if}
</div>

<style>
	nav,
	form {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 16px 0;
	}
	small {
		display: block;
		color: var(--muted, #777);
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		padding: 12px 8px;
		text-align: left;
		border-bottom: 1px solid #8883;
	}
	.table-scroll {
		overflow: auto;
	}
	section {
		margin-top: 28px;
	}
	.board-row {
		display: flex;
		justify-content: space-between;
		padding: 12px;
		border-bottom: 1px solid #8883;
	}
	.edit-board {
		flex-direction: column;
	}
	.edit-board label {
		display: grid;
		gap: 5px;
	}
	button.active {
		font-weight: bold;
		border-color: currentColor;
	}
	input,
	select {
		max-width: 100%;
	}
</style>
