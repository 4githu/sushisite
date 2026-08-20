<!--
<script lang="ts">
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
		label="요금제 업그레이드"
		//icon={Storefront}
		onclick={() => goto("/pricing")}
	/>

	<DropdownItem
		label="프로필"
		//icon={AccountCircleOutline}
		onclick={() => goto("/profile")}
	/>

	<DropdownItem
		label="설정"
		//icon={Settings}
		onclick={() => goto("/settings")}
	/>

	<div class="divider"></div>

	<DropdownItem
		label="도움말"
		//icon={Help}
		onclick={() => goto("/help")}
	/>

	<DropdownItem
		label="로그아웃"
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
	import DropdownItem from "./DropdownItem.svelte";

	import {
		account_icon as AccountCircle
	} from "$lib/odi/icons";

	let {
		userName = "사용자",
		planName = "새싹 보이스",
		profileImage = AccountCircle,
		onOpenAccount,
		onLogout
	}: {
		userName?: string;
		planName?: string;
		profileImage?: string;
		onOpenAccount?: () => void;
		onLogout?: () => void;
	} = $props();
</script>

<div class="dropdown">
	<button type="button" class="profile clickable" onclick={onOpenAccount}>
		<div class="left">
			<img class="profile-icon" src={profileImage} alt="" />

			<div class="info">
				<span class="text-caption-medium">{userName}</span>
				<span class="plan text-caption-nav">{planName}</span>
			</div>
		</div>

		<span class="arrow">›</span>
	</button>

	<div class="divider"></div>

	<DropdownItem label="요금제 업그레이드" disabled status="준비 중" />

	<DropdownItem label="회원정보 수정" onclick={onOpenAccount} />

	<DropdownItem label="설정" disabled status="준비 중" />

	<div class="divider"></div>

	<DropdownItem label="도움말" disabled status="준비 중" />

	<DropdownItem label="로그아웃" onclick={onLogout} />
</div>


<style>
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
