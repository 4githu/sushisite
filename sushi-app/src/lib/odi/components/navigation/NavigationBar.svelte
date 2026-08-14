<!--
<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/state";
	import { onMount } from "svelte";

	import Button from "$lib/odi/components/common/Button.svelte";
	import NavigationItem from "./NavigationItem.svelte";
	import ProfileDropdown from "./ProfileDropdown.svelte";

	import Logo from "$lib/odi/icons/LOGO.svg";

	import {
		account_icon as AccountCircle,
		naviplus as Add,
		home as Home,
		kid_star as Favorites,
		list_alt as Report,
		voice_selection as MyPractice,
		sprout
	} from "$lib/odi/icons";

	let {
		userName = "사용자",
		planName = "새싹 보이스",
		onNewSession
	}: {
		userName?: string;
		planName?: string;
		onNewSession?: () => void;
	} = $props();


	let showProfile = $state(false);

	let navigation: HTMLElement;

	const currentPage = $derived.by(() => {
		const pathname = page.url.pathname;

		if (pathname.startsWith("/odi/report")) return "report";
		if (pathname.startsWith("/odi/practice")) return "practice";
		if (pathname.startsWith("/odi/favorites")) return "favorites";
		if (pathname == "/odi") return "home";

		return null;
	});

	function toggleProfile(event: MouseEvent) {
		event.stopPropagation();
		showProfile = !showProfile;
	}

	function logout() {
		console.log("logout");
	}

	onMount(() => {
		function handleOutside(event: MouseEvent) {
			if (
				showProfile &&
				navigation &&
				!navigation.contains(event.target as Node)
			) {
				showProfile = false;
			}
		}

		document.addEventListener("click", handleOutside);

		return () => {
			document.removeEventListener("click", handleOutside);
		};
	});
</script>

<aside
	class="navigation"
	bind:this={navigation}
