<script lang="ts">
	import { onMount, tick } from 'svelte';
	import PersonalAccountCard from '$lib/personal-project/shared/PersonalAccountCard.svelte';
	import ServiceSwitcher from '$lib/personal-project/shared/ServiceSwitcher.svelte';
	import { playerApi, googleConnectUrl, type GooglePlayerAccount, type GooglePlaylist, type PlayerCollection, type PlayerSummary, type PlayerTrack } from '$lib/personal-project/player/api';
	import { PlayQueue } from '$lib/personal-project/player/queue';
	import '../personal.css';

	type YTPlayer = {
		cueVideoById(id: string): void;
		loadVideoById(id: string): void;
		playVideo(): void;
		pauseVideo(): void;
		setPlaybackRate(rate: number): void;
		getPlaybackRate(): number;
		getAvailablePlaybackRates(): number[];
		destroy(): void;
	};
	type YouTubeWindow = Window & {
		YT?: { Player: new (element: HTMLElement, options: Record<string, unknown>) => YTPlayer };
		onYouTubeIframeAPIReady?: () => void;
	};

	let summaries = $state<PlayerSummary[]>([]);
	let collection = $state<PlayerCollection | null>(null);
	let accounts = $state<GooglePlayerAccount[]>([]);
	let googlePlaylists = $state<GooglePlaylist[]>([]);
	let selectedAccount = $state<number | null>(null);
	let needsConsentRetry = $state(false);
	let newName = $state('');
	let sourceUrl = $state('');
	let videoUrl = $state('');
	let error = $state('');
	let notice = $state('');
	let loading = $state(false);
	let importing = $state(false);
	let accountLoading = $state(false);
	let current = $state<PlayerTrack | null>(null);
	let playing = $state(false);
	let playerReady = $state(false);
	let appliedRate = $state(1);
	let availableRates = $state<number[]>([]);
	let youtubeHost = $state<HTMLDivElement>();
	let youtubePlayer: YTPlayer | null = null;
	let queue: PlayQueue | null = null;
	let failedTrackIds = new Set<number>();

	const enabledCount = $derived(collection?.tracks.filter((track) => track.enabled).length ?? 0);
	const visiblePlaylists = $derived(googlePlaylists.filter((item) => item.count > 0 || collection?.sources.some((source) => source.playlist_id === item.id)));

	function message(cause: unknown) {
		error = cause instanceof Error ? cause.message : '요청을 처리하지 못했습니다.';
	}

	async function refreshSummaries() {
		summaries = await playerApi.collections();
	}

	function replaceCollection(next: PlayerCollection, reset = false) {
		if (reset || collection?.id !== next.id) {
			youtubePlayer?.pauseVideo();
			current = null;
			playing = false;
			queue = new PlayQueue(next);
			failedTrackIds = new Set();
		} else {
			queue?.reset(next);
			current = next.tracks.find((track) => track.id === current?.id) ?? null;
		}
		collection = next;
	}

	async function loadCollection(id: number) {
		try {
			error = '';
			replaceCollection(await playerApi.collection(id), true);
			localStorage.setItem('personal-player-collection', String(id));
		} catch (cause) { message(cause); }
	}

	async function createCollection() {
		if (!newName.trim()) return;
		try {
			loading = true;
			error = '';
			const created = await playerApi.create(newName.trim());
			newName = '';
			replaceCollection(created, true);
			localStorage.setItem('personal-player-collection', String(created.id));
			await refreshSummaries();
			await tick();
			if (!youtubePlayer) await initializePlayer();
		} catch (cause) { message(cause); } finally { loading = false; }
	}

	async function updateSettings(data: Parameters<typeof playerApi.update>[1]) {
		if (!collection) return;
		try {
			error = '';
			replaceCollection(await playerApi.update(collection.id, data));
			if (data.playback_rate !== undefined) applyRate();
			await refreshSummaries();
		} catch (cause) { message(cause); }
	}

	async function renameCollection() {
		if (!collection) return;
		const name = prompt('새 목록 이름', collection.name)?.trim();
		if (name && name !== collection.name) await updateSettings({ name });
	}

	async function importSource(url = sourceUrl) {
		if (!collection || !url.trim()) return;
		try {
			importing = true;
			error = '';
			notice = '';
			replaceCollection(await playerApi.importSource(collection.id, url.trim(), selectedAccount ?? undefined));
			sourceUrl = '';
			notice = '재생목록을 합쳤습니다.';
			await refreshSummaries();
		} catch (cause) { message(cause); } finally { importing = false; }
	}

	async function addTrack() {
		if (!collection || !videoUrl.trim()) return;
		try {
			importing = true;
			error = '';
			replaceCollection(await playerApi.addTrack(collection.id, videoUrl.trim(), selectedAccount ?? undefined));
			videoUrl = '';
			await refreshSummaries();
		} catch (cause) { message(cause); } finally { importing = false; }
	}

	async function removeSource(sourceId: number, ask = true) {
		if (!collection || (ask && !confirm('이 원본에서 가져온 곡을 모두 지울까요?'))) return;
		try {
			importing = true;
			error = '';
			await playerApi.removeSource(collection.id, sourceId);
			replaceCollection(await playerApi.collection(collection.id));
			await refreshSummaries();
			notice = '재생목록을 뺐습니다.';
		} catch (cause) { message(cause); } finally { importing = false; }
	}

	async function updateTrack(trackId: number, data: { weight?: number; enabled?: boolean }) {
		if (!collection) return;
		try { replaceCollection(await playerApi.updateTrack(collection.id, trackId, data)); }
		catch (cause) { message(cause); }
	}

	async function changeWeight(track: PlayerTrack, input: HTMLInputElement) {
		const weight = Number(input.value);
		if (!Number.isFinite(weight) || weight < 0.1 || weight > 10) {
			error = '빈도는 0.1부터 10까지 입력해 주세요.';
			input.value = String(track.weight);
			return;
		}
		await updateTrack(track.id, { weight });
		input.value = String(collection?.tracks.find((item) => item.id === track.id)?.weight ?? track.weight);
	}

	async function removeTrack(trackId: number) {
		if (!collection) return;
		try {
			replaceCollection(await playerApi.removeTrack(collection.id, trackId).then(() => playerApi.collection(collection!.id)));
			await refreshSummaries();
		} catch (cause) { message(cause); }
	}

	async function moveTrack(index: number, direction: -1 | 1) {
		if (!collection) return;
		const ids = collection.tracks.map((track) => track.id);
		const target = index + direction;
		if (target < 0 || target >= ids.length) return;
		[ids[index], ids[target]] = [ids[target], ids[index]];
		try { replaceCollection(await playerApi.reorder(collection.id, ids)); }
		catch (cause) { message(cause); }
	}

	async function removeCollection() {
		if (!collection || !confirm(`“${collection.name}” 목록을 지울까요?`)) return;
		try {
			await playerApi.remove(collection.id);
			youtubePlayer?.pauseVideo();
			collection = null;
			current = null;
			queue = null;
			localStorage.removeItem('personal-player-collection');
			await refreshSummaries();
			if (summaries[0]) await loadCollection(summaries[0].id);
		} catch (cause) { message(cause); }
	}

	async function loadAccounts() {
		try {
			accounts = await playerApi.accounts();
			if (accounts.length && !accounts.some((account) => account.id === selectedAccount)) selectedAccount = accounts[0].id;
			if (selectedAccount) await loadGooglePlaylists(selectedAccount);
		} catch (cause) { message(cause); }
	}

	async function loadGooglePlaylists(accountId: number) {
		try {
			accountLoading = true;
			googlePlaylists = [];
			googlePlaylists = await playerApi.googlePlaylists(accountId);
		} catch (cause) { message(cause); } finally { accountLoading = false; }
	}

	async function disconnectAccount(accountId: number) {
		if (!confirm('이 Google 연결을 해제할까요? 저장한 재생목록은 유지됩니다.')) return;
		try {
			await playerApi.disconnect(accountId);
			selectedAccount = null;
			googlePlaylists = [];
			await loadAccounts();
		} catch (cause) { message(cause); }
	}

	function applyRate() {
		if (!youtubePlayer || !collection) return;
		appliedRate = youtubePlayer.getPlaybackRate();
		const available = youtubePlayer.getAvailablePlaybackRates();
		availableRates = available;
		const wanted = collection.playback_rate;
		youtubePlayer.setPlaybackRate(wanted);
		if (available.length && !available.includes(wanted)) {
			const supported = available.filter((value) => value <= wanted).at(-1) ?? 1;
			notice = `이 영상은 ${wanted}배속을 지원하지 않습니다. 유튜브에서 지원하는 속도는 최대 ${Math.max(...available)}배속이며, ${supported}배속으로 재생을 요청했습니다.`;
		}
	}

	function selectTrack(track: PlayerTrack) {
		if (!track.enabled || !playerReady || !youtubePlayer) return;
		failedTrackIds.clear();
		current = track;
		error = '';
		youtubePlayer.loadVideoById(track.video_id);
		playing = true;
	}

	function nextTrack(recoverFromError = false) {
		if (!queue || !collection) return;
		let next = queue.next(current);
		if (failedTrackIds.size && (recoverFromError || next)) {
			const playable = collection.tracks.filter((track) => track.enabled && !failedTrackIds.has(track.id));
			if (!next || failedTrackIds.has(next.id)) next = playable.find((track) => track.id !== current?.id) ?? playable[0] ?? null;
		}
		if (!next) {
			playing = false;
			youtubePlayer?.pauseVideo();
			notice = failedTrackIds.size ? '재생 가능한 다른 곡이 없습니다.' : '목록 재생을 마쳤습니다.';
			return;
		}
		current = next;
		error = '';
		youtubePlayer?.loadVideoById(next.video_id);
		playing = true;
	}

	function togglePlayback() {
		if (!playerReady || !collection || !enabledCount) return;
		if (!current) { nextTrack(); return; }
		if (playing) youtubePlayer?.pauseVideo(); else youtubePlayer?.playVideo();
		playing = !playing;
	}

	async function initializePlayer() {
		if (youtubePlayer || !youtubeHost) return;
		const ytWindow = window as YouTubeWindow;
		if (!ytWindow.YT?.Player) {
			await new Promise<void>((resolve, reject) => {
				const timeout = window.setTimeout(() => reject(new Error('유튜브 플레이어를 불러오지 못했습니다. 네트워크 연결을 확인해주세요.')), 12000);
				const prior = ytWindow.onYouTubeIframeAPIReady;
				ytWindow.onYouTubeIframeAPIReady = () => { window.clearTimeout(timeout); prior?.(); resolve(); };
				if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
					const script = document.createElement('script');
					script.src = 'https://www.youtube.com/iframe_api';
					script.onerror = () => { window.clearTimeout(timeout); reject(new Error('유튜브 플레이어 스크립트를 불러오지 못했습니다.')); };
					document.head.appendChild(script);
				}
			});
		}
		if (!ytWindow.YT) return;
		youtubePlayer = new ytWindow.YT.Player(youtubeHost, {
			width: '100%', height: '100%',
			playerVars: { playsinline: 1, origin: window.location.origin },
			events: {
				onReady: () => { playerReady = true; },
			onStateChange: (event: { data: number }) => {
					if (event.data === 0) nextTrack();
					if (event.data === 1) { playing = true; applyRate(); }
					if (event.data === 2) playing = false;
				},
				onPlaybackRateChange: (event: { data: number }) => { appliedRate = event.data; },
				onError: () => { if (current) failedTrackIds.add(current.id); notice = '이 영상은 재생할 수 없어 다음 곡으로 넘어갑니다.'; nextTrack(true); }
			}
		});
	}

	onMount(() => {
		let disposed = false;
		(async () => {
			try {
				loading = true;
				await Promise.all([refreshSummaries(), loadAccounts()]);
				if (disposed) return;
				const stored = Number(localStorage.getItem('personal-player-collection'));
				const first = summaries.find((item) => item.id === stored) ?? summaries[0];
				if (first) await loadCollection(first.id);
				await tick();
				await initializePlayer();
				const params = new URLSearchParams(location.search);
				if (params.get('google_player') === 'connected') notice = 'Google 재생목록을 연결했습니다.';
				const googleError = params.get('google_error');
				if (googleError === 'refresh_missing') {
					needsConsentRetry = true;
					error = 'Google이 장기 연결 토큰을 보내지 않았습니다. 아래의 다시 연결 버튼으로 한 번 더 동의해주세요.';
				} else if (googleError === 'player_permission') {
					error = 'YouTube 계정 보기 권한을 허용하지 않아 목록을 가져올 수 없습니다.';
				} else if (googleError && googleError !== 'cancelled') {
					error = 'Google 연결을 완료하지 못했습니다. 다시 시도해주세요.';
				}
			} catch (cause) { message(cause); } finally { loading = false; }
		})();
		return () => { disposed = true; youtubePlayer?.destroy(); youtubePlayer = null; };
	});
