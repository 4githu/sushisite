<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { checkPersonalAuth, logoutPersonal, type PersonalUser } from './auth';

	let user = $state<PersonalUser | null>(null);
	let open = $state(false);
	let error = $state('');

	onMount(async () => {
		user = await checkPersonalAuth().catch(() => null);
	});

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

<div class="account">
	<button class="account-button" onclick={() => (open = !open)} aria-expanded={open}>
		<span>{(user?.data.name ?? user?.data.email ?? '계정').slice(0, 1).toUpperCase()}</span>
		<span>
			<strong>{user?.data.name ?? '계정 설정'}</strong>
			<small>{user?.data.email ?? 'Account settings'}</small>
		</span>
		<i>{open ? '⌃' : '⌄'}</i>
	</button>
	{#if open}
		<div class="account-menu">
			<p><strong>계정 설정 / Account</strong><span>{user?.data.email}</span></p>
			<a href="/register">새 계정 만들기 / Create account</a>
			<button onclick={logout}>로그아웃 / Sign out</button>
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
</style>
