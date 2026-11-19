<script lang="ts">
	import { onMount, setContext } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	import InstallApp from '$lib/personal-project/shared/InstallApp.svelte';
	import { page } from '$app/state';
	import type { MemoBridge } from '$lib/personal-project/shared/memo-context';
	import { installDialogDismissal } from '$lib/personal-project/shared/dismiss-dialogs';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import QuickCapture from '$lib/personal-project/shared/QuickCapture.svelte';
	import CalendarIcon from '$lib/personal-project/shared/CalendarIcon.svelte';
	import '../personal.css';
	import './calendar-shell.css';

	let { children } = $props();
	let activeView = $state('');
	const memoBridge = $state<MemoBridge>({ day: '', modalOpen: false });
	setContext('netaq-memo', memoBridge);
	let shell: HTMLDivElement;
	onMount(() => installDialogDismissal(shell));
	setContext('calendar-navigation', {
		setView: (value: string) => {
			activeView = value;
		}
	});
	const rawView = $derived(
		page.url.pathname.includes('/student')
			? 'student'
			: (['today', 'day', 'week', 'tasks', ''].includes(page.url.pathname.split('/')[3] || '')
					? activeView
					: '') ||
					page.url.pathname.split('/')[3] ||
					'month'
	);
	const currentView = $derived(
		rawView === 'day' ? 'today' : rawView === 'week' ? 'month' : rawView
	);
	let collapsed = $state(false),
		mobileOpen = $state(false),
		mobile = $state(false);
	const expanded = $derived(mobile ? mobileOpen : !collapsed);
	const icons: Record<string, string> = {
		day: 'e6da8',
		month: '64c4e',
		tasks: '70e80',
		files: 'd3042',
		boards: 'e94ee',
		school: '707e4',
		plan: '9012e',
		meals: 'f4a60',
		week: '707e4'
	};
	const views = [
		{ path: '/today', label: '오늘', icon: 'day' },
		{ path: '', label: '캘린더', icon: 'month' },
		{ path: '/tasks', label: '해야 할 일', icon: 'tasks' },
		{ path: '/drive', label: '내 드라이브', icon: 'files' },
		{ path: '/boards', label: '게시판', icon: 'boards' }
	] as const;
	onMount(() => {
		void request('/membership', { method: 'POST' }).catch(() => {});
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

<div bind:this={shell} class="ondo-shell" class:rail={collapsed} class:mobile-open={mobileOpen}>
	<a class="ondo-skip" href="#calendar-content">일정으로 건너뛰기</a>
	<aside class="ondo-sidebar" aria-label="캘린더 탐색">
		<div class="ondo-brand-row">
			<a
				class="ondo-brand"
				href="/personal-project/calendar/today"
				aria-label="NETAQ 홈"
				title="NETAQ 홈"
			>
				<img class="ondo-logo" src="/netaq-design/2ffec.svg" width="21" height="21" alt="" />
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
			<p class="ondo-nav-label">내 공간</p>
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
						<span
							class="ondo-nav-icon"
							style={`--nav-icon:url(/netaq-design/${icons[view.icon]}.svg)`}
							aria-hidden="true"
						></span><span class="ondo-nav-text">{view.label}</span>
					</a>
				{/each}
			</nav>
			<p class="ondo-nav-label">학생서비스</p>
			<nav aria-label="학생서비스">
				{#each [{ path: 'timetable', label: '시간표', icon: 'week' }, { path: 'meals', label: '학식', icon: 'meals' }, { path: 'plan', label: '수강계획', icon: 'plan' }] as const as item}
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
						}}
						><span
							class="ondo-nav-icon"
							style={`--nav-icon:url(/netaq-design/${icons[item.icon]}.svg)`}
							aria-hidden="true"
						></span><span class="ondo-nav-text">{item.label}</span></a
					>
				{/each}
			</nav>
		</div>
		<div class="ondo-sidebar-footer">
			<PersonalAccountCard />
			<div class="ondo-install"><InstallApp /></div>
		</div>
	</aside>
	<main id="calendar-content" class="ondo-main" tabindex="-1">
		<div class="ondo-page-actions"><QuickCapture /></div>
		{@render children()}
	</main>
	<nav class="ondo-bottom-nav" aria-label="주요 메뉴">
		{#each [{ path: '/today', label: '오늘', icon: 'day' }, { path: '', label: '캘린더', icon: 'month' }, { path: '/tasks', label: '할 일', icon: 'tasks' }, { path: '/student', label: '학생', icon: 'school' }] as const as item}
			<a
				href={`/personal-project/calendar${item.path}`}
				aria-current={currentView === (item.path.slice(1) || 'month') ? 'page' : undefined}
				onclick={() => (mobileOpen = false)}
				><CalendarIcon name={item.icon} size={22} /><span>{item.label}</span></a
			>
		{/each}<button onclick={toggle} aria-expanded={mobileOpen} aria-controls="ondo-navigation"
			><CalendarIcon name="panel" size={22} /><span>더보기</span></button
		>
	</nav>
</div>
