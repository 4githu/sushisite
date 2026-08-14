<!-- src/routes/odi/+layout.svelte -->
<script lang="ts">
	import "$lib/odi/styles/globals.css";

	import type { Snippet } from "svelte";
	import { onMount } from "svelte";
	import { goto } from "$app/navigation";
	import { page } from "$app/state";

	import { auth } from "$lib/stores/mainauth";
	import { odiuser, template } from "$lib/odi/stores";
	import { API_BASE as API } from '$lib/config/api';

	import NavigationBar from "$lib/odi/components/navigation/NavigationBar.svelte";
	import SessionStartModal from "$lib/odi/components/session/SessionStartModal.svelte";
	import OdiGuestModal from "$lib/odi/components/login/OdiGuestModal.svelte";
	import LoginModal from "$lib/odi/components/login/LoginModal.svelte";
	import AccountModal from "$lib/odi/components/login/AccountModal.svelte";
	import OdiJoinRequiredModal from "$lib/odi/components/login/OdiJoinRequiredModal.svelte";

	type SessionType = "presentation" | "interview";

	let {
		children
	}: {
		children: Snippet;
	} = $props();

	let showStartModal = $state(false);
	let showGuestModal = $state(false);
	let showLoginModal = $state(false);
	let showAccountModal = $state(false);
	let showJoinRequiredModal = $state(false);
	let checkingAccess = $state(true);
	let sidebarOpen = $state(true);

	let mainAuthName = $state("");
	let mainAuthEmail = $state("");

	const isAuthExceptionPage = $derived(page.url.pathname.startsWith("/odi/join"));

	onMount(async () => {
		sidebarOpen = !window.matchMedia("(max-width: 900px)").matches;

		if (isAuthExceptionPage) {
			checkingAccess = false;
			return;
		}

		try {
			const result = await odiuser.checkAccess();

			if (result.status === "odi_authenticated") {
				showGuestModal = false;
				showJoinRequiredModal = false;
				return;
			}

			if (result.status === "main_authenticated_needs_odi_join") {
				const payload = auth.get();

				mainAuthName = payload?.data?.name ?? "사용자";
				mainAuthEmail = payload?.data?.email ?? "";

				showJoinRequiredModal = true;
				return;
			}

			showGuestModal = true;
		} catch {
			// 백엔드가 잠시 응답하지 않아도 빈 화면에 멈추지 않고 로그인 UI를 표시합니다.
			showGuestModal = true;
		} finally {
			checkingAccess = false;
		}
	});

	function openStartModal() {
		if (!odiuser.get()) {
			showGuestModal = true;
			return;
		}

		showStartModal = true;
	}

	function closeStartModal() {
		showStartModal = false;
	}

	function selectSessionType(type: SessionType) {
		showStartModal = false;
		// 새 유형 시작은 최근 세션 값을 물려받지 않는 완전히 빈 초안입니다.
		template.setDefault(type);

		if (type === "presentation") {
			goto("/odi/session/presentation");
			return;
		}

		goto("/odi/session/interview");
	}

	function loadPreviousSession() {
		showStartModal = false;
		console.log("기존 세션 불러오기");
	}

	function closeGuestModal() {
		showGuestModal = false;
	}

	function openLoginModal() {
		showGuestModal = false;
		showLoginModal = true;
	}

	function closeLoginModal() {
		showLoginModal = false;
	}

	function openRegisterPage() {
		showGuestModal = false;
		goto("/register");
	}

	function handleLoginSuccess() {
		const payload = auth.get();

		mainAuthName = payload?.data?.name ?? "사용자";
		mainAuthEmail = payload?.data?.email ?? "";

		showGuestModal = false;
		showLoginModal = false;

		if (!odiuser.get()) {
			showJoinRequiredModal = true;
		}
	}

	function openAccountModal() {
		if (!odiuser.get()) {
			showGuestModal = true;
			return;
		}

		showAccountModal = true;
	}

	function closeAccountModal() {
		showAccountModal = false;
	}

	function goOdiJoin() {
		showJoinRequiredModal = false;
		goto("/odi/join");
	}

	async function logoutMainAuth() {
		await Promise.all([
			fetch(`${API}/auth/logout`, {
				method: "POST",
				credentials: "include"
			}).catch(() => null),
			odiuser.logout().catch(() => null)
		]);

		auth.logout();
		odiuser.clear();

		showJoinRequiredModal = false;
		showGuestModal = true;
	}
