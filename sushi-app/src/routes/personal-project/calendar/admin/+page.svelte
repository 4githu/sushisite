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
		archived: number;
		system_key: string | null;
		post_count: number;
		children_count: number;
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
		boardScoped = $state(false),
		busy = $state(false),
		error = $state(''),
		notice = $state('');
	let roleConfirm = $state(false);
	let inspection = $state<{
			posts: {
				id: number;
				title: string;
				plain: string;
				author_name: string;
				deleted: number;
				comments: { content: string; author_name: string; deleted: number }[];
			}[];
			total: number;
			page: number;
		} | null>(null),
		inspectBoard = $state<number>();
	async function inspect(id: number, p = 1) {
		inspectBoard = id;
		inspection = await request(`/admin/boards/${id}/posts?page=${p}`);
	}
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
	function openBoardPermissions(id: number) {
		boardId = id;
		boardScoped = true;
		tab = 'members';
		q = '';
		membership = 'all';
		page = 1;
		selected = undefined;
		void run(load);
	}
	async function deleteBoard(board: Board) {
		const details = `${board.post_count}개 게시글, ${board.children_count}개 하위 게시판`;
		if (
			!confirm(
				`‘${board.name}’과 하위 게시판 및 첨부 자료를 영구 삭제할까요? (${details}) 이 작업은 되돌릴 수 없습니다.`
			)
		)
			return;
		await request(`/admin/boards/${board.id}`, { method: 'DELETE' });
		await load();
		notice = '게시판과 하위 자료를 삭제했습니다.';
	}
	onMount(() => {
		void run(load);
	});
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key === 'Escape' && !busy) {
			inspection = null;
			editBoard = null;
		}
	}}
