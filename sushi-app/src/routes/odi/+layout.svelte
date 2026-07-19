<!-- src/routes/odi/+layout.svelte -->
<script lang="ts">
	import "$lib/odi/styles/globals.css";

	import type { Snippet } from "svelte";
	import { onMount } from "svelte";
	import { goto } from "$app/navigation";
	import { page } from "$app/state";

	import { auth } from "$lib/stores/mainauth";
	import { odiuser } from "$lib/odi/stores";

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

	let mainAuthName = $state("");
	let mainAuthEmail = $state("");

	const isAuthExceptionPage = $derived(page.url.pathname.startsWith("/odi/join"));

	onMount(async () => {
		if (isAuthExceptionPage) {
			checkingAccess = false;
			return;
		}

		const result = await odiuser.checkAccess();

		if (result.status === "odi_authenticated") {
			showGuestModal = false;
			showJoinRequiredModal = false;
			checkingAccess = false;
			return;
		}

		if (result.status === "main_authenticated_needs_odi_join") {
			const payload = auth.get();

			mainAuthName = payload?.data?.name ?? "사용자";
			mainAuthEmail = payload?.data?.email ?? "";

			showJoinRequiredModal = true;
			checkingAccess = false;
			return;
		}

		showGuestModal = true;
		checkingAccess = false;
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
		const API = import.meta.env.VITE_SUSHIFASTURL;

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
	<div class="sidebar">
		<NavigationBar
			userName="리히어"
			planName="Plus"
			onNewSession={openStartModal}
			onOpenAccount={openAccountModal}
		/>
	</div>

	<main class="content">
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
	}

	.content {
		min-height: 100vh;
		margin-left: 260px;
		padding: 36px 48px;
		overflow: auto;
	}
</style>