</script>

<div class="layout">
	{#if !sidebarOpen}
		<button
			type="button"
			class="sidebar-open clickable"
			aria-label="사이드바 열기"
			onclick={() => (sidebarOpen = true)}
		>
			<span></span><span></span><span></span>
		</button>
	{/if}

	{#if sidebarOpen}
		<button
			type="button"
			class="sidebar-backdrop"
			aria-label="메뉴 닫기"
			onclick={() => (sidebarOpen = false)}
		></button>
	{/if}

	<div class:open={sidebarOpen} class="sidebar">
		<NavigationBar
			onNewSession={openStartModal}
			onOpenAccount={openAccountModal}
			onCloseMobile={() => (sidebarOpen = false)}
		/>
	</div>

	<main class:sidebar-expanded={sidebarOpen} class="content">
		{@render children()}
	</main>
</div>

{#if showStartModal}
	<SessionStartModal
		onclose={closeStartModal}
		onselect={selectSessionType}
		onload={loadPreviousSession}
	/>
{/if}

{#if showGuestModal && !checkingAccess}
	<OdiGuestModal
		onClose={closeGuestModal}
		onRegister={openRegisterPage}
		onLogin={openLoginModal}
	/>
{/if}

{#if showLoginModal}
	<LoginModal
		onClose={closeLoginModal}
		onLoginSuccess={handleLoginSuccess}
	/>
{/if}

{#if showAccountModal}
	<AccountModal onClose={closeAccountModal} />
{/if}

{#if showJoinRequiredModal && !checkingAccess}
	<OdiJoinRequiredModal
		userName={mainAuthName}
		userEmail={mainAuthEmail}
		onJoin={goOdiJoin}
		onLogout={logoutMainAuth}
	/>
{/if}

<style>
	.layout {
		min-height: 100vh;
		background: var(--background);
	}

	.sidebar {
		position: fixed;
		top: 0;
		left: 0;
		width: 260px;
		height: 100vh;
		z-index: 100;
		transform: translateX(-100%);
		transition: transform 180ms ease;
	}

	.sidebar.open {
		transform: translateX(0);
	}

	.content {
		min-height: 100vh;
		min-width: 0;
		margin-left: 0;
		padding: 0;
		overflow-x: clip;
		overflow-y: auto;
		transition: margin-left 180ms ease;
	}

	.content.sidebar-expanded {
		margin-left: 260px;
	}

	.sidebar-open {
		position: fixed;
		top: 8px;
		left: 8px;
		z-index: 999;
		width: 34px;
		height: 34px;
		display: grid;
		place-content: center;
		gap: 5px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: 10px;
		background: var(--surface);
		box-shadow: var(--shadow-sm);
	}

	.sidebar-open span {
		width: 20px;
		height: 2px;
		border-radius: 2px;
		background: var(--brand-dark);
	}

	.sidebar-backdrop {
		display: none;
	}

	@media (max-width: 900px) {
		.sidebar-open {
			top: 14px;
			left: 14px;
			width: 44px;
			height: 44px;
		}

		.sidebar {
			z-index: 1001;
		}

		.sidebar-backdrop {
			position: fixed;
			inset: 0;
			z-index: 1000;
			display: block;
			background: rgba(3, 8, 18, 0.42);
		}

		.content {
			margin-left: 0;
			padding-top: 64px;
		}

		.content.sidebar-expanded {
			margin-left: 0;
		}
	}
</style>