>

	<div class="top">

		<div class="logo-area">

			<img
				class="logo"
				src={Logo}
				alt="Re:hear"
			/>

			<p class="text-caption slogan">
				Practice. Feedback. Real Growth.
			</p>

		</div>

		<Button
			width="212px"
			leadingIcon={Add}
			onclick={onNewSession}
		>
			New Session
		</Button>

		<div class="menu">

			<NavigationItem
				label="Home"
				icon={Home}
				selected={currentPage === "home"}
				onclick={() => goto("/odi")}
			/>

			<NavigationItem
				label="Favorites"
				icon={Favorites}
				selected={currentPage === "favorites"}
				onclick={() => goto("/odi/favorites")}
			/>

			<NavigationItem
				label="Report"
				icon={Report}
				selected={currentPage === "report"}
				onclick={() => goto("/odi/report")}
			/>

			<NavigationItem
				label="My Practice"
				icon={MyPractice}
				selected={currentPage === "practice"}
				onclick={() => goto("/odi/practice")}
			/>

		</div>

	</div>

	<div class="bottom">

		<button
			type="button"
			class="my-page clickable"
			onclick={toggleProfile}
		>

			<div class="my-page-left">

				<img
					class="profile-icon"
					src={AccountCircle}
					alt=""
				/>

				<span class="text-body-medium">
					My page
				</span>

			</div>

			<span class="arrow">
				›
			</span>

		</button>

		{#if showProfile}

			<div class="profile-dropdown">

				<ProfileDropdown
					{userName}
					{planName}
					onLogout={logout}
				/>

			</div>

		{/if}

	</div>

</aside>

<style>

.navigation{

	display:flex;
	flex-direction:column;
	justify-content:space-between;

	width:260px;
	height:100vh;

	padding:
		38px
		17px
		18px;

	background:var(--brand-dark);

	position:relative;

	flex-shrink:0;
}

.top{

	display:flex;
	flex-direction:column;

	align-items:center;

	gap:28px;
}

.logo-area{

	width:222px;

	display:flex;
	flex-direction:column;

	align-items:flex-start;

	gap:8px;
}

.logo{

	width:150px;
	height:auto;
}

.slogan{

	color:var(--surface);
}

.menu{

	display:flex;
	flex-direction:column;

	gap:8px;
}

.bottom{

	position:relative;
}

.my-page{

	display:inline-flex;

	align-items:center;
	justify-content:space-between;

	width:212px;
	height:50px;

	padding:
		11px
		11px
		11px
		0;

	border-radius:var(--radius-sm);

	color:var(--surface);

	background:transparent;

	transition:background var(--transition-fast);
}

.my-page:hover{

	background:rgb(from var(--surface) r g b / 8%);
}

.my-page-left{

	display:flex;

	align-items:center;

	gap:10px;
}

.profile-icon{

	width:36px;
	height:36px;

	flex-shrink:0;
}

.arrow{

	font-size:20px;

	line-height:1;

	user-select:none;
}

.profile-dropdown{

	position:absolute;

	left:0;
	bottom:60px;

	z-index:100;
}

</style>

-->
<!-- src/lib/odi/components/navigation/NavigationBar.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/state";
	import { onMount } from "svelte";
	import { auth } from "$lib/stores/mainauth";
	import { odiuser } from "$lib/odi/stores";
	import { API_BASE as API } from '$lib/config/api';

	import Button from "$lib/odi/components/common/Button.svelte";
	import NavigationItem from "./NavigationItem.svelte";
	import ProfileDropdown from "./ProfileDropdown.svelte";

	import Logo from "$lib/odi/icons/LOGO.svg";

	import {
		account_icon as AccountCircle,
		naviplus as Add,
		home as Home,
		kid_star as Favorites,
		list_alt as Report,
		voice_selection as MyPractice,
		sprout
	} from "$lib/odi/icons";

	let {
		userName = "사용자",
		planName = "새싹 보이스",
		onNewSession,
		onOpenAccount
	}: {
		userName?: string;
		planName?: string;
		onNewSession?: () => void;
		onOpenAccount?: () => void;
	} = $props();

	let showProfile = $state(false);
	let navigation: HTMLElement;

	const displayName = $derived($odiuser?.config?.profile?.nickname ?? auth.get()?.data?.name ?? userName);
	const displayLevel = $derived($odiuser?.config?.profile?.level ?? planName);
	const displayProfileImage = $derived($odiuser?.config?.profile?.profile_image || sprout);

	const currentPage = $derived.by(() => {
		const pathname = page.url.pathname;

		if (pathname.startsWith("/odi/report")) return "report";
		if (pathname.startsWith("/odi/practice")) return "practice";
		if (pathname.startsWith("/odi/favorites")) return "favorites";
		if (pathname == "/odi") return "home";

		return null;
	});

	function toggleProfile(event: MouseEvent) {
		event.stopPropagation();
		showProfile = !showProfile;
	}

	async function logout() {
		await Promise.all([
			fetch(`${API}/auth/logout`, {
				method: "POST",
				credentials: "include"
			}).catch(() => null),
			odiuser.logout().catch(() => null)
		]);

		auth.logout();
		showProfile = false;
		goto("/odi");
	}

	function openAccount() {
		showProfile = false;
		onOpenAccount?.();
	}

	onMount(() => {
		function handleOutside(event: MouseEvent) {
			if (showProfile && navigation && !navigation.contains(event.target as Node)) {
				showProfile = false;
			}
		}

		document.addEventListener("click", handleOutside);

		return () => {
			document.removeEventListener("click", handleOutside);
		};
	});
</script>

<aside class="navigation" bind:this={navigation}>
	<div class="top">
		<div class="logo-area">
			<img class="logo" src={Logo} alt="Re:hear" />
			<p class="text-caption slogan">Practice. Feedback. Real Growth.</p>
		</div>

		<Button width="212px" leadingIcon={Add} onclick={onNewSession}>
			New Session
		</Button>

		<div class="menu">
			<NavigationItem label="Home" icon={Home} selected={currentPage === "home"} onclick={() => goto("/odi")} />
			<NavigationItem label="Favorites" icon={Favorites} selected={currentPage === "favorites"} onclick={() => goto("/odi/favorites")} />
			<NavigationItem label="Report" icon={Report} selected={currentPage === "report"} onclick={() => goto("/odi/report")} />
			<NavigationItem label="My Practice" icon={MyPractice} selected={currentPage === "practice"} onclick={() => goto("/odi/practice")} />
		</div>
	</div>

	<div class="bottom">
		<button type="button" class="my-page clickable" onclick={toggleProfile}>
			<div class="my-page-left">
				<img class="profile-icon" src={displayProfileImage} alt="" />
				<span class="account-copy">
					<strong class="text-body-medium">{displayName}</strong>
					<small class="text-caption-nav">{displayLevel}</small>
				</span>
			</div>

			<span class="arrow">›</span>
		</button>

		{#if showProfile}
			<div class="profile-dropdown">
				<ProfileDropdown
					userName={displayName}
					planName={displayLevel}
					profileImage={displayProfileImage}
					onOpenAccount={openAccount}
					onLogout={logout}
				/>
			</div>
		{/if}
	</div>
</aside>

<style>
	.navigation {
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		width: 260px;
		height: 100vh;
		padding: 38px 17px 18px;
		background: var(--brand-dark);
		position: relative;
		flex-shrink: 0;
	}

	.top {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 28px;
	}

	.logo-area {
		width: 222px;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 8px;
	}

	.logo {
		width: 150px;
		height: auto;
	}

	.slogan {
		color: var(--surface);
	}

	.menu {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.bottom {
		position: relative;
	}

	.my-page {
		width: 226px;
		height: 56px;
		padding: 11px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-radius: var(--radius-sm);
		color: var(--surface);
	}

	.my-page:hover {
		background: rgb(from var(--surface) r g b / 8%);
	}

	.my-page-left {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.account-copy { display: grid; gap: 2px; text-align: left; }
	.account-copy strong { color: var(--surface); }
	.account-copy small { color: var(--primary); }

	.profile-icon {
		width: 32px;
		height: 32px;
	}

	.arrow {
		font-size: 20px;
		line-height: 1;
	}

	.profile-dropdown {
		position: absolute;
		left: 0;
		bottom: 64px;
		z-index: 10;
	}
</style>
<!---->