/>
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
					<thead><tr><th>회원</th><th>서비스</th><th>역할</th><th>학교·학과</th></tr></thead><tbody
						>{#each data.users as u}<tr
								><td>{u.name}<small>{u.email}</small></td><td
									>{u.member ? 'NETAQ 이용' : '미이용'}</td
								><td
									><button
										disabled={!u.member || busy}
										onclick={() => {
											selected = u.id;
											resetPermissions();
										}}>{u.isAdmin ? '관리자' : '일반 회원'}</button
									></td
								><td>{u.profile?.school || '—'}<small>{u.profile?.department || ''}</small></td></tr
							>{:else}<tr><td colspan="4">조건에 맞는 회원이 없습니다.</td></tr>{/each}</tbody
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
							? '관리 화면 접근 권한입니다. 일반 게시판 열람은 아래 회원 권한을 따릅니다.'
							: '기본 규칙과 게시판별 설정을 함께 적용합니다.'}
					</p>
					<p>
						<button onclick={() => (roleConfirm = !roleConfirm)} aria-expanded={roleConfirm}
							>{member.isAdmin ? '관리자' : '일반 회원'} ▾</button
						>
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
					{#if boardScoped}<div class="board-scope-heading">
							<strong>게시판 권한 · {data.boards.find((b) => b.id === boardId)?.name}</strong>
							<button type="button" onclick={() => (boardScoped = false)}>전체 권한 보기</button>
						</div>{:else}<label
							>대상 게시판<select
								aria-label="대상 게시판"
								bind:value={boardId}
								onchange={resetPermissions}
								>{#each data.boards as b}<option value={b.id}>{b.name}</option>{/each}</select
							></label
						>{/if}
					<table class="permission-table">
						<thead><tr><th>권한</th><th>현재 적용</th><th>개별 설정 변경</th></tr></thead><tbody
							>{#each actions as [a, label]}<tr
									><td>{label}</td><td
										>{member.effective[String(boardId)]?.[a] ? '허용' : '차단'}</td
									><td
										><div class="segmented-control" role="group" aria-label={`${label} 설정`}>
											{#each [['default', '기본'], ['1', '허용'], ['0', '거부']] as [value, text]}
												<button
													type="button"
													class:active={permissionDraft[a] === value}
													aria-pressed={permissionDraft[a] === value}
													disabled={busy}
													onclick={() => {
														permissionDraft[a] = value;
														void run(savePermissions);
													}}>{text}</button
												>
											{/each}
										</div></td
									></tr
								>{/each}</tbody
						>
					</table>
					<p>
						선택하면 바로 저장합니다. 게시판·학과 제한·전체 범위 거부를 적용한 결과가 현재 권한에
						표시됩니다.
					</p>

					{#if !boardScoped}{#each data.permissions.filter((p) => p.user_id === selected && !p.scope.startsWith('board:')) as p}
							<p>
								{p.scope === 'main' ? '메인 게시판 범위' : '기타 게시판 전체 범위'} · {actions.find(
									([a]) => a === p.action
								)?.[1] || '게시판 생성'} · {p.allowed ? '개별 허용' : '개별 거부'}
								<button
									disabled={busy}
									onclick={() =>
										void run(async () => {
											await request('/boards/permissions', {
												method: 'PUT',
												body: {
													user_id: p.user_id,
													scope: p.scope,
													action: p.action,
													allowed: null
												}
											});
											await load();
											notice = '전체 범위 예외를 기본 규칙으로 복원했습니다.';
										})}>이 범위 설정 해제</button
								>
							</p>
						{/each}{/if}
				</section>{/if}
		{:else if tab === 'boards'}<div class="board-config-heading">
				<h2>게시판 구성</h2>
				<a href="/personal-project/calendar/boards/settings">채널·게시판 설정</a>
			</div>
			<p>게시판과 하위 채널을 표에서 함께 확인하고 설정할 수 있습니다.</p>
			<div class="table-scroll">
				<table class="boards-table">
					<thead
						><tr
							><th>게시판·채널</th><th>상위 게시판</th><th>공개 범위</th><th>게시글</th><th>상태</th
							><th>작업</th></tr
						></thead
					>
					<tbody
						>{#each data.boards as b}<tr>
								<td
									><strong>{b.name}</strong>{#if b.school}<small>{b.school} · {b.department}</small
										>{/if}</td
								>
								<td
									>{b.parent_id
										? data.boards.find((parent) => parent.id === b.parent_id)?.name ||
											'상위 게시판 없음'
										: '독립 게시판'}</td
								>
								<td>{b.school ? '학과 제한' : b.restricted ? '지정 회원' : '회원 공개'}</td>
								<td>{b.post_count}</td><td>{b.archived ? '보관됨' : '사용 중'}</td>
								<td class="row-actions"
									><button disabled={busy} onclick={() => openBoardPermissions(b.id)}>권한</button>
									<details class="row-menu">
										<summary>작업</summary>
										<div>
											<button onclick={() => (editBoard = { ...b })}>게시판 설정</button>
											<button disabled={busy} onclick={() => run(() => inspect(b.id))}
												>게시글 확인</button
											>
											<button
												disabled={busy}
												onclick={() =>
													void run(async () => {
														await request(`/admin/boards/${b.id}/archive`, {
															method: 'PUT',
															body: { archived: !b.archived }
														});
														await load();
													})}>{b.archived ? '보관 해제' : '보관'}</button
											>
											<button
												class="danger"
												disabled={busy || !!b.system_key}
												onclick={() => void run(() => deleteBoard(b))}>삭제</button
											>
										</div>
									</details></td
								>
							</tr>{/each}</tbody
					>
				</table>
			</div>
			{#if inspection}<div
					class="modal-backdrop"
					role="presentation"
					onclick={(e) => {
						if (e.target === e.currentTarget && !busy) inspection = null;
					}}
				>
					<dialog
						open
						class="inspection modal-card"
						aria-label="게시글 검토"
						oncancel={(e) => {
							e.preventDefault();
							if (!busy) inspection = null;
						}}
					>
						<header class="modal-heading">
							<h3>{data.boards.find((b) => b.id === inspectBoard)?.name} · 글 검토</h3>
							<button onclick={() => (inspection = null)}>닫기</button>
						</header>
						{#each inspection.posts as post}<article>
								<h4>{post.deleted ? '[삭제됨] ' : ''}{post.title}</h4>
								<small>{post.author_name}</small>
								<p style="white-space:pre-wrap">{post.plain}</p>
								{#each post.comments as comment}<p>
										{comment.deleted ? '[삭제됨] ' : ''}{comment.author_name} · {comment.content}
									</p>{/each}
							</article>{:else}<p>게시글이 없습니다.</p>{/each}
						<button
							disabled={busy || inspection.page === 1}
							onclick={() => run(() => inspect(inspectBoard!, inspection!.page - 1))}>이전</button
						><span>{inspection.page} / {Math.max(1, Math.ceil(inspection.total / 20))}</span><button
							disabled={busy || inspection.page * 20 >= inspection.total}
							onclick={() => run(() => inspect(inspectBoard!, inspection!.page + 1))}>다음</button
						>
					</dialog>
				</div>{/if}
			{#if editBoard}<div
					class="modal-backdrop"
					role="presentation"
					onclick={(e) => {
						if (e.target === e.currentTarget && !busy) editBoard = null;
					}}
				>
					<form
						class="edit-board modal-card"
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
							>소속 게시판<select bind:value={editBoard.parent_id}
								><option value={null}>독립 게시판</option
								>{#each data.boards.filter((b) => b.id !== editBoard?.id) as b}<option value={b.id}
										>{b.name}</option
									>{/each}</select
							></label
						><label
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
					</form>
				</div>{/if}
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
	button,
	select,
	input {
		border: 1px solid #8885;
		border-radius: 8px;
		min-height: 38px;
		padding: 7px 11px;
		background: var(--surface, #fff);
		color: inherit;
	}
	button {
		cursor: pointer;
	}
	button:hover:not(:disabled) {
		border-color: #8b5cf6;
		background: #8b5cf615;
	}
	button:disabled {
		opacity: 0.5;
	}

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
	.boards-table th {
		white-space: nowrap;
	}
	.board-config-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}
	.board-config-heading h2 {
		margin: 0;
	}
	.board-config-heading a {
		padding: 8px 12px;
		border: 1px solid #8885;
		border-radius: 8px;
		color: inherit;
		text-decoration: none;
	}
	.boards-table td {
		vertical-align: middle;
	}
	.row-actions {
		white-space: nowrap;
	}
	.board-scope-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin: 12px 0;
	}
	.row-menu {
		position: relative;
		display: inline-block;
		margin-left: 6px;
	}
	.row-menu summary {
		cursor: pointer;
		padding: 8px 11px;
		border: 1px solid #8885;
		border-radius: 8px;
	}
	.row-menu div {
		position: absolute;
		right: 0;
		z-index: 20;
		display: grid;
		gap: 4px;
		min-width: 150px;
		padding: 8px;
		border: 1px solid #8885;
		border-radius: 10px;
		background: var(--surface, #fff);
		box-shadow: 0 8px 24px #0002;
	}
	.row-menu div button {
		text-align: left;
	}
	.segmented-control {
		display: inline-flex;
		gap: 0;
		border: 1px solid #8885;
		border-radius: 9px;
		padding: 3px;
	}
	.segmented-control button {
		min-height: 30px;
		padding: 4px 10px;
		border: 0;
		border-radius: 6px;
		background: transparent;
	}
	.segmented-control button.active {
		background: #8b5cf61a;
		color: #6d28d9;
		box-shadow: inset 0 0 0 1px #8b5cf655;
		font-weight: 700;
	}
	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 100;
		display: grid;
		place-items: center;
		padding: 20px;
		background: #10141888;
	}
	.modal-card {
		width: min(760px, 100%);
		max-height: min(85vh, 900px);
		overflow: auto;
		padding: 20px;
		border: 1px solid #8885;
		border-radius: 14px;
		background: var(--surface, #fff);
		box-shadow: 0 18px 60px #0003;
	}
	.inspection article {
		padding: 12px 0;
		border-bottom: 1px solid #8883;
	}
	.inspection article p {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.modal-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.modal-heading h3 {
		margin: 0;
	}
	.inspection > button,
	.inspection > span {
		margin: 12px 4px 0 0;
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
