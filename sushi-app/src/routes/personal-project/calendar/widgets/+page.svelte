<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	let code = $state(''),
		expires = $state(0),
		now = $state(Date.now()),
		busy = $state(false),
		message = $state(''),
		error = $state('');
	const remaining = $derived(Math.max(0, Math.ceil((expires - now) / 1000)));
	let timer: ReturnType<typeof setInterval>;
	onMount(() => {
		timer = setInterval(() => (now = Date.now()), 1000);
	});
	onDestroy(() => clearInterval(timer));
	async function pair() {
		busy = true;
		error = '';
		message = '';
		try {
			const result = await request<{ code: string; expiresIn: number }>('/calendar/widget/pair', {
				method: 'POST'
			});
			code = result.code;
			expires = Date.now() + result.expiresIn * 1000;
			now = Date.now();
			message = '아래 코드를 위젯 앱에 붙여넣으세요';
		} catch (e) {
			error = e instanceof Error ? e.message : '코드를 만들지 못했어요';
		} finally {
			busy = false;
		}
	}
	async function revoke() {
		busy = true;
		error = '';
		try {
			await request('/calendar/widget/devices', { method: 'DELETE' });
			message = '연결된 모든 위젯을 해제했어요';
			code = '';
		} catch (e) {
			error = e instanceof Error ? e.message : '연결을 해제하지 못했어요';
		} finally {
			busy = false;
		}
	}
	async function copy() {
		try {
			await navigator.clipboard.writeText(code);
			message = '연결 코드를 복사했어요';
		} catch {
			message = '코드를 선택해서 복사해주세요';
		}
	}
</script>

