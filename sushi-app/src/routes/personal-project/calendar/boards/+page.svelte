<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { page } from '$app/state';
	import { goto, beforeNavigate } from '$app/navigation';
	import { request } from '$lib/personal-project/shared/api';
	import PersonalTextEditor from '$lib/personal-project/editor/PersonalTextEditor.svelte';
	import { createDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import '$lib/personal-project/student/student.css';
	type Board = {
        school?: string;
        system_key?: string;
		relayRoom?: string;
		id: number;
		parent_id: number | null;
		name: string;
		realm: string;
		post_count?: number;
		last_title?: string;
		permissions: Record<string, boolean>;
	};
	type Post = {
		thumbnail?: string;
		id: number;
		title: string;
		author_id: number;
		author_name: string;
		pinned: number;
		revision: number;
		created_at: string;
		comments: number;
	};
	type Detail = Omit<Post, 'comments'> & {
		board_id: number;
		document: EditorDocument;
		canEdit: boolean;
		canManage: boolean;
		canComment: boolean;
		comments: {
			id: number;
			content: string;
			parent_id: number | null;
			author_id: number;
			author_name: string;
			created_at: string;
			deleted: number;
			canDelete: boolean;
		}[];
	};
	let management=$state<{members:{id:number;name:string;manager:boolean;locked:boolean}[];archived:{id:number;name:string}[]}>({members:[],archived:[]});
 async function loadManagement(){management=await request(`/boards/${bid}/management`);}
	let settingsOpen = $state(false), settingsName = $state(''), managerId = $state<number>();
	let creatingBoard = $state(false),
		newBoardName = $state('');
	let boards = $state<Board[]>([]),
		canAdmin = $state(false),
		canCreate = $state(false),
		posts = $state<Post[]>([]),
		total = $state(0),
		detail = $state<Detail | null>(null),
		loading = $state(true),
		busy = $state(false),
		error = $state(''),
		q = $state(''),
		trash = $state(false);
	let composing = $state(false),
		editId = $state<number | null>(null),
		title = $state(''),
		initial = $state<EditorDocument>(createDocument()),
		document = $state<EditorDocument>(createDocument()),
		changed = $state(false),
		comment = $state(''),
		reply = $state<number | null>(null),
		ready = $state(false);
	let account = $state<number | undefined>(),
		scope = $state('main'),
		action = $state('read'),
		permission = $state('allow'),
		acl = $state<{ user_id: number; scope: string; action: string; allowed: number }[]>([]);
	const bid = $derived(Number(page.url.searchParams.get('board') || 0));
	const pid = $derived(Number(page.url.searchParams.get('post') || 0));
	const currentPage = $derived(Number(page.url.searchParams.get('page') || 1));
	const board = $derived(boards.find((b) => b.id === bid));
	const rootBoard = $derived(board?.parent_id && !board.school ? boards.find((b) => b.id === board.parent_id) : board);
	let composer = $state<PersonalTextEditor>();
	let generation = 0;
	beforeNavigate(({ cancel }) => {
		if (changed && !confirm('작성 중인 글을 두고 이동할까요?')) cancel();
	});
	async function run(fn: () => Promise<void>) {
		if (busy) return;
		busy = true;
		error = '';
		try {
			await fn();
		} catch (e) {
			error = e instanceof Error ? e.message : '처리하지 못했습니다.';
		} finally {
			busy = false;
			if (!ready) loading = false;
		}
	}
	onMount(() => {
		void run(async () => {
			const data = await request<{ boards: Board[]; canAdmin: boolean; canCreate: boolean }>(
				'/boards'
			);
			boards = data.boards;
			canAdmin = data.canAdmin;
			canCreate = data.canCreate;
			ready = true;
		});
	});
	$effect(() => {
		bid;
		pid;
		currentPage;
		if (ready) void untrack(load);
	});
	async function load() {
		const version = ++generation;
		loading = true;
		error = '';
		composing = false;
		changed = false;
		detail = null;
		try {
			if (pid) {
				const data = await request<Detail>(`/boards/posts/${pid}`);
				if (version === generation) detail = data;
			} else if (bid) {
				const data = await request<{ posts: Post[]; total: number }>(
					`/boards/${bid}/posts?${new URLSearchParams({ page: String(currentPage), q, deleted: String(trash) })}`
				);
				if (version === generation) {
					posts = data.posts;
					total = data.total;
				}
			}
		} catch (e) {
			if (version === generation) error = String(e);
		} finally {
			if (version === generation) loading = false;
		}
	}
	function navigate(b: number, p = 0, n = 1) {
		return goto(`?board=${b}${p ? `&post=${p}` : ''}${n > 1 ? `&page=${n}` : ''}`, {
			keepFocus: true,
			noScroll: false
		});
	}
	function compose(edit = false) {
		editId = edit && detail ? detail.id : null;
		title = edit && detail ? detail.title : '';
		initial = edit && detail ? detail.document : createDocument();
		document = initial;
		composing = true;
		changed = false;
	}
	async function save() {
		const result = await request<{ id: number }>(
			editId ? `/boards/posts/${editId}` : `/boards/${bid}/posts`,
			{
				method: editId ? 'PUT' : 'POST',
				body: { title, document, revision: editId ? detail?.revision : 0 }
			}
		);
		changed = false;
		composing = false;
		if (result.id === pid) await load();
		else await navigate(bid, result.id);
	}
</script>

<svelte:head><title>게시판 · NETAQ</title></svelte:head>
<div class="student-page board-page">
	<header class="board-heading">
		<h1>{rootBoard?.name || '게시판'}</h1>
		{#if (!bid && canCreate) || (bid && rootBoard?.permissions.manage)}<button
				onclick={() => (creatingBoard = !creatingBoard)}
				>{bid ? '채널 추가' : '게시판 만들기'}</button
			>{/if}
	</header>
	{#if creatingBoard}<form
			onsubmit={(e) => {
				e.preventDefault();
				void run(async () => {
					const b = await request<{ id: number }>('/boards', {
						method: 'POST',
						body: { name: newBoardName, parent_id: rootBoard?.id || null }
					});
					boards = (await request<{ boards: Board[] }>('/boards')).boards;
					creatingBoard = false;
					newBoardName = '';
					await navigate(b.id);
				});
			}}
		>
			<input aria-label="새 게시판 이름" bind:value={newBoardName} required maxlength="80" /><button
				disabled={busy}>만들기</button
			><button type="button" onclick={() => (creatingBoard = false)}>취소</button>
		</form>{/if}
	{#if board?.permissions.manage}<button onclick={() => run(async()=> { settingsName = board!.name; settingsOpen = !settingsOpen;if(settingsOpen)await loadManagement(); })}>게시판·채널 설정</button>{/if}
	{#if settingsOpen && board?.permissions.manage}<section class="panel">
		<label>이름<input bind:value={settingsName} maxlength="80" /></label>
		<button disabled={busy || !settingsName.trim()} onclick={() => run(async () => {
			await request(`/boards/${bid}/settings`, {method:'PUT',body:{name:settingsName}});
			boards = (await request<{boards:Board[]}>('/boards')).boards; settingsOpen=false;
		})}>이름 저장</button>
		<button disabled={busy} onclick={() => run(async () => {
			if (!confirm('글을 보존한 채 보관합니다. 채널은 게시판 설정에서, 게시판은 관리자 페이지에서 복구할 수 있습니다.')) return;
			const parent=board?.parent_id || 0;await request(`/boards/${bid}/settings`, {method:'PUT',body:{name:board!.name,archived:true}});
			boards = (await request<{boards:Board[]}>('/boards')).boards; settingsOpen=false; await navigate(parent);
		})}>보관하기</button>
        <h3>게시판 관리자</h3>
        {#each management.members as member}<label>{member.name || `회원 ${member.id}`}<select aria-label={`${member.name} 게시판 권한`} value={member.manager?'manager':'member'} disabled={busy||member.locked} onchange={e=>{const enabled=e.currentTarget.value==='manager';void run(async()=>{await request(`/boards/${bid}/managers/${member.id}`,{method:'PUT',body:{enabled}});await loadManagement();});}}><option value="member">일반 회원</option><option value="manager">게시판 관리자</option></select></label>{/each}
        {#if management.archived.length}<h3>보관한 채널</h3>{#each management.archived as channel}<button disabled={busy} onclick={()=>run(async()=>{await request(`/boards/${bid}/channels/${channel.id}/restore`,{method:'POST'});await loadManagement();boards=(await request<{boards:Board[]}>('/boards')).boards;})}>{channel.name} 복구</button>{/each}{/if}

	</section>{/if}
	{#if rootBoard}<nav class="channel-tabs" aria-label="게시판 채널">
		<a class:active={bid === rootBoard.id} aria-current={bid === rootBoard.id ? 'page' : undefined} href={`?board=${rootBoard.id}`}>일반</a>
		{#each boards.filter((b) => b.parent_id === rootBoard.id) as channel}
			<a class:active={bid === channel.id} aria-current={bid === channel.id ? 'page' : undefined} href={`?board=${channel.id}`}>{channel.name}</a>
		{/each}
	</nav>{/if}
	{#if !bid}<section class="board-directory">
			<h2>전체 게시판</h2>
			{#if !ready}<p>게시판을 불러오는 중…</p>{/if}{#each boards.filter((b) => (!b.parent_id || b.school) && b.system_key !== 'department-root') as b}<a
					href={`?board=${b.id}`}
					><div>
						<strong>{b.name}</strong>
						<p>{b.last_title || '첫 글을 남겨보세요.'}</p>
					</div>
					<span>{b.post_count || 0}개 글 · 목록 보기 →</span></a
				>{/each}
		</section>{/if}
	{#if error}<p class="error" role="alert">
			{error}<button onclick={load}>다시 불러오기</button>
		</p>{/if}
	{#if board?.relayRoom}<p role="status">
			이 게시판의 새 글·이미지는 ‘{board.relayRoom}’ 카카오톡 방에도 공유됩니다. 파일은 게시글
			링크에서 접근 권한을 확인한 뒤 열 수 있습니다.
		</p>{/if}
	{#if bid}{#if composing}<section class="composer">
				<div class="heading">
					<h2>{editId ? '글 수정' : '새 글'}</h2>
					<button
						onclick={() => {
							if (!changed || confirm('작성 중인 글을 닫을까요?')) {
								composing = false;
								changed = false;
							}
						}}>닫기</button
					>
				</div>
				<label
					>제목<input
						aria-label="글 제목"
						bind:value={title}
						maxlength="160"
						oninput={() => (changed = true)}
					/></label
				>
				<p class="attachment-help">
					‘그림 메모’로 그려서 첨부하세요. 사진·그림을 선택하면 위치와 크기를 바꿀 수 있습니다.
				</p>
				<PersonalTextEditor
					bind:this={composer}
					initialValue={initial}
					boardId={bid}
					onchange={(value) => {
						document = value;
						changed = true;
					}}
				/>
				<div class="actions">
					<button class="primary" disabled={busy || !title.trim()} onclick={() => run(save)}
						>{busy ? '저장 중…' : editId ? '수정 저장' : '게시하기'}</button
					>
				</div>
			</section>
		{:else if loading}<p role="status" class="list-status">불러오는 중…</p>
		{:else if detail}<article class="post-detail">
				<a href={`?board=${detail.board_id}`}>← 목록</a>
				<header>
				<div class="actions post-actions">
					{#if detail.canEdit}<button onclick={() => compose(true)}>글 수정</button>{/if}
					{#if detail.canEdit}<button
							onclick={() =>
								run(async () => {
									await request(`/boards/posts/${pid}`, {
										method: 'PATCH',
										body: { deleted: true }
									});
									await navigate(detail!.board_id);
								})}>삭제</button
						>{/if}{#if detail.canManage}<button
							onclick={() =>
								run(async () => {
									await request(`/boards/posts/${pid}`, {
										method: 'PATCH',
										body: { pinned: !detail!.pinned }
									});
									await load();
								})}>{detail.pinned ? '공지 해제' : '공지로 고정'}</button
						>{/if}
				</div>
					<h2>{detail.title}</h2>
					<p class="muted">
						{detail.author_name} · {new Date(detail.created_at + 'Z').toLocaleString('ko-KR')}
					</p>
				</header>
				<PersonalTextEditor initialValue={detail.document} readonly />

				<section class="comments">
					<h3>댓글 {detail.comments.filter((c) => !c.deleted).length}</h3>
					{#each detail.comments as c}<article class:reply={!!c.parent_id}>
							<small>{c.author_name}{c.parent_id ? ` · 댓글 #${c.parent_id}에 답글` : ''}</small>
							<p>{c.content}</p>
							{#if !c.deleted}<button onclick={() => (reply = c.id)}>답글</button
								>{#if c.canDelete}<button
										onclick={() =>
											run(async () => {
												await request(`/boards/comments/${c.id}`, { method: 'DELETE' });
												await load();
											})}>삭제</button
									>{/if}{/if}
						</article>{/each}
					{#if detail.canComment}<form
							onsubmit={(e) => {
								e.preventDefault();
								void run(async () => {
									detail = await request(`/boards/posts/${pid}/comments`, {
										method: 'POST',
										body: { content: comment, parent_id: reply }
									});
									comment = '';
									reply = null;
								});
							}}
						>
							{#if reply}<p>
									댓글 #{reply}에 답글
									<button type="button" onclick={() => (reply = null)}>취소</button>
								</p>{/if}<textarea
								aria-label="댓글 내용"
								placeholder="댓글을 남겨보세요"
								bind:value={comment}
								required
								maxlength="10000"
								rows="3"
							></textarea><button class="primary" disabled={busy || !comment.trim()}
								>댓글 등록</button
							>
						</form>{/if}
				</section>
			</article>
		{:else}<section>
				<div class="list-toolbar">
					<h2>{rootBoard?.name || '게시판'}</h2>
					<form
						onsubmit={(e) => {
							e.preventDefault();
							void load();
						}}
					>
						<input aria-label="게시글 검색" placeholder="제목·본문 검색" bind:value={q} /><button
							>검색</button
						>
					</form>
					{#if board?.permissions.post}<button class="primary" onclick={() => compose()}
							>글쓰기</button
						>{/if}{#if board?.permissions.manage}<label
							><input type="checkbox" bind:checked={trash} onchange={load} />휴지통</label
						>{/if}
				</div>
				<div class="post-list">
					{#each posts as p}<div class="post-row">
							<a href={`?board=${bid}&post=${p.id}`}
								>{#if p.thumbnail}<img
										class="post-thumb"
										src={p.thumbnail}
										alt="첨부 이미지"
										loading="lazy"
									/>{/if}<span>{p.pinned ? '공지 · ' : ''}{p.title}</span><small
									>{p.author_name} · {p.created_at.slice(0, 10)} · 댓글 {p.comments}</small
								></a
							>{#if trash}<button
									onclick={() =>
										run(async () => {
											await request(`/boards/posts/${p.id}`, {
												method: 'PATCH',
												body: { deleted: false }
											});
											await load();
										})}>복구</button
								>{/if}
						</div>{:else}<p class="list-status">
							{q ? '검색 결과가 없습니다.' : '아직 게시글이 없습니다.'}
						</p>{/each}
				</div>
				<nav class="pagination" aria-label="게시글 페이지">
					<button disabled={currentPage <= 1} onclick={() => navigate(bid, 0, currentPage - 1)}
						>이전</button
					><span>{currentPage} / {Math.max(1, Math.ceil(total / 30))}</span><button
						disabled={currentPage * 30 >= total}
						onclick={() => navigate(bid, 0, currentPage + 1)}>다음</button
					>
				</nav>
			</section>{/if}
	{/if}


</div>

<style>
	.board-page button, .post-detail > a { border: 1px solid var(--border,#d6d9df); border-radius: 8px; padding: 8px 12px; min-height: 38px; background: var(--surface,#fff); color: inherit; cursor: pointer; }
	.board-page button:hover:not(:disabled) { background: #8b5cf612; border-color: #8b5cf6; }
	.board-page button:disabled { opacity: .5; cursor: not-allowed; }
	.channel-tabs { display: flex; overflow-x: auto; gap: 4px; padding: 5px 5px 0; border-bottom: 1px solid #8884; margin: 16px 0 24px; }
	.channel-tabs a { white-space: nowrap; padding: 10px 18px; border: 1px solid #8884; border-bottom: 0; border-radius: 9px 9px 0 0; color: inherit; text-decoration: none; background: #8881; }
	.channel-tabs a.active { background: #8b5cf61a; color: #6d28d9; box-shadow: inset 0 3px #8b5cf6; font-weight: 700; }
	.post-actions { justify-content: flex-end; margin-bottom: 12px; }

	.post-thumb {
		float: right;
		width: 76px;
		height: 64px;
		object-fit: cover;
		border-radius: 6px;
		margin-left: 12px;
	}
	.attachment-help {
		font-size: 13px;
		color: #666;
	}
	.board-directory {
		display: grid;
		gap: 12px;
	}
	.board-directory > a {
		display: flex;
		justify-content: space-between;
		gap: 16px;
		padding: 18px;
		border: 1px solid #8884;
		border-radius: 12px;
		background: var(--surface,#fff);
		text-decoration: none;
		color: inherit;
	}
	.board-directory p {
		font-size: 13px;
		color: #666;
		margin: 8px 0 0;
	}
	.board-directory span {
		font-size: 13px;
		color: #777;
	}
	.board-page {
		max-width: 1100px;
	}
	.board-heading,
	.heading,
	.list-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}
	.board-heading h1 {
		font-size: 28px;
	}
	.list-toolbar form {
		display: flex;
		gap: 6px;
		margin-left: auto;
	}
	.list-toolbar h2 {
		font-size: 20px;
	}
	.post-list {
		margin-top: 20px;
		border-top: 2px solid currentColor;
	}
	.post-row {
		border-bottom: 1px solid var(--border, #ddd);
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.post-row > a {
		flex: 1;
		min-width: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 8px;
		padding: 20px 4px;
		text-decoration: none;
		font-size: 16px;
	}
	.post-row > a > span,
	.post-row > a > small {
		grid-column: 1;
		overflow-wrap: anywhere;
	}
	.post-row > a > .post-thumb {
		grid-column: 2;
		grid-row: 1 / 3;
		align-self: center;
	}
	.post-row small {
		font-size: 13px;
		opacity: 0.65;
	}
	.post-row:hover {
		background: #8888880b;
	}
	.pagination,
	.actions {
		display: flex;
		gap: 12px;
		justify-content: flex-end;
		align-items: center;
		margin: 18px 0;
	}
	.pagination {
		justify-content: center;
	}
	.list-status {
		padding: 48px 12px;
		text-align: center;
	}
	.composer > label {
		display: block;
		margin-bottom: 16px;
	}
	.composer > label input {
		width: 100%;
		margin-top: 8px;
		font-size: 20px;
	}
	.post-detail header {
		padding: 24px 0;
	}
	.post-detail h2 {
		font-size: 28px;
	}
	.comments {
		border-top: 1px solid var(--border, #ddd);
		margin-top: 32px;
		padding-top: 24px;
	}
	.comments article {
		padding: 16px 0;
		border-bottom: 1px solid var(--border, #ddd);
	}
	.comments article.reply {
		margin-left: 24px;
	}
	.comments p {
		white-space: pre-wrap;
	}
	.comments article button {
		font-size: 13px;
		margin-right: 12px;
	}
	.comments textarea {
		display: block;
		width: 100%;
		margin: 16px 0 8px;
	}
	@media (max-width: 600px) {
		.list-toolbar form {
			order: 3;
			width: 100%;
		}
		.list-toolbar input {
			flex: 1;
			min-width: 0;
		}
		.post-detail h2 {
			font-size: 23px;
		}
	}
</style>
