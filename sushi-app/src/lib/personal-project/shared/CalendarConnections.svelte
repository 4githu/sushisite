<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from './api';
	import GoogleExport from './GoogleExport.svelte';
	type Account = { id: number; email: string; last_sync: string | null; error: string | null };
	type Calendar = { calendar_id: string; name: string; enabled: number; writable: number };
	type Project = { id: number; name: string; owner_id: number; memberCount: number; parent_id?: number | null; isolate_tasks?: boolean | number };
	let { onchange = () => {} }: { onchange?: () => void } = $props();
	let accounts = $state<Account[]>([]);
	let calendars = $state<Record<number, Calendar[]>>({});
	type Conflict = { calendar_id: string; google_id: string; title: string };
	let conflicts = $state<Record<number, Conflict[]>>({});
	let projects = $state<Project[]>([]);
	let busy = $state(false);
	let error = $state('');
	let notice = $state('');
	let name = $state('');
	let parentId = $state('');
	let isolateTasks = $state(false);
	let email = $state('');
	let projectId = $state('');
	let inviteUrl = $state('');
	let returnTo = $state('/personal-project/calendar');
	let pairCode = $state('');
	let connectorKey = $state('');
	let connectorName = $state('');
	let connectorProject = $state('');
	let connectors = $state<{id:number;name:string;active:boolean}[]>([]);
	async function run(action: () => Promise<void>) {
		if (busy) return;
		busy = true;
		error = '';
		notice = '';
		try {
			await action();
		} catch (e) {
			error = e instanceof Error ? e.message : '요청을 완료하지 못했습니다.';
		} finally {
			busy = false;
		}
	}
	async function load() {
		[accounts, projects] = await Promise.all([
			request<Account[]>('/google/accounts'),
			request<Project[]>('/calendar/projects')
		]);
		for (const account of accounts)
			conflicts[account.id] = await request<Conflict[]>(`/google/accounts/${account.id}/conflicts`);
	}
	async function refreshCalendars(id: number) {
		calendars[id] = await request<Calendar[]>(`/google/accounts/${id}/calendars`);
	}
	async function saveCalendars(id: number) {
		await request(`/google/accounts/${id}/calendars`, {
			method: 'PUT',
			body: { calendar_ids: calendars[id].filter((c) => c.enabled).map((c) => c.calendar_id) }
		});
		const result = await request<{ updated: number; conflicts: string[] }>(
			`/google/accounts/${id}/sync`,
			{ method: 'POST' }
		);
		notice = result.conflicts.length
			? `동시 수정된 일정 ${result.conflicts.length}건은 보존했습니다. 연결 상태를 확인해주세요.`
			: '일정을 가져왔습니다. Google 변경 사항은 5분마다 가져옵니다. 앱 변경은 자동으로 내보내지 않습니다.';
		await load();
		onchange();
	}
	onMount(() => {
		returnTo = location.pathname + location.search;
		const query = new URL(location.href).searchParams;
		if (query.get('google') === 'connected')
			notice = 'Google 계정을 연결했습니다. 아래에서 가져올 캘린더를 선택하세요.';
		if (query.has('google_error'))
			error = 'Google 연결을 완료하지 못했습니다. 권한에 동의했는지 확인하고 다시 연결해주세요.';
		void run(load);
	});
</script>