<svelte:head><title>위젯 · NETAQ</title></svelte:head>
<div class="widgets-page">
	<header>
		<h1>위젯</h1>
		<a href="/personal-project/calendar/projects">연결·프로젝트</a>
	</header>
	<div class="platforms">
		<section>
			<h2>Windows</h2>
			<p>바탕화면에서 일정·할 일·메모를 확인하고 바로 기록하세요.</p>
			<div class="widget-sample">
				<strong>오늘</strong>
				<div class="sample-event"><b>다음 일정</b><span>시작–종료 시간 · 장소</span></div>
				<span>할 일 완료 · 메모 이어 쓰기</span>
			</div>
			<a class="download" href="/downloads/windows-widget">Windows 설치 파일</a><small
				>Windows 10/11 x64 · 바탕화면 앱<br />서명되지 않은 직접 설치 파일입니다.</small
			>
		</section>
		<section>
			<h2>Android</h2>
			<p>홈 화면에 필요한 크기와 종류의 위젯을 추가하세요.</p>
			<div class="widget-sample">
				<strong>7가지 위젯</strong><span>다음 일정 2×2 · 오늘 일정 4×2</span><span
					>월간 · 주간 · 할 일 · 메모 · 일별 계획</span
				>
			</div>
			<a class="download" href="/downloads/android-widget">Android APK</a><small
				>Android 8 이상 · 직접 설치<br />기존 위젯 앱을 업데이트할 수 있어요.</small
			>
		</section>
	</div>
	<section class="pair">
		<h2>계정 연결</h2>
		<ol>
			<li>위젯 앱을 설치하고 실행하세요.</li>
			<li>연결 코드를 만들고 앱에 입력하세요.</li>
			<li>Android는 ‘홈 화면에 추가’, Windows는 원하는 위치와 크기를 정하세요.</li>
		</ol>
		<div class="actions">
			<button class="primary" disabled={busy} onclick={pair}
				>{code ? '새 연결 코드' : '연결 코드 만들기'}</button
			><button disabled={busy} onclick={revoke}>연결 모두 해제</button>
		</div>
		{#if code}<div class="pair-code">
				<input
					aria-label="위젯 연결 코드"
					value={code}
					readonly
					onclick={(e) => e.currentTarget.select()}
				/><button disabled={!remaining} onclick={copy}>복사</button><span
					>{remaining
						? `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')} 남음`
						: '만료됨 · 새 코드를 만들어주세요'}</span
				>
			</div>{/if}
		<p class="feedback" role="status">{busy ? '처리 중…' : message}</p>
		{#if error}<p role="alert">{error}</p>{/if}
	</section>
	<details>
		<summary>갱신과 연결에 대해</summary>
		<p>
			Windows는 실행 중 약 1분마다, Android는 약 30분마다 갱신해요. 새로고침 버튼으로 바로 확인할 수
			있고, 절전·오프라인 상태에서는 늦어질 수 있어요. 연결 실패 시 마지막 내용을 유지하며, 계정
			연결이 해제된 응답을 받으면 내용을 숨겨요.
		</p>
		<p>Windows의 Win+W 위젯 보드 대신 독립된 바탕화면 앱으로 실행됩니다.</p>
	</details>
</div>

<style>
	.widgets-page {
		max-width: 1000px;
		margin: auto;
		color: var(--ondo-ink);
	}
	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 32px;
	}
	h1 {
		font-size: 26px;
		margin: 0;
	}
	h2 {
		font-size: 20px;
		margin: 0 0 12px;
	}
	p,
	li {
		font-size: 14px;
		line-height: 1.7;
	}
	p,
	small {
		color: var(--ondo-muted);
	}
	a {
		color: inherit;
		font-size: 14px;
	}
	.platforms {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 40px;
	}
	.platforms section {
		min-width: 0;
	}
	.widget-sample {
		display: grid;
		gap: 12px;
		padding: 24px;
		background: var(--ondo-canvas, #f4f5f7);
		border-radius: 16px;
		margin: 20px 0;
		min-height: 170px;
		box-sizing: border-box;
	}
	.widget-sample > span {
		font-size: 13px;
		color: var(--ondo-muted);
	}
	.sample-event {
		border-left: 3px solid #27634b;
		padding-left: 12px;
		display: grid;
		gap: 4px;
	}
	.sample-event span {
		font-size: 12px;
		color: var(--ondo-muted);
	}
	.download {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 44px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		padding: 8px 16px;
		box-sizing: border-box;
		text-decoration: none;
		font-weight: 600;
	}
	small {
		display: block;
		font-size: 12px;
		line-height: 1.7;
		margin-top: 12px;
	}
	.pair {
		border-top: 1px solid var(--ondo-line);
		margin-top: 32px;
		padding-top: 24px;
	}
	ol {
		padding-left: 20px;
		margin: 16px 0 24px;
	}
	.actions {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
	}
	button {
		font: inherit;
		font-size: 14px;
		min-height: 44px;
		padding: 8px 16px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		background: white;
		color: var(--ondo-ink);
		cursor: pointer;
	}
	.primary {
		background: var(--ondo-accent);
		border-color: var(--ondo-accent);
		color: white;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.pair-code {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-top: 20px;
		align-items: center;
	}
	.pair-code input {
		font: inherit;
		min-width: 0;
		width: min(400px, 100%);
		padding: 12px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		background: var(--ondo-canvas, #f4f5f7);
	}
	.pair-code span {
		font-size: 13px;
		color: var(--ondo-muted);
	}
	.feedback {
		min-height: 24px;
		font-size: 13px;
	}
	p[role='alert'] {
		color: #b33625;
	}
	details {
		border-top: 1px solid var(--ondo-line);
		padding: 20px 0;
		margin-top: 16px;
	}
	summary {
		cursor: pointer;
		min-height: 44px;
		font-size: 14px;
	}
	@media (max-width: 760px) {
		.platforms {
			grid-template-columns: 1fr;
			gap: 32px;
		}
		header h1 {
			font-size: 23px;
		}
		.pair-code input {
			font-size: 16px;
		}
	}
</style>
