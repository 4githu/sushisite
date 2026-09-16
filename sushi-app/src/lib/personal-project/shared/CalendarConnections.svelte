<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from './api';
	type Account = { id: number; email: string; last_sync: string | null; error: string | null };
	type Calendar = { calendar_id: string; name: string; enabled: number; writable: number };
	type Project = { id: number; name: string; owner_id: number; memberCount: number };
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
	let email = $state('');
	let projectId = $state('');
	let inviteUrl = $state('');
	let returnTo = $state('/personal-project/calendar');
	let pairCode = $state('');
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
			: '일정을 가져왔습니다. 연결된 일정은 5분마다 동기화됩니다.';
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
									: '동기화했습니다.';
								await load();
								onchange();
							})}>동기화</button
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
						{#each [{ choice: 'local', label: '앱 내용 유지' }, { choice: 'google', label: '구글 내용 사용' }] as option}
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
								/>{cal.name}<small>{cal.writable ? '읽기·쓰기' : '읽기 전용'}</small></label
							>
						{/each}
						<button
							class="action"
							disabled={busy}
							onclick={() => run(() => saveCalendars(account.id))}>선택한 캘린더 가져오기</button
						>
					</div>
				{/if}
			</article>
		{/each}
		<p class="hint">
			가져온 일정과 ‘구글로 보내기’한 일정의 수정·삭제가 연동됩니다. 개인 일정 전체를 자동 공개하지
			않습니다. 가져오는 범위는 지난 1년부터 앞으로 2년입니다.
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
						body: { name: name.trim() }
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
			/><button disabled={busy || !name.trim()}>프로젝트 만들기</button>
		</form>
		{#each projects as project}<div class="project">
				<strong>{project.name}</strong><span>{project.memberCount}명</span>
			</div>{/each}
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
				<p>온도 위젯 앱에서 연결 코드를 입력하면 다음 일정을 확인할 수 있습니다.</p>
				<a class="action" href="/downloads/ondo-widget.apk" download>Android 위젯 APK 다운로드</a>
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
		border: 1px solid #d8dfe8;
		border-radius: 7px;
		background: white;
		color: #273343;
		font-size: 13px;
		cursor: pointer;
		text-decoration: none;
	}
	.action {
		background: #245ac7;
		color: white;
		border-color: #245ac7;
	}
	button:disabled {
		opacity: 0.5;
	}
	article {
		padding: 16px 0;
		border-top: 1px solid #edf0f4;
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
		border: 1px solid #d8dfe8;
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
		color: #738197;
	}
	.calendar-list button {
		justify-self: start;
	}
	.project {
		display: flex;
		justify-content: space-between;
		padding: 12px 0;
		border-bottom: 1px solid #edf0f4;
	}
	.project span,
	.hint {
		font-size: 12px;
		color: #748094;
	}
	.hint {
		margin-top: 18px;
	}
	.feedback {
		padding: 12px;
		border-radius: 7px;
		background: #edf4ff;
		color: #2455a6;
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