<div class="connections">
	{#if error}<p class="feedback error" role="alert">{error}</p>{/if}
	{#if notice}<p class="feedback" role="status">{notice}</p>{/if}
	<section>
		<header>
			<div>
				<h2>Google 캘린더</h2>
				<p>여러 계정의 일정을 한곳에서 확인하세요.</p>
			</div>
			<a
				class="action"
				href={`/auth/google/start?purpose=calendar&return_to=${encodeURIComponent(returnTo)}`}
				>계정 추가</a
			>
		</header>
		{#if !accounts.length}<p class="empty">
				연결된 계정이 없습니다. 계정을 추가한 후 가져올 캘린더를 선택하세요.
			</p>{/if}
		{#each accounts as account (account.id)}
			<article>
				<div class="account">
					<div>
						<strong>{account.email}</strong><small
							>{account.last_sync
								? `최근 동기화 ${new Date(account.last_sync).toLocaleString('ko-KR')}`
								: '아직 동기화하지 않음'}</small
						>
					</div>
					<button disabled={busy} onclick={() => run(() => refreshCalendars(account.id))}
						>캘린더 선택</button
					>
					<button
						disabled={busy}
						onclick={() =>
							run(async () => {
								const result = await request<{ conflicts: string[] }>(
									`/google/accounts/${account.id}/sync`,
									{ method: 'POST' }
								);
								notice = result.conflicts.length
									? '동시 수정 충돌이 있습니다. 변경 내용을 보존했습니다.'
									: 'Google 일정을 가져왔습니다.';
								await load();
								onchange();
							})}>지금 가져오기</button
					>
					<button
						class="subtle"
						disabled={busy}
						onclick={() =>
							run(async () => {
								if (
									!confirm('이 계정 연결을 해제할까요? 이미 가져온 일정과 구글 원본은 유지됩니다.')
								)
									return;
								await request(`/google/accounts/${account.id}`, { method: 'DELETE' });
								await load();
								onchange();
							})}>연결 해제</button
					>
				</div>
				{#if account.error}<p class="feedback error">{account.error}</p>{/if}
				{#each conflicts[account.id] || [] as conflict}
					<div class="feedback error">
						<strong>{conflict.title}</strong><span>동시 수정</span>
						{#each [{ choice: 'google', label: '구글 내용 사용' }] as option}
							<button
								disabled={busy}
								onclick={() =>
									run(async () => {
										if (
											!confirm(
												`${conflict.title}: ${option.label}로 충돌을 해결할까요? 반대쪽 변경 내용을 덮어씁니다.`
											)
										)
											return;
										await request(`/google/accounts/${account.id}/conflicts`, {
											method: 'POST',
											body: { ...conflict, choice: option.choice }
										});
										await load();
										onchange();
									})}>{option.label}</button
							>
						{/each}
					</div>
				{/each}
				{#if calendars[account.id]}
					<div class="calendar-list">
						{#each calendars[account.id] as cal (cal.calendar_id)}
							<label
								><input
									type="checkbox"
									checked={Boolean(cal.enabled)}
									onchange={(e) => {
										cal.enabled = e.currentTarget.checked ? 1 : 0;
									}}
								/>{cal.name}<small>가져오기 전용</small></label
							>
						{/each}
						<button
							class="action"
							disabled={busy}
							onclick={() => run(() => saveCalendars(account.id))}>선택한 캘린더 가져오기</button
						>
					</div>
					<GoogleExport accountId={account.id} calendars={calendars[account.id]} />
				{/if}
			</article>
		{/each}
		<p class="hint">
			가져오기는 Google → 앱 방향이며 원본 수정은 Google에서 합니다. 지난 1년부터 앞으로 2년의 일정을 5분마다 조회합니다. 내보내기는 대상 캘린더와 기간을 선택하고 미리보기 후 실행하세요.
		</p>
	</section>
	<section>
		<header>
			<div>
				<h2>함께 쓰는 프로젝트</h2>
				<p>일정은 함께 보고, 할 일 완료는 각자 기록합니다.</p>
			</div>
		</header>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				void run(async () => {
					projects = await request<Project[]>('/calendar/projects', {
						method: 'POST',
						body: { name: name.trim(), parent_id: parentId ? Number(parentId) : null, isolate_tasks: isolateTasks }
					});
					name = '';
					onchange();
				});
			}}
		>
			<input
				aria-label="새 프로젝트 이름"
				placeholder="예: 스시과 일정"
				bind:value={name}
				required
				maxlength="80"
			/><label>상위 프로젝트<select bind:value={parentId}><option value="">없음</option>{#each projects as p}<option value={String(p.id)}>{p.name}</option>{/each}</select></label><label><input type="checkbox" bind:checked={isolateTasks} />할 일 따로 표시</label><button disabled={busy || !name.trim()}>프로젝트 만들기</button>
		</form>
		{#each projects as project}<div class="project">
				<strong>{project.name}</strong><span>{project.memberCount}명</span>
                <form onsubmit={(event) => { event.preventDefault(); void run(async () => { projects = await request<Project[]>(`/calendar/projects/${project.id}`, { method: 'PUT', body: { name: project.name, parent_id: project.parent_id || null, isolate_tasks: Boolean(project.isolate_tasks) } }); onchange(); notice = '프로젝트 설정을 저장했습니다.'; }); }}>
                <input aria-label={`${project.name} 이름`} bind:value={project.name} required maxlength="80" />
                <select aria-label={`${project.name} 상위 프로젝트`} bind:value={project.parent_id}><option value={null}>없음</option>{#each projects.filter(p => p.id !== project.id) as p}<option value={p.id}>{p.name}</option>{/each}</select>
                <label><input type="checkbox" checked={Boolean(project.isolate_tasks)} onchange={(e) => project.isolate_tasks = e.currentTarget.checked} />할 일 따로 표시</label><button disabled={busy}>설정 저장</button></form>
			</div>{/each}
        {#if projects.length}<details><summary>외부 프로젝트 API 연결</summary>
            <p>선택한 프로젝트에 일정과 할 일을 보내는 연동 키입니다. 키는 발급 직후 한 번만 표시됩니다.</p>
            <select aria-label="API 연결 프로젝트" bind:value={connectorProject} onchange={()=>{ connectors=[]; connectorKey=''; }}><option value="">프로젝트 선택</option>{#each projects as p}<option value={String(p.id)}>{p.name}</option>{/each}</select>
            <input aria-label="API 연결 이름" bind:value={connectorName} placeholder="연결할 서비스 이름" maxlength="80" />
            <button disabled={busy || !connectorProject || !connectorName.trim()} onclick={()=>run(async()=>{const result=await request<{token:string}>(`/calendar/projects/${connectorProject}/connectors`,{method:'POST',body:{name:connectorName}}); connectorKey=result.token; connectors=await request(`/calendar/projects/${connectorProject}/connectors`);})}>연동 키 발급</button>
            <button disabled={busy || !connectorProject} onclick={()=>run(async()=>{connectors=await request(`/calendar/projects/${connectorProject}/connectors`);})}>연동 목록</button>
            {#if connectorKey}<label>새 연동 키<input type="password" readonly value={connectorKey} /></label><button onclick={()=>run(async()=>{await navigator.clipboard.writeText(connectorKey);notice='연동 키를 복사했습니다.';})}>키 복사</button><button onclick={()=>connectorKey=''}>키 닫기</button>{/if}
            {#each connectors as item}<p>{item.name} · {item.active?'사용 중':'해제됨'} {#if item.active}<button disabled={busy} onclick={()=>run(async()=>{await request(`/calendar/projects/${connectorProject}/connectors/${item.id}`,{method:'DELETE'});connectors=await request(`/calendar/projects/${connectorProject}/connectors`);connectorKey='';})}>연동 해제</button>{/if}</p>{/each}
        </details>{/if}
		{#if projects.length}
			<form
				onsubmit={(e) => {
					e.preventDefault();
					void run(async () => {
						const result = await request<{ token: string }>(
							`/calendar/projects/${projectId}/invites`,
							{ method: 'POST', body: { email } }
						);
						inviteUrl = `${location.origin}/personal-project/calendar?invite=${encodeURIComponent(result.token)}`;
					});
				}}
			>
				<select aria-label="초대할 프로젝트" bind:value={projectId} required
					><option value="">프로젝트 선택</option>{#each projects as p}<option value={String(p.id)}
							>{p.name}</option
						>{/each}</select
				>
				<input
					type="email"
					aria-label="초대할 이메일"
					placeholder="초대할 이메일"
					bind:value={email}
					required
				/><button disabled={busy}>초대 링크 만들기</button>
			</form>
			{#if inviteUrl}<label class="link-label"
					>초대받은 사람에게 이 링크를 전달하세요. 7일간 유효합니다.<input
						readonly
						value={inviteUrl}
						onclick={(e) => e.currentTarget.select()}
					/></label
				>{/if}
			<p class="hint">
				소유자가 초대 링크를 만들 수 있습니다. 초대한 이메일로 로그인한 사람만 참여할 수 있습니다.
			</p>
		{/if}
	</section>
	<section>
		<header>
			<div>
				<h2>안드로이드 위젯 연결</h2>
				<p>NETAQ 위젯 앱에서 연결 코드를 입력하면 다음 일정을 확인할 수 있습니다.</p>
				<a class="action" href="/downloads/android-widget" download="ondo-widget.apk">Android 위젯 APK 다운로드</a>
			</div>
		</header>
		<div class="account">
			<button
				disabled={busy}
				onclick={() =>
					run(async () => {
						const result = await request<{ code: string }>('/calendar/widget/pair', {
							method: 'POST'
						});
						pairCode = result.code;
					})}>5분 연결 코드 발급</button
			><button
				disabled={busy}
				onclick={() =>
					run(async () => {
						await request('/calendar/widget/devices', { method: 'DELETE' });
						notice = '모든 위젯 연결을 해제했습니다.';
					})}>위젯 연결 모두 해제</button
			>
		</div>
		{#if pairCode}<label class="link-label"
				>위젯 앱에 입력할 코드<input
					readonly
					value={pairCode}
					onclick={(e) => e.currentTarget.select()}
				/></label
			>{/if}
		<p class="hint">
			직접 설치용 테스트 APK입니다. 별도 위젯 앱 설치가 필요합니다. Google/Samsung 캘린더 위젯을
			쓰는 경우에는 일정을 구글로 보낸 후 해당 캘린더를 선택해도 됩니다.
		</p>
	</section>
</div>

<style>
	.connections {
		display: grid;
		gap: 20px;
		color: #273343;
		font-size: 14px;
	}
	section {
		background: #fff;
		border: 1px solid #e2e7ee;
		border-radius: 12px;
		padding: 24px;
	}
	header,
	.account {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}
	header {
		justify-content: space-between;
		margin-bottom: 18px;
	}
	h2 {
		margin: 0;
		font-size: 17px;
		font-weight: 650;
	}
	p {
		margin: 6px 0;
		color: #647085;
		line-height: 1.6;
	}
	button,
	.action {
		padding: 9px 13px;
		border: 1px solid #dfe1e6;
		border-radius: 7px;
		background: white;
		color: #273343;
		font-size: 13px;
		cursor: pointer;
		text-decoration: none;
	}
	.action {
		background: #bf402d;
		color: white;
		border-color: #bf402d;
	}
	button:disabled {
		opacity: 0.5;
	}
	article {
		padding: 16px 0;
		border-top: 1px solid #eff0f3;
	}
	.account > div {
		flex: 1;
		min-width: 180px;
	}
	.account small {
		display: block;
		margin-top: 5px;
		color: #69778a;
		font-size: 12px;
	}
	.subtle {
		color: #8f3c3c;
	}
	form {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin: 14px 0;
	}
	input:not([type='checkbox']),
	select {
		min-width: 0;
		flex: 1;
		padding: 10px 12px;
		border: 1px solid #dfe1e6;
		border-radius: 7px;
		background: white;
		font: inherit;
	}
	.calendar-list {
		display: grid;
		gap: 12px;
		margin: 18px 0;
	}
	.calendar-list label {
		display: flex;
		align-items: center;
		gap: 9px;
	}
	.calendar-list small {
		color: #6b6e78;
	}
	.calendar-list button {
		justify-self: start;
	}
	.project {
		display: flex;
		justify-content: space-between;
		padding: 12px 0;
		border-bottom: 1px solid #eff0f3;
	}
	.project span,
	.hint {
		font-size: 12px;
		color: #6b6e78;
	}
	.hint {
		margin-top: 18px;
	}
	.feedback {
		padding: 12px;
		border-radius: 7px;
		background: #f7f8fa;
		color: #bf402d;
	}
	.feedback.error {
		background: #fff0ee;
		color: #a33333;
	}
	.empty {
		padding: 14px 0;
	}
	.link-label {
		display: grid;
		gap: 8px;
		font-size: 12px;
		margin: 15px 0;
	}
	.link-label input {
		width: 100%;
	}
	@media (max-width: 600px) {
		section {
			padding: 16px;
		}
		form {
			flex-direction: column;
		}
	}
</style>
