<!--
<script lang="ts">
 import { locale as siteLocale, copy as tr } from "$lib/odi/i18n";
	import { goto } from "$app/navigation";

	import DropdownItem from "./DropdownItem.svelte";

	import {
		account_icon as AccountCircle,
	} from "$lib/odi/icons";

	let {
		userName = "사용자",
		planName = "새싹 보이스",
		profileImage = AccountCircle,

		onLogout
	}: {
		userName?: string;
		planName?: string;
		profileImage?: string;

		onLogout?: () => void;
	} = $props();
</script>

<div class="dropdown">

	<div class="profile">

		<div class="left">

			<img
				class="profile-icon"
				src={AccountCircle}
				alt=""
			/>

			<div class="info">

				<span class="text-caption-medium">
					{userName}
				</span>

				<span class="plan text-caption-nav">
					{planName}
				</span>

			</div>

		</div>

		<span class="arrow">›</span>

	</div>

	<div class="divider"></div>

	<DropdownItem
		label={tr($siteLocale, "요금제 업그레이드")}
		//icon={Storefront}
		onclick={() => goto("/pricing")}
	/>

	<DropdownItem
		label={tr($siteLocale, "프로필")}
		//icon={AccountCircleOutline}
		onclick={() => goto("/profile")}
	/>

	<DropdownItem
		label={tr($siteLocale, "설정")}
		//icon={Settings}
		onclick={() => goto("/settings")}
	/>

	<div class="divider"></div>

	<DropdownItem
		label={tr($siteLocale, "도움말")}
		//icon={Help}
		onclick={() => goto("/help")}
	/>

	<DropdownItem
		label={tr($siteLocale, "로그아웃")}
		//icon={Logout}
		onclick={onLogout}
	/>

</div>

<style>

.dropdown{

	display:inline-flex;

	flex-direction:column;

	width:228px;

	padding:16px;

	gap:8px;

	border-radius:var(--radius-sm);

	background:rgb(from var(--purple-dark) r g b / 70%);
}

.profile{

	display:inline-flex;

	align-items:center;
	justify-content:space-between;

	width:212px;
	height:50px;

	padding:11px;

	color:var(--surface);
}

.left{

	display:flex;

	align-items:center;

	gap:10px;
}

.profile-icon{

	width:32px;
	height:32px;

	flex-shrink:0;
}

.info{

	display:flex;

	flex-direction:column;

	align-items:flex-start;

	gap:2px;
}

.plan{

	color:var(--primary);
}

.arrow{

	font-size:20px;

	line-height:1;
}

.divider{

	width:100%;
	height:1px;

	background:rgb(from var(--surface) r g b / 20%);
}

</style>
-->

<!-- src/lib/odi/components/navigation/ProfileDropdown.svelte -->
<script lang="ts">
	import DropdownItem from './DropdownItem.svelte';
	import { locale, setLocale, message as t, copy } from '$lib/odi/i18n';

	import { account_icon as AccountCircle } from '$lib/odi/icons';

	let {
		userName = '사용자',
		planName = '새싹 보이스',
		profileImage = AccountCircle,
		onOpenAccount,
        loggedIn = true,
		onOpenSettings,
		onLogout
	}: {
		userName?: string;
		planName?: string;
		profileImage?: string;
		onOpenAccount?: () => void;
        loggedIn?: boolean;
		onOpenSettings?: () => void;
		onLogout?: () => void;
	} = $props();
</script>

<div class="dropdown">
	<button type="button" class="profile clickable" onclick={onOpenAccount}>
		<div class="left">
			<img class="profile-icon" src={profileImage} alt="" />

			<div class="info">
				<span class="text-caption-medium">{userName}</span>
				<span class="plan text-caption-nav">{copy($locale, planName)}</span>
			</div>
		</div>

		<span class="arrow">›</span>
	</button>

	<div class="divider"></div>
    <div class="language"><span>{t($locale, 'language')}</span><div role="group" aria-label={t($locale, 'language')}><button type="button" aria-pressed={$locale === 'ko'} onclick={() => setLocale('ko')}>한국어</button><button type="button" aria-pressed={$locale === 'en'} onclick={() => setLocale('en')}>English</button></div></div>
    <div class="divider"></div>
    {#if loggedIn}
	<DropdownItem label={copy($locale, "요금제 업그레이드")} disabled status={copy($locale, "메뉴 준비 중")} />

	<DropdownItem label={copy($locale, "회원정보 수정")} onclick={onOpenAccount} />

	<DropdownItem label={copy($locale, "설정")} onclick={onOpenSettings} />

	<div class="divider"></div>

	<DropdownItem label={copy($locale, "도움말")} disabled status={copy($locale, "메뉴 준비 중")} />

	<DropdownItem label={copy($locale, "로그아웃")} onclick={onLogout} />
    {:else}<DropdownItem label={t($locale, 'signIn')} onclick={onOpenAccount} />{/if}
</div>

<style>
    .language {display:grid;gap:8px;padding:4px 8px;color:white;font-size:13px}
    .language div {display:flex;gap:6px}
    .language button {flex:1;border:1px solid #7777a0;background:transparent;color:white;border-radius:6px;padding:7px 4px;cursor:pointer}
    .language button[aria-pressed="true"] {background:white;color:#17163f}

	.dropdown {
		display: inline-flex;
		flex-direction: column;
		box-sizing: border-box;
		width: 228px;
		padding: 12px;
		gap: 8px;
		border-radius: var(--radius-sm);
		background: var(--purple-dark);
		box-shadow: 0 14px 36px rgba(3, 4, 40, 0.32);
		overflow: hidden;
	}

	.profile {
		display: inline-flex;
		align-items: center;
		justify-content: space-between;
		box-sizing: border-box;
		width: 100%;
		height: 50px;
		padding: 9px 8px;
		color: var(--surface);
		border-radius: var(--radius-sm);
		text-align: left;
	}

	.profile:hover {
		background: rgb(from var(--surface) r g b / 8%);
	}

	.left {
		display: flex;
		align-items: center;
		min-width: 0;
		gap: 10px;
	}

	.profile-icon {
		width: 32px;
		height: 32px;
		flex-shrink: 0;
	}

	.info {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		min-width: 0;
		gap: 2px;
	}

	.info span {
		max-width: 132px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.plan {
		color: var(--primary);
	}

	.arrow {
		font-size: 20px;
		line-height: 1;
	}

	.divider {
		width: 100%;
		height: 1px;
		background: rgb(from var(--surface) r g b / 20%);
	}
</style>
