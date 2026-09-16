<script lang="ts">
	import { onMount } from 'svelte';
	let { service = 'calendar' }: { service?: 'calendar' | 'aura' } = $props();
	type InstallPrompt = Event & {
		prompt: () => Promise<void>;
		userChoice: Promise<{ outcome: string }>;
	};
	let promptEvent = $state<InstallPrompt | null>(null),
		installed = $state(false),
		hint = $state('');
	onMount(() => {
		installed = matchMedia('(display-mode: standalone)').matches;
		const handler = (e: Event) => {
			e.preventDefault();
			promptEvent = e as InstallPrompt;
		};
		window.addEventListener('beforeinstallprompt', handler);
		if ('serviceWorker' in navigator)
			void navigator.serviceWorker
				.register('/personal-sw.js', { scope: '/personal-project/' })
				.catch(() => {});
		return () => window.removeEventListener('beforeinstallprompt', handler);
	});
	async function install() {
		if (promptEvent) {
			await promptEvent.prompt();
			installed = (await promptEvent.userChoice).outcome === 'accepted';
			promptEvent = null;
		} else hint = 'Chrome 메뉴(⋮)에서 “홈 화면에 추가” 또는 “앱 설치”를 선택하세요.';
	}
</script>

<svelte:head
	><link rel="manifest" href={`/pwa/${service}/manifest.webmanifest`} /><meta
		name="theme-color"
		content="#245ac7"
	/><meta name="mobile-web-app-capable" content="yes" /></svelte:head
>
{#if !installed}<button class="install-app" onclick={install}>앱으로 설치</button>{/if}
{#if hint}<p class="install-hint" role="status">{hint}</p>{/if}

<style>
	.install-app {
		margin: 16px 0 8px;
		border: 1px solid #d9e1ed;
		border-radius: 8px;
		background: white;
		padding: 10px 12px;
		color: #315ba3;
		cursor: pointer;
		font-size: 13px;
	}
	.install-hint {
		font-size: 12px;
		color: #687990;
		line-height: 1.6;
		margin: 4px 0 12px;
	}
</style>
