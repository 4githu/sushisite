<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import '../personal.css';

	let { children } = $props();
	let sidebarCollapsed = $state(false);

	const links = [
		{ href: '/personal-project/aura', label: '클리닉 홈', icon: '✦' },
		{ href: '/personal-project/aura/schools', label: '학교별 리포트', icon: '▦' },
		{ href: '/personal-project/aura/settlements', label: '월별 정산', icon: '₩' }
	];
</script>

<svelte:head>
	<title>아우라 클리닉</title>
	<meta name="description" content="학생, 클리닉, 리포트와 정산을 관리하는 아우라 시스템" />
</svelte:head>


<div class="personal-shell aura-system" class:sidebar-collapsed={sidebarCollapsed}>
	<aside class="sidebar aura-sidebar">
		<button
			class="sidebar-toggle"
			type="button"
			onclick={() => (sidebarCollapsed = !sidebarCollapsed)}
			aria-label={sidebarCollapsed ? '사이드바 펼치기' : '사이드바 접기'}
			title={sidebarCollapsed ? '사이드바 펼치기' : '사이드바 접기'}
		>{sidebarCollapsed ? '›' : '‹'}</button>
		<button class="brand" onclick={() => goto('/personal-project/aura')} aria-label="아우라 홈으로">
			<span class="brand-mark aura-mark">A</span>
			<span><b>아우라</b><small>클리닉 운영 시스템</small></span>
		</button>
		<nav aria-label="아우라 클리닉">
			{#each links as link}
				<a href={link.href} class:active={page.url.pathname === link.href}>
					<span class="nav-icon">{link.icon}</span>{link.label}
				</a>
			{/each}
		</nav>
		<a class="calendar-link" href="/personal-project/calendar">◇ 연결된 캘린더에서 보기</a>
		<PersonalAccountCard />
	</aside>
	<main class="personal-main">
		{@render children()}
	</main>
</div>

<style>
	.aura-sidebar {
		/* 공통 사이드바와 달리, 아우라는 화면 스크롤과 무관하게 고정합니다. */
		position: fixed;
		left: 0;
		top: 0;
		width: 236px;
		box-sizing: border-box;
		height: 100dvh;
		background: #f0ece8;
	}
	:global(.aura-system .personal-main) { grid-column: 2; }
	.sidebar-toggle {
		position: absolute;
		top: 14px;
		right: -14px;
		z-index: 4;
		width: 28px;
		height: 28px;
		border: 1px solid var(--pp-line);
		border-radius: 50%;
		background: #fff;
		color: var(--pp-sage-dark);
		font-size: 20px;
		line-height: 1;
		cursor: pointer;
	}
	:global(.aura-system.sidebar-collapsed) {
		grid-template-columns: 72px minmax(0, 1fr);
	}
	:global(.aura-system.sidebar-collapsed .sidebar) {
		width: 72px;
		padding: 36px 12px 24px;
	}
	:global(.aura-system.sidebar-collapsed .brand) {
		justify-content: center;
		padding: 0 0 34px;
	}
	:global(.aura-system.sidebar-collapsed .brand > span:last-child),
	:global(.aura-system.sidebar-collapsed .calendar-link),
	:global(.aura-system.sidebar-collapsed .account-button > span:nth-child(2)),
	:global(.aura-system.sidebar-collapsed .account-button > i) {
		display: none;
	}
	:global(.aura-system.sidebar-collapsed nav a) {
		justify-content: center;
		padding: 11px 0;
		font-size: 0;
	}
	:global(.aura-system.sidebar-collapsed .nav-icon) { font-size: 18px; }
	:global(.aura-system.sidebar-collapsed .account-button) {
		display: grid;
		grid-template-columns: 1fr;
		justify-items: center;
		padding: 8px;
	}
	@media (max-width: 820px) {
		/* 분할 화면에서도 아우라 내비게이션은 화면 높이를 계속 채웁니다. */
		:global(.aura-system) {
			display: grid;
			grid-template-columns: 72px minmax(0, 1fr);
			min-height: 100dvh;
		}
		:global(.aura-system .sidebar) {
			position: fixed;
			left: 0;
			top: 0;
			width: 236px;
			height: 100dvh;
			padding: 36px 12px 24px;
		}
		:global(.aura-system.sidebar-collapsed .sidebar) { width: 72px; }
		:global(.aura-system.sidebar-collapsed .brand) {
			justify-content: center;
			padding: 0 0 34px;
		}
		:global(.aura-system.sidebar-collapsed .brand > span:last-child),
		:global(.aura-system.sidebar-collapsed .calendar-link),
		:global(.aura-system.sidebar-collapsed .account-button > span:nth-child(2)),
		:global(.aura-system.sidebar-collapsed .account-button > i) { display: none; }
		:global(.aura-system nav) { display: grid; overflow: visible; }
		:global(.aura-system.sidebar-collapsed nav a) {
			justify-content: center;
			padding: 11px 0;
			font-size: 0;
		}
		:global(.aura-system.sidebar-collapsed .nav-icon) { font-size: 18px; }
		:global(.aura-system.sidebar-collapsed .account-button) {
			display: grid;
			grid-template-columns: 1fr;
			justify-items: center;
			padding: 8px;
		}
		.sidebar-toggle { display: grid; place-items: center; }
	}

	.aura-mark {
		background: #8d6f63;
	}

	.calendar-link {
		margin: 18px 8px 0;
		padding: 10px;
		border: 1px solid #d8d5ca;
		border-radius: 8px;
		color: var(--pp-sage-dark);
		font-size: 10px;
		font-weight: 700;
		text-decoration: none;
	}
</style>