</script>

<svelte:head>
	<title>온전히 · 집중 음악</title>
	<meta name="description" content="내가 고른 유튜브 재생목록만 모아 듣는 집중 음악 플레이어" />
</svelte:head>

<div class="player-shell">
	<aside class="player-sidebar">
		<a class="player-brand" href="/personal-project/player"><span class="brand-icon">◉</span><span><b>온전히</b><small>집중 음악 플레이어</small></span></a>
		<div class="side-heading">내 목록 <span>{summaries.length}</span></div>
		<nav class="collection-nav" aria-label="내 재생목록">
			{#each summaries as item (item.id)}
				<button class:active={collection?.id === item.id} onclick={() => loadCollection(item.id)}><span>{item.name}</span><small>{item.track_count}곡</small></button>
			{/each}
		</nav>
		<form class="new-list" onsubmit={(event) => { event.preventDefault(); createCollection(); }}>
			<input aria-label="새 목록 이름" placeholder="새 목록 이름" bind:value={newName} maxlength="100" />
			<button disabled={loading || !newName.trim()} aria-label="목록 만들기">＋</button>
		</form>
		<div class="side-bottom"><ServiceSwitcher active="player" /><PersonalAccountCard /></div>
	</aside>

	<main class="player-main">
		<header class="topbar"><div><span class="eyebrow">YOUR LISTENING SPACE</span><h1>{collection?.name ?? '나만의 음악 공간'}{#if collection}<button class="rename-button" onclick={renameCollection} aria-label="목록 이름 변경" title="목록 이름 변경">✎</button>{/if}</h1><p>듣기로 정한 곡만, 원하는 빈도로.</p></div><span class="topbar-badge">YouTube 공식 플레이어</span></header>
		{#if error}<div class="message error" role="alert">{error}<button aria-label="오류 닫기" onclick={() => (error = '')}>×</button></div>{/if}
		{#if notice}<div class="message notice" role="status">{notice}<button aria-label="알림 닫기" onclick={() => (notice = '')}>×</button></div>{/if}
		{#if !collection}
			<section class="empty-state"><div class="empty-symbol">♫</div><h2>첫 목록을 만들어 보세요</h2><p>왼쪽에서 이름을 입력하고 유튜브 재생목록 링크를 추가하면 됩니다.</p></section>
		{:else}
			<div class="workspace-grid">
				<div class="primary-column">
					<section class="now-playing panel">
						<div class="section-title"><div><span class="eyebrow">NOW PLAYING</span><h2>{current?.title ?? '재생할 곡을 선택하세요'}</h2><p>{current?.channel_title ?? '목록에서 한 곡을 누르거나 재생 버튼을 누르세요.'}</p></div><span class="playing-dot" class:on={playing}></span></div>
						<div class="video-frame"><div bind:this={youtubeHost}></div></div>
						<div class="transport"><button class="play-button" onclick={togglePlayback} disabled={!enabledCount || !playerReady}>{playing ? '일시정지' : '재생'}</button><button class="next-button" onclick={() => nextTrack()} disabled={!enabledCount || !playerReady}>다음 곡 →</button><span>실제 {appliedRate}배속 · {enabledCount}곡 사용 중</span></div>
					</section>
					<section class="panel editor-panel">
						<div class="section-title"><div><span class="eyebrow">PLAY QUEUE</span><h2>곡 목록</h2></div><span class="count">{collection.tracks.length}곡</span></div>
						{#if !collection.tracks.length}<p class="subtle">재생목록 링크나 영상 링크를 추가해주세요.</p>{/if}
						<div class="track-list">
							{#each collection.tracks as track, index (track.id)}
								<div class="track-row" class:selected={current?.id === track.id} class:disabled={!track.enabled}>
									<button class="track-play" aria-label={`${track.title} 재생`} onclick={() => selectTrack(track)} disabled={!track.enabled || !playerReady}>{current?.id === track.id && playing ? '♫' : '▶'}</button>
									{#if track.thumbnail_url}<img src={track.thumbnail_url} alt="" loading="lazy" />{:else}<span class="no-thumb">♫</span>{/if}
									<div class="track-meta"><strong>{track.title}</strong><small>{track.channel_title}</small></div>
									<label class="weight-field">빈도<input type="number" aria-label={`${track.title} 등장 빈도`} min="0.1" max="10" step="any" value={track.weight} onchange={(event) => changeWeight(track, event.currentTarget)} /></label>
									<div class="row-actions"><button title="위로" aria-label={`${track.title} 위로`} disabled={index === 0} onclick={() => moveTrack(index, -1)}>↑</button><button title="아래로" aria-label={`${track.title} 아래로`} disabled={index === collection!.tracks.length - 1} onclick={() => moveTrack(index, 1)}>↓</button><button title={track.enabled ? '재생에서 제외' : '재생에 포함'} aria-label={`${track.title} ${track.enabled ? '제외' : '포함'}`} onclick={() => updateTrack(track.id, { enabled: !track.enabled })}>{track.enabled ? '◉' : '○'}</button><button class="delete" title="곡 삭제" aria-label={`${track.title} 삭제`} onclick={() => removeTrack(track.id)}>×</button></div>
								</div>
							{/each}
						</div>
					</section>
				</div>
				<div class="settings-column">
					<section class="panel"><span class="eyebrow">PLAYBACK</span><h2>재생 설정</h2><label class="field">재생 방식<select value={collection.mode} onchange={(event) => updateSettings({ mode: event.currentTarget.value as PlayerCollection['mode'] })}><option value="ordered">목록 순서대로</option><option value="weighted">빈도에 따라 섞기</option></select></label><label class="field">반복<select value={collection.repeat_mode} onchange={(event) => updateSettings({ repeat_mode: event.currentTarget.value as PlayerCollection['repeat_mode'] })}><option value="all">전체 반복</option><option value="one">한 곡 반복</option><option value="off">반복 안 함</option></select></label><label class="field">요청 재생 속도<select value={String(collection.playback_rate)} onchange={(event) => updateSettings({ playback_rate: Number(event.currentTarget.value) })}><option value="1">1배속</option><option value="1.25">1.25배속</option><option value="1.5">1.5배속</option><option value="1.75">1.75배속</option><option value="2">2배속</option><option value="3">3배속 시도</option><option value="4">4배속 시도</option><option value="8">8배속 시도</option></select></label><label class="check-field"><input type="checkbox" checked={!!collection.avoid_repeat} onchange={(event) => updateSettings({ avoid_repeat: event.currentTarget.checked ? 1 : 0 })} />연속으로 같은 곡 피하기</label><p class="hint">빈도는 0.1~10 사이의 상대값입니다. 값이 클수록 더 자주 선택됩니다. {availableRates.length ? `현재 영상 지원 속도: ${availableRates.join('·')}배속` : '영상을 재생하면 지원 속도를 확인합니다.'} 광고 재생은 유튜브 플레이어가 관리합니다.</p></section>
					<section class="panel"><span class="eyebrow">BUILD YOUR MIX</span><h2>목록 합치기</h2><form onsubmit={(event) => { event.preventDefault(); importSource(); }}><label class="field">유튜브 재생목록 링크<input type="url" placeholder="https://www.youtube.com/playlist?list=…" bind:value={sourceUrl} /></label><button class="wide-button" disabled={importing || !sourceUrl.trim()}>{importing ? '가져오는 중…' : '재생목록 추가'}</button></form><form onsubmit={(event) => { event.preventDefault(); addTrack(); }}><label class="field">영상 한 곡 추가<input type="url" placeholder="https://www.youtube.com/watch?v=…" bind:value={videoUrl} /></label><button class="outline-button" disabled={importing || !videoUrl.trim()}>영상 추가</button></form>{#if collection.sources.length}<div class="source-list"><h3>합친 원본 목록</h3>{#each collection.sources as source (source.id)}<div><span title={source.title}>{source.title}</span><button aria-label={`${source.title} 원본과 곡 삭제`} title="원본과 곡 삭제" onclick={() => removeSource(source.id)}>×</button></div>{/each}</div>{/if}</section>
					<section class="panel">
						<span class="eyebrow">GOOGLE ACCOUNT</span><h2>내 유튜브 목록</h2>
						<p class="hint">내 목록을 가져오려면 Google의 ‘YouTube 계정 보기’ 권한이 필요합니다. 이 서비스는 재생목록 조회와 가져오기에 사용합니다. Google의 미인증 앱 경고가 나타날 수 있습니다. 아래 목록은 내 YouTube 목록이며 공식 추천이 아닙니다.</p>
						<a class="outline-button link-button" href={googleConnectUrl()}>Google 계정 연결</a>
						{#if needsConsentRetry}<a class="text-button" href={googleConnectUrl(true)}>다시 동의하고 연결</a>{/if}
						{#if accounts.length}
							<label class="field">연결된 계정<select value={String(selectedAccount ?? '')} onchange={(event) => { selectedAccount = Number(event.currentTarget.value); loadGooglePlaylists(selectedAccount); }}>{#each accounts as account}<option value={account.id}>{account.email}</option>{/each}</select></label>
							<button class="text-button" onclick={() => selectedAccount && disconnectAccount(selectedAccount)}>연결 해제</button>
						{/if}
						{#if accountLoading}
							<p class="subtle">목록을 불러오는 중…</p>
						{:else if visiblePlaylists.length}
							<h3 class="suggestion-title">내 목록에서 골라보기</h3>
							<div class="suggestions">
								{#each visiblePlaylists as item}
									{@const imported = collection.sources.find((source) => source.playlist_id === item.id)}
									<div class="suggestion-row" class:included={!!imported}>
										<div><strong>{item.title}</strong><small>{item.count}곡 · {imported ? '현재 목록에 추가됨' : '현재 목록에 추가하기'}</small></div>
										<button type="button" class:remove={!!imported} aria-label={`${item.title} ${imported ? '현재 목록에서 빼기' : '현재 목록에 추가하기'}`} onclick={() => imported ? removeSource(imported.id, false) : importSource(`https://www.youtube.com/playlist?list=${item.id}`)} disabled={importing}>{imported ? '빼기' : '추가'}</button>
									</div>
								{/each}
							</div>
						{:else if selectedAccount}
							<p class="subtle">이 계정에 재생목록이 없습니다. 다른 계정을 선택하거나 목록 링크를 입력해 주세요.</p>
						{/if}
					</section>
					<section class="panel danger-panel"><span class="eyebrow">MANAGE</span><h2>목록 관리</h2><button class="delete-list" onclick={removeCollection}>이 목록 삭제</button></section>
				</div>
			</div>
		{/if}
	</main>
</div>

<style>
	:global(body) { margin: 0; background: #f5f5f2; color: #212724; font-family: 'Noto Sans KR', system-ui, sans-serif; }
	:global(button), :global(input), :global(select) { font: inherit; }
	.player-shell { min-height: 100vh; display: grid; grid-template-columns: 238px minmax(0, 1fr); }
	.player-sidebar { position: sticky; top: 0; height: 100vh; box-sizing: border-box; display: flex; flex-direction: column; padding: 30px 16px 18px; background: #e9ece7; border-right: 1px solid #dbe0d9; }
	.player-brand { display: flex; gap: 12px; align-items: center; padding: 4px 10px 38px; text-decoration: none; color: #1d2a23; }
	.player-brand b { display: block; font-size: 22px; letter-spacing: -.05em; }
	.player-brand small { display: block; margin-top: 2px; color: #6e7a70; font-size: 11px; }
	.brand-icon { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 12px; background: #263e31; color: #e4efd9; font-size: 19px; }
	.side-heading { display: flex; justify-content: space-between; padding: 0 11px 9px; color: #536158; font-size: 12px; font-weight: 700; }
	.side-heading span { color: #8b978e; }
	.collection-nav { display: grid; gap: 4px; overflow-y: auto; }
	.collection-nav button { border: 0; border-radius: 10px; background: transparent; padding: 10px 11px; color: #4c5950; display: flex; align-items: center; justify-content: space-between; gap: 10px; text-align: left; cursor: pointer; }
	.collection-nav button.active { background: #fff; color: #203c2b; box-shadow: 0 1px 4px #203c2b10; font-weight: 700; }
	.collection-nav button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.collection-nav small { flex: none; font-size: 11px; color: #7d8a7f; }
	.new-list { display: flex; margin: 14px 2px 0; background: #fff; border-radius: 9px; overflow: hidden; border: 1px solid #d9e1d9; }
	.new-list input { width: 100%; min-width: 0; padding: 10px 11px; border: 0; outline: none; font-size: 12px; }
	.new-list button { border: 0; background: transparent; padding: 0 12px; color: #305f3a; cursor: pointer; font-size: 22px; }
	.side-bottom { margin-top: auto; }
	.player-main { min-width: 0; padding: 36px clamp(20px, 4vw, 58px) 70px; }
	.topbar { display: flex; justify-content: space-between; gap: 20px; align-items: start; margin-bottom: 24px; }
	.eyebrow { display: block; font-size: 10px; font-weight: 800; letter-spacing: .15em; color: #68816e; }
	h1 { font-size: clamp(27px, 3vw, 37px); letter-spacing: -.055em; line-height: 1.2; margin: 9px 0 7px; }
	.topbar p { color: #6a776d; margin: 0; font-size: 13px; }
	.rename-button { vertical-align: middle; margin-left: 9px; border: 0; background: none; color: #899b8b; cursor: pointer; font-size: 18px; }
	.topbar-badge { padding: 8px 11px; border: 1px solid #dfe6de; border-radius: 999px; white-space: nowrap; color: #607567; font-size: 11px; background: #fff; }
	.workspace-grid { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(280px, .85fr); gap: 18px; align-items: start; }
	.primary-column, .settings-column { display: grid; gap: 18px; min-width: 0; }
	.panel { background: #fff; border: 1px solid #e5e9e3; border-radius: 16px; padding: 21px; box-shadow: 0 2px 14px #203c2b07; min-width: 0; }
	.section-title { display: flex; justify-content: space-between; gap: 15px; align-items: start; margin-bottom: 16px; }
	h2 { margin: 7px 0 0; font-size: 18px; letter-spacing: -.035em; }
	.section-title h2 { margin: 5px 0 2px; overflow-wrap: anywhere; }
	.section-title p { color: #738077; font-size: 12px; margin: 4px 0 0; }
	.playing-dot { width: 9px; height: 9px; border-radius: 50%; background: #cdd5cd; margin-top: 11px; flex: none; }
	.playing-dot.on { background: #5a9e68; box-shadow: 0 0 0 5px #e1f1e2; }
	.video-frame { width: 100%; aspect-ratio: 16 / 9; border-radius: 11px; overflow: hidden; background: #1b221d; }
	.video-frame > div { width: 100%; height: 100%; }
	.transport { display: flex; gap: 9px; align-items: center; padding-top: 15px; }
	.transport button, .wide-button, .outline-button { border-radius: 8px; border: 1px solid #284d33; padding: 9px 15px; cursor: pointer; font-size: 12px; font-weight: 700; }
	.play-button, .wide-button { background: #284d33; color: #fff; }
	.next-button, .outline-button { background: #fff; color: #284d33; }
	.transport span { margin-left: auto; color: #7b887d; font-size: 11px; }
	button:disabled { cursor: not-allowed !important; opacity: .48; }
	.count { color: #8a958a; font-size: 12px; }
	.track-list { display: grid; }
	.track-row { display: flex; align-items: center; gap: 10px; min-width: 0; padding: 9px 0; border-top: 1px solid #eef0ed; }
	.track-row.selected { background: #f5f9f4; }
	.track-row.disabled { opacity: .55; }
	.track-row img, .no-thumb { width: 53px; height: 32px; object-fit: cover; border-radius: 5px; background: #e7eee6; flex: none; }
	.no-thumb { display: grid; place-items: center; }
	.track-play { width: 27px; flex: none; background: none; border: 0; color: #34553b; cursor: pointer; }
	.track-meta { min-width: 0; flex: 1; }
	.track-meta strong, .track-meta small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.track-meta strong { font-size: 12px; }
	.track-meta small { color: #849087; font-size: 10px; margin-top: 2px; }
	.weight-field { display: grid; gap: 2px; color: #829084; font-size: 9px; flex: none; }
	.weight-field input { width: 58px; box-sizing: border-box; padding: 4px 5px; border: 1px solid #e0e6de; border-radius: 4px; font-size: 11px; color: #405346; background: white; }
	.row-actions { display: flex; flex: none; }
	.row-actions button { border: 0; background: none; color: #708073; cursor: pointer; padding: 4px; font-size: 14px; }
	.row-actions .delete { color: #ad7369; font-size: 18px; }
	.field { display: grid; gap: 6px; margin-top: 16px; font-size: 11px; font-weight: 700; color: #59695d; }
	.field input, .field select { width: 100%; box-sizing: border-box; border: 1px solid #dfe6dd; border-radius: 8px; background: #fff; padding: 9px 10px; color: #28392d; font-size: 12px; }
	.check-field { display: flex; align-items: center; gap: 8px; margin-top: 17px; font-size: 12px; color: #52665a; }
	.check-field input { accent-color: #315f3d; }
	.hint, .subtle { color: #7b897d; font-size: 11px; line-height: 1.6; margin: 14px 0 0; }
	.wide-button, .outline-button { width: 100%; margin-top: 11px; display: block; text-align: center; box-sizing: border-box; text-decoration: none; }
	.source-list { margin-top: 19px; border-top: 1px solid #edf0ec; padding-top: 12px; }
	h3 { font-size: 11px; color: #657569; margin: 0 0 8px; }
	.source-list > div { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 11px; padding: 6px 0; }
	.source-list span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.source-list button { border: 0; background: none; color: #ad7369; font-size: 17px; cursor: pointer; }
	.link-button { font-size: 12px; }
	.text-button { margin-top: 8px; border: 0; background: none; color: #8b665f; font-size: 11px; cursor: pointer; padding: 4px 0; }
	.suggestion-title { margin-top: 18px; }
	.suggestions { display: grid; gap: 6px; max-height: 310px; overflow-y: auto; }
	.suggestion-row { display: flex; align-items: center; gap: 8px; min-width: 0; border: 1px solid #e6ece4; background: #f8faf7; border-radius: 8px; padding: 8px; }
	.suggestion-row.included { background: #edf5ec; border-color: #cbdcc9; }
	.suggestion-row > div { min-width: 0; flex: 1; }
	.suggestion-row button { flex: none; border: 1px solid #315f3d; color: #315f3d; background: #fff; border-radius: 6px; padding: 5px 8px; cursor: pointer; font-size: 11px; font-weight: 700; }
	.suggestion-row button.remove { border-color: #cfa7a0; color: #9d6158; }
	.suggestions strong, .suggestions small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.suggestions strong { font-size: 11px; }.suggestions small { margin-top: 2px; font-size: 10px; color: #819083; }
	.danger-panel { padding-top: 17px; padding-bottom: 17px; }
	.delete-list { background: none; border: 0; color: #ac6c61; font-size: 12px; cursor: pointer; padding: 14px 0 0; }
	.message { display: flex; justify-content: space-between; gap: 12px; padding: 12px 15px; margin-bottom: 18px; border-radius: 8px; font-size: 12px; }
	.message button { border: 0; background: none; cursor: pointer; font-size: 18px; }
	.error { background: #faebe7; color: #a45345; }.notice { background: #eaf2e9; color: #366044; }
	.empty-state { min-height: 330px; display: grid; align-content: center; justify-items: center; background: #fff; border: 1px solid #e5e9e3; border-radius: 16px; text-align: center; }
	.empty-symbol { font-size: 34px; color: #73977a; }.empty-state p { font-size: 13px; color: #7b897d; }
	@media (max-width: 1080px) { .workspace-grid { grid-template-columns: minmax(0, 1fr); }.settings-column { grid-template-columns: repeat(2, minmax(0, 1fr)); }.danger-panel { align-self: start; } }
	@media (max-width: 680px) { .player-shell { display: block; }.player-sidebar { position: static; height: auto; padding: 16px; }.player-brand { padding-bottom: 15px; }.collection-nav { display: flex; overflow-x: auto; }.collection-nav button { white-space: nowrap; }.new-list { max-width: 340px; }.side-bottom { display: none; }.player-main { padding: 23px 15px 50px; }.topbar-badge { display: none; }.settings-column { grid-template-columns: 1fr; }.panel { padding: 16px; }.row-actions button { padding: 2px; }.track-row { gap: 5px; }.track-row img, .no-thumb { width: 42px; height: 26px; }.track-meta strong { font-size: 11px; } }
</style>
