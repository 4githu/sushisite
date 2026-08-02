<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import '../personal.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>온도 캘린더</title>
	<meta name="description" content="서비스 일정과 개인 일정을 모아보는 독립 캘린더" />
</svelte:head>

<div class="personal-shell calendar-system">
	<aside class="sidebar calendar-sidebar">
		<button
			class="brand"
			onclick={() => goto('/personal-project/calendar')}
			aria-label="캘린더 홈으로"
		>
			<span class="brand-mark">O</span>
			<span><b>온도 캘린더</b><small>일정을 모으는 독립 공간</small></span>
		</button>
		<nav aria-label="캘린더">
			<a
				class:active={page.url.pathname === '/personal-project/calendar'}
				href="/personal-project/calendar"
			>
				<span class="nav-icon">◇</span>월간 캘린더
			</a>
			<a
				class:active={page.url.pathname === '/personal-project/calendar/week'}
				href="/personal-project/calendar/week"
			>
				<span class="nav-icon">▦</span>주간 시간표
			</a>
		</nav>
		<PersonalAccountCard />
	</aside>
	<main class="personal-main">
		{@render children()}
	</main>
</div>
