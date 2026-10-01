<script lang="ts">
	import { onMount, setContext } from 'svelte';
	import InstallApp from '$lib/personal-project/shared/InstallApp.svelte';
	import { request } from '$lib/personal-project/shared/api';
	import { page } from '$app/state';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import CalendarIcon from '$lib/personal-project/shared/CalendarIcon.svelte';
	import '../personal.css';
	import './calendar-shell.css';

	let { children } = $props();
	let activeView = $state('');
	let canAdmin = $state(false);
	setContext('calendar-navigation', {
		setView: (value: string) => {
			activeView = value;
		}
	});
	const currentView = $derived(
		page.url.pathname.includes('/student')
			? 'student'
			: (['day', 'week', 'tasks', ''].includes(page.url.pathname.split('/')[3] || '')
					? activeView
					: '') ||
					page.url.pathname.split('/')[3] ||
					'month'
	);
	let collapsed = $state(false),
		mobileOpen = $state(false),
		mobile = $state(false);
	const expanded = $derived(mobile ? mobileOpen : !collapsed);
	const views = [
		{ path: '/day', label: '일별 계획', icon: 'day' },
		{ path: '/week', label: '주간 시간표', icon: 'week' },
		{ path: '', label: '월간 캘린더', icon: 'month' },
		{ path: '/tasks', label: '해야 할 일', icon: 'tasks' },
		{ path: '/boards', label: '게시판', icon: 'boards' },
		{ path: '/resources', label: '자료 · PDF', icon: 'files' }
	] as const;
	onMount(() => {
		void request<{ canAdmin: boolean }>('/boards')
			.then((v) => (canAdmin = v.canAdmin))
			.catch(() => {});
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
				{#if canAdmin}<a
						href="/personal-project/calendar/admin"
						onclick={() => (mobileOpen = false)}
						><CalendarIcon name="settings" /><span class="ondo-nav-text">관리자</span></a
					>{/if}
			</nav>
			<p class="ondo-nav-label">학생서비스</p>
			<nav aria-label="학생서비스">
				{#each [{ path: 'timetable', label: '시간표', icon: 'week' }, { path: 'meals', label: '학식', icon: 'meals' }, { path: 'plan', label: '수강계획', icon: 'plan' }, { path: '', label: '학교 설정', icon: 'school' }] as const as item}
					<a
						href={`/personal-project/calendar/student${item.path ? '/' + item.path : ''}`}
						class:active={page.url.pathname ===
							`/personal-project/calendar/student${item.path ? '/' + item.path : ''}`}
						aria-current={page.url.pathname ===
						`/personal-project/calendar/student${item.path ? '/' + item.path : ''}`
							? 'page'
							: undefined}
						aria-label={item.label}
						title={item.label}
						onclick={() => {
							activeView = '';
							mobileOpen = false;
						}}><CalendarIcon name={item.icon} /><span class="ondo-nav-text">{item.label}</span></a
					>
				{/each}
			</nav>
			<p class="ondo-nav-label">연결</p>
			<nav aria-label="연결">
				<a
					href="/personal-project/calendar/projects"
					class:active={page.url.pathname.endsWith('/projects')}
					onclick={() => {
						activeView = '';
						mobileOpen = false;
					}}
					aria-label="프로젝트와 연결"
					title="프로젝트와 연결"
					><CalendarIcon name="projects" /><span class="ondo-nav-text">프로젝트와 연결</span></a
				>
			</nav>
		</div>
		<div class="ondo-sidebar-footer">
			<PersonalAccountCard />
			<div class="ondo-install"><InstallApp /></div>
		</div>
	</aside>
	<main id="calendar-content" class="ondo-main" tabindex="-1">{@render children()}</main>
</div>
