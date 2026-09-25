<script lang="ts">
	import { onMount, setContext } from 'svelte';
	import InstallApp from '$lib/personal-project/shared/InstallApp.svelte';
	import { page } from '$app/state';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import CalendarIcon from '$lib/personal-project/shared/CalendarIcon.svelte';
	import '../personal.css';
	import './calendar-shell.css';

	let { children } = $props();
	let activeView = $state('');
	setContext('calendar-navigation', {
		setView: (value: string) => {
			activeView = value;
		}
	});
	const currentView = $derived(activeView || page.url.pathname.split('/')[3] || 'month');
	let collapsed = $state(false),
		mobileOpen = $state(false),
		mobile = $state(false);
	const expanded = $derived(mobile ? mobileOpen : !collapsed);
	const views = [
		{ path: '/day', label: '일별 계획', icon: 'day' },
		{ path: '/week', label: '주간 시간표', icon: 'week' },
		{ path: '', label: '월간 캘린더', icon: 'month' },
		{ path: '/tasks', label: '해야 할 일', icon: 'tasks' },
        { path: '/projects', label: '프로젝트와 연결', icon: 'tasks' },
        { path: '/student', label: '학생 서비스', icon: 'week' }
	] as const;
	onMount(() => {
		try {
			collapsed = localStorage.getItem('ondo.sidebar-collapsed') === 'true';
		} catch {
			/* Preference storage is optional. */
		}
		const media = matchMedia('(max-width: 760px)');
		const sync = () => {
			mobile = media.matches;
		};
		sync();
		media.addEventListener('change', sync);
		return () => media.removeEventListener('change', sync);
	});
	function toggle() {
		if (mobile) mobileOpen = !mobileOpen;
		else {
			collapsed = !collapsed;
			try {
				localStorage.setItem('ondo.sidebar-collapsed', String(collapsed));
			} catch {
				/* Keep the control working without storage. */
			}
		}
	}
</script>

<svelte:head>
	<title>NETAQ</title>
	<meta name="description" content="계획과 일정을 한눈에 정리하는 NETAQ" />
</svelte:head>

<div class="ondo-shell" class:rail={collapsed} class:mobile-open={mobileOpen}>
	<a class="ondo-skip" href="#calendar-content">일정으로 건너뛰기</a>
	<aside class="ondo-sidebar" aria-label="캘린더 탐색">
		<div class="ondo-brand-row">
			<a
				class="ondo-brand"
				href="/personal-project/calendar"
				aria-label="NETAQ 홈"
				title="NETAQ 홈"
			>
				<span class="ondo-symbol" aria-hidden="true"><i></i></span>
				<span class="ondo-wordmark">NETAQ<span>CALENDAR</span></span>
			</a>
			<button
				class="ondo-toggle"
				onclick={toggle}
				aria-label={expanded ? '사이드바 접기' : '사이드바 펼치기'}
				aria-expanded={expanded}
				aria-controls="ondo-navigation"
				title={expanded ? '사이드바 접기' : '사이드바 펼치기'}
				><CalendarIcon name="panel" size={18} /></button
			>
		</div>
		<div id="ondo-navigation" class="ondo-navigation">
			<p class="ondo-nav-label">내 워크스페이스</p>
			<nav aria-label="캘린더">
				{#each views as view}
					<a
						href={`/personal-project/calendar${view.path}`}
						class:active={currentView === (view.path.slice(1) || 'month')}
						aria-current={currentView === (view.path.slice(1) || 'month') ? 'page' : undefined}
						aria-label={view.label}
						title={view.label}
						onclick={() => (mobileOpen = false)}
					>
						<CalendarIcon name={view.icon} /><span class="ondo-nav-text">{view.label}</span>
					</a>
				{/each}
			</nav>
		</div>
		<div class="ondo-sidebar-footer">
			<PersonalAccountCard />
			<div class="ondo-install"><InstallApp /></div>
		</div>
	</aside>
	<main id="calendar-content" class="ondo-main" tabindex="-1">{@render children()}</main>
</div>
