<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { checkPersonalAuth, logoutPersonal, type PersonalUser } from './auth';
	import { request } from './api';

	let user = $state<PersonalUser | null>(null);
	let open = $state(false);
	let error = $state('');
	let canAdmin = $state(false);
	let checking = $state(false);
	let accountRoot: HTMLDivElement;
	let alive = false;
	let sequence = 0;

	async function refresh(force = false) {
		const serial = ++sequence;
		checking = true;
		try {
			const next = await checkPersonalAuth(force);
			if (!alive || serial !== sequence) return;
			user = next;
			error = next ? '' : '로그인이 만료되었습니다. 다시 로그인해주세요.';
			canAdmin = false;
			if (next) {
				const allowed = await request<{ canAdmin: boolean }>('/boards')
					.then((v) => v.canAdmin)
					.catch(() => false);
				if (alive && serial === sequence) canAdmin = allowed;
			}
		} catch {
			if (alive && serial === sequence)
				error = '연결을 확인해주세요. 이전 계정 정보가 표시될 수 있습니다.';
		} finally {
			if (alive && serial === sequence) checking = false;
		}
	}
	function onVisibility() {
		if (document.visibilityState === 'visible') void refresh(true);
	}
	function onInvalid() {
		void refresh(true);
	}
	function onExpired() {
		sequence++;
		user = null;
		canAdmin = false;
		error = '로그인이 만료되었습니다. 다시 로그인해주세요.';
	}
	onMount(() => {
		alive = true;
		const outside = (event: PointerEvent) => {
			if (open && event.target instanceof Node && !accountRoot.contains(event.target)) open = false;
		};
		const escape = (event: KeyboardEvent) => {
			if (event.key === 'Escape') open = false;
		};
		document.addEventListener('pointerdown', outside, true);
		window.addEventListener('keydown', escape);
		void refresh(true);
		document.addEventListener('visibilitychange', onVisibility);
		window.addEventListener('personal-auth-updated', onInvalid);
		window.addEventListener('personal-auth-invalid', onExpired);
		window.addEventListener('personal-auth-expired', onExpired);
		window.addEventListener('storage', onInvalid);
		return () => {
			alive = false;
			document.removeEventListener('pointerdown', outside, true);
			window.removeEventListener('keydown', escape);
			sequence++;
			document.removeEventListener('visibilitychange', onVisibility);
			window.removeEventListener('personal-auth-updated', onInvalid);
			window.removeEventListener('personal-auth-invalid', onExpired);
			window.removeEventListener('personal-auth-expired', onExpired);
			window.removeEventListener('storage', onInvalid);
		};
	});
	function toggle() {
		open = !open;
		if (open) void refresh(true);
	}

	async function logout() {
		error = '';
		try {
			await logoutPersonal();
			await goto('/personal-project');
			location.reload();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '로그아웃 실패 / Sign-out failed';
		}
	}
</script>

<div class="account" bind:this={accountRoot}>
	<button class="account-button" onclick={toggle} aria-expanded={open}>
		<span>{(user?.data.name ?? user?.data.email ?? '계정').slice(0, 1).toUpperCase()}</span>
		<span>
			<strong>{user?.data.name ?? '계정 설정'}</strong>
			<small>{user?.data.email ?? 'Account settings'}</small>
		</span>
		<i>{open ? '⌃' : '⌄'}</i>
	</button>
	{#if open}
		<div class="account-menu" aria-label="프로필 옵션">
			{#if checking}<small role="status">계정 정보 확인 중…</small>{/if}
			<p><strong>내 계정</strong><span>{user?.data.email}</span></p>
			{#if user?.data.email_verified === false}<small>이메일 확인 필요</small>{/if}
			<a href="/register">새 계정 만들기</a>
			{#if canAdmin}<a href="/personal-project/calendar/admin" onclick={() => (open = false)}
					>관리자 페이지</a
				>{/if}
			<a href="/personal-project/calendar/projects" onclick={() => (open = false)}
				>캘린더 연결·프로젝트</a
			>
			<a href="/personal-project/calendar/student" onclick={() => (open = false)}>학교 설정</a>
			<a href="/personal-project/calendar/widgets" onclick={() => (open = false)}>위젯 설치·연결</a>
			<a href="/personal-project/notes" onclick={() => (open = false)}>노트 목록</a>
			<button onclick={logout}>로그아웃</button>
			{#if error}<small>{error}</small>{/if}
		</div>
	{/if}
</div>

<style>
	.account {
		position: relative;
		margin-top: auto;
	}
	.account-button {
		width: 100%;
		padding: 10px;
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 9px;
		border: 1px solid #d8d5ca;
		border-radius: 12px;
		background: rgba(255, 254, 250, 0.72);
		color: var(--pp-ink);
		text-align: left;
		cursor: pointer;
	}
	.account-button > span:first-child {
		width: 31px;
		height: 31px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: var(--pp-sage-dark);
		color: white;
		font:
			600 13px Georgia,
			serif;
	}
	.account-button strong,
	.account-button small {
		overflow: hidden;
		display: block;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.account-button strong {
		font-size: 10px;
	}
	.account-button small {
		margin-top: 3px;
		color: var(--pp-muted);
		font-size: 8px;
	}
	.account-button i {
		color: var(--pp-muted);
		font-style: normal;
	}
	.account-menu {
		position: absolute;
		bottom: calc(100% + 8px);
		left: 0;
		width: 100%;
		padding: 12px;
		display: grid;
		gap: 8px;
		border: 1px solid var(--pp-line);
		border-radius: 11px;
		background: white;
		box-shadow: 0 10px 30px rgba(37, 48, 44, 0.12);
	}
	.account-menu p {
		margin: 0;
	}
	.account-menu p strong,
	.account-menu p span {
		display: block;
		font-size: 9px;
	}
	.account-menu p span {
		margin-top: 3px;
		color: var(--pp-muted);
	}
	.account-menu a,
	.account-menu button {
		padding: 7px;
		border: 0;
		border-radius: 6px;
		background: #f4f4ef;
		color: var(--pp-ink);
		font-size: 9px;
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}
	.account-menu > small {
		color: #a74b36;
		font-size: 8px;
	}

	.account-menu {
		box-sizing: border-box;
		width: 280px;
		max-width: calc(100vw - 32px);
		gap: 4px;
		padding: 12px;
		background: white;
	}
	.account-menu p {
		padding: 6px 8px 12px;
		border-bottom: 1px solid var(--pp-line);
		margin-bottom: 4px;
	}
	.account-menu p strong {
		font-size: 16px;
	}
	.account-menu p span {
		font-size: 13px;
		overflow-wrap: anywhere;
	}
	.account-menu a,
	.account-menu button {
		font-size: 14px;
		min-height: 40px;
		background: white;
		padding: 8px;
		border-radius: 6px;
		display: flex;
		align-items: center;
	}
	.account-menu a:hover,
	.account-menu button:hover {
		background: #f4f5f7;
	}
	.account-menu > small {
		font-size: 12px;
		padding: 4px 8px;
		line-height: 1.5;
	}
</style>
