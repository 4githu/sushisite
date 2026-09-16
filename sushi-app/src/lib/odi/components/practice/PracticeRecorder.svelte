<script lang="ts">
	import { onDestroy } from 'svelte';
	import { AudioRecorder } from '$lib/odi/domain/audioRecorder';
	import type { PracticeExercise, PracticeAttempt } from '$lib/odi/domain/practice';
	import { API_BASE } from '$lib/config/api';
	import Button from '../common/Button.svelte';
	let {
		exercise,
		attempt,
		oncreated,
		onclose
	}: {
		exercise: PracticeExercise;
		attempt: PracticeAttempt | null;
		oncreated: (id: string) => void;
		onclose: () => void;
	} = $props();
	let recorder: AudioRecorder | null = null,
		timer: ReturnType<typeof setInterval> | undefined,
		disposed = false;
	let recording = $state(false),
		preparing = $state(false),
		submitting = $state(false),
		elapsed = $state(0),
		level = $state(0),
		target = $state(60),
		blob = $state<Blob | null>(null),
		url = $state(''),
		error = $state(''),
		attemptId = $state('');
	const analyzing = $derived(
		attempt?.attempt_id === attemptId && ['queued', 'analyzing'].includes(attempt.state)
	);
	const ownAttempt = $derived(attempt?.attempt_id === attemptId ? attempt : null);
	async function begin() {
		if (preparing || recording) return;
		preparing = true;
		error = '';
		blob = null;
		if (url) URL.revokeObjectURL(url);
		url = '';
		attemptId = '';
		elapsed = 0;
		try {
			const next = await AudioRecorder.start(
				(v) => (level = v),
				() => {
					void stop();
				}
			);
			if (disposed) {
				await next.dispose();
				return;
			}
			recorder = next;
			recording = true;
			const start = Date.now();
			timer = setInterval(() => {
				elapsed = (Date.now() - start) / 1000;
				if (elapsed >= 180) void stop();
			}, 200);
		} catch (e) {
			error =
				e instanceof DOMException && e.name === 'NotAllowedError'
					? '마이크 권한이 필요해요. 브라우저 설정을 확인해 주세요.'
					: e instanceof Error
						? e.message
						: '마이크를 시작하지 못했어요.';
		} finally {
			preparing = false;
		}
	}
	async function stop() {
		if (!recorder || !recording) return;
		recording = false;
		preparing = true;
		clearInterval(timer);
		const active = recorder;
		recorder = null;
		try {
			blob = await active.finish();
			url = URL.createObjectURL(blob);
			attemptId = crypto.randomUUID();
		} catch (e) {
			error = e instanceof Error ? e.message : '녹음 실패';
		} finally {
			preparing = false;
		}
	}
	async function analyze() {
		if (!blob || submitting) return;
		submitting = true;
		error = '';
		try {
			const form = new FormData();
			form.append('audio', blob, 'practice.wav');
			form.append('attempt_id', attemptId);
			form.append('metric_id', exercise.id);
			form.append('target_seconds', String(target));
			const res = await fetch(`${API_BASE}/odi/coaching/practice/attempts`, {
				method: 'POST',
				credentials: 'include',
				body: form
			});
			const data = await res.json();
			if (!res.ok)
				throw new Error(
					typeof data.detail === 'string' ? data.detail : '분석 요청에 실패했습니다.'
				);
			oncreated(data.attempt_id);
		} catch (e) {
			error = e instanceof Error ? e.message : '분석 실패';
		} finally {
			submitting = false;
		}
	}
	onDestroy(() => {
		disposed = true;
		clearInterval(timer);
		void recorder?.dispose();
		if (url) URL.revokeObjectURL(url);
	});
</script>

