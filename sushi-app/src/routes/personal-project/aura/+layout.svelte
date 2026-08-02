<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import '../personal.css';

	let { children } = $props();

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

<div class="personal-shell aura-system">
	<aside class="sidebar aura-sidebar">
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
		background: #f0ece8;
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