<section class="surface recorder">
	<div class="section-head">
		<div>
			<p class="eyebrow">FOCUS PRACTICE</p>
			<h2>{exercise.title}</h2>
		</div>
		<Button size="sm" variant="ghost" onclick={onclose} disabled={recording || preparing}
			>닫기</Button
		>
	</div>
	<p>{exercise.task}</p>
	<label
		>목표 시간 <select bind:value={target} disabled={recording || Boolean(blob)}
			><option value={30}>30초</option><option value={60}>60초</option><option value={120}
				>2분</option
			><option value={180}>3분</option></select
		></label
	>
	<div class="recording-stage" aria-live="polite">
		<div
			class="pulse"
			class:live={recording}
			style:transform={`scale(${1 + Math.min(0.5, level * 4)})`}
		>
			●
		</div>
		<strong>{Math.floor(elapsed / 60)}:{String(Math.floor(elapsed % 60)).padStart(2, '0')}</strong>
		<p>{recording ? '녹음 중 · 최대 3분' : '준비가 되면 녹음을 시작하세요'}</p>
		<progress value={Math.min(elapsed, target)} max={target} aria-label="목표 시간 대비 녹음 시간"
		></progress>
	</div>
	<div class="actions">
		{#if recording}<Button onclick={stop}>녹음 마치기</Button>{:else}<Button
				variant={blob ? 'outline' : 'primary'}
				onclick={begin}
				disabled={preparing || submitting || analyzing}
				>{preparing ? '마이크 준비 중…' : blob ? '다시 녹음' : '녹음 시작'}</Button
			>{/if}{#if blob}<Button
				onclick={analyze}
				disabled={submitting || analyzing || ownAttempt?.state === 'completed'}
				>{submitting || analyzing
					? '분석 중…'
					: ownAttempt?.state === 'failed'
						? '분석 다시 시도'
						: '이 녹음 분석하기'}</Button
			>{/if}
	</div>
	{#if url}<audio controls src={url}></audio>{/if}{#if error}<p class="error" role="alert">
			{error}
		</p>{/if}{#if ownAttempt?.state === 'failed'}<p class="error" role="alert">
			{ownAttempt.error}
		</p>{:else if ownAttempt?.state === 'completed'}<div class="result">
			<span class="chip">훈련 완료</span>
			<h2>{ownAttempt.score}점</h2>
			<p>{ownAttempt.feedback?.feedback}</p>
			<blockquote>{ownAttempt.feedback?.evidence}</blockquote>
			<details>
				<summary>내가 말한 내용</summary>
				<p>{ownAttempt.transcript}</p>
			</details>
			<p class="muted">
				{(ownAttempt.score ?? 0) >= 80
					? '80점 이상 달성! 레벨 진도에 반영했어요.'
					: '같은 목표로 다시 도전해 보세요.'}
			</p>
		</div>{/if}<small class="muted"
		>녹음 원본은 보관하지 않습니다. 전사와 분석 결과만 훈련 기록에 남아요.</small
	>
</section>

<style>
	.recorder {
		border-color: #b5baff !important;
		margin: 24px 0;
	}
	.recording-stage {
		text-align: center;
		padding: 30px;
	}
	.pulse {
		width: 66px;
		height: 66px;
		border-radius: 50%;
		display: grid;
		place-items: center;
		background: #ecefff;
		color: #8b97c9;
		font-size: 22px;
		margin: 0 auto 14px;
		transition: transform 0.2s;
	}
	.pulse.live {
		background: #ffe9ee;
		color: #dc4168;
	}
	.recording-stage strong {
		font-size: 38px;
		color: #050632;
	}
	.recording-stage p {
		font-size: 14px;
		color: #727c91;
	}
	progress {
		width: min(300px, 100%);
		height: 6px;
		accent-color: #03f;
	}
	.actions {
		justify-content: center;
	}
	audio {
		display: block;
		margin: 22px auto;
		width: min(450px, 100%);
	}
	small {
		display: block;
		margin-top: 24px;
	}
	.result {
		padding: 24px;
		background: #f4f6ff;
		border-radius: 12px;
		margin: 24px 0;
	}
	.result h2 {
		font-size: 36px;
		margin-top: 12px;
	}
	.result blockquote {
		padding-left: 18px;
		border-left: 3px solid #807dfe;
		color: #69728b;
	}
	label {
		font-size: 14px;
	}
</style>
