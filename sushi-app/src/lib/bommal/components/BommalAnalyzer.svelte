<script lang="ts">
	import { analyzeSentence, analyzeWord, checkPronunciationHealth } from '$lib/bommal/api/pronunciation';
	import type { ProductMode, VoiceEvaluationResponse, WordEvaluationResponse } from '$lib/bommal/types';
	import LpcChart from '$lib/bommal/components/LpcChart.svelte';
	import ScoreDial from '$lib/bommal/components/ScoreDial.svelte';

	let sentenceFile = $state<File | null>(null);
	let wordFile = $state<File | null>(null);
	let mode = $state<ProductMode>('education');
	let targetText = $state('안녕하세요, 고 발표를 시작하겠습니다.');
	let vowel = $state('아');
	let sentenceResult = $state<VoiceEvaluationResponse | null>(null);
	let wordResult = $state<WordEvaluationResponse | null>(null);
	let statusMessage = $state('백엔드 연결 대기');
	let loading = $state(false);
	let errorMessage = $state('');

	const backendState = $derived(errorMessage ? '확인 필요' : sentenceResult || wordResult ? '연결됨' : '대기');
	const mainScore = $derived(sentenceResult?.score.overallScore ?? wordResult?.score ?? null);

	function setSentenceFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		sentenceFile = input.files?.[0] ?? null;
	}

	function setWordFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		wordFile = input.files?.[0] ?? null;
	}

	async function pingBackend() {
		errorMessage = '';
		statusMessage = '서버 확인 중';
		try {
			const result = await checkPronunciationHealth();
			statusMessage = `${result.status} · api ${result.apiVersion}`;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '서버 상태 확인 실패';
			statusMessage = '연결 실패';
		}
	}

	async function submitSentence() {
		if (!sentenceFile) {
			errorMessage = '문장 분석용 음성 파일을 선택해주세요.';
			return;
		}

		loading = true;
		errorMessage = '';
		statusMessage = '문장 분석 중';
		try {
			sentenceResult = await analyzeSentence({
				audio: sentenceFile,
				mode,
				sessionId: `bommal-${Date.now()}`,
				attemptId: `attempt-${Date.now()}`,
				targetText: targetText.trim()
			});
			statusMessage = '문장 분석 완료';
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '문장 분석 실패';
			statusMessage = '문장 분석 실패';
		} finally {
			loading = false;
		}
	}

	async function submitWord() {
		if (!wordFile) {
			errorMessage = '글자 평가용 음성 파일을 선택해주세요.';
			return;
		}

		loading = true;
		errorMessage = '';
		statusMessage = 'LPC 평가 중';
		try {
			wordResult = await analyzeWord({ audio: wordFile, vowel: vowel.trim() });
			statusMessage = 'LPC 평가 완료';
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'LPC 평가 실패';
			statusMessage = 'LPC 평가 실패';
		} finally {
			loading = false;
		}
	}
</script>

<section class="analyzer" aria-label="봄말 음성 평가 데모">
	<div class="control-panel">
		<div class="panel-heading">
			<p>Live API Test</p>
			<h2>음성 파일을 넣고 바로 평가하기</h2>
		</div>

		<div class="status-strip">
			<span>{backendState}</span>
			<strong>{statusMessage}</strong>
			<button type="button" onclick={pingBackend}>서버 확인</button>
		</div>

		<div class="form-grid">
			<form onsubmit={(event) => { event.preventDefault(); submitSentence(); }}>
				<div class="form-title">
					<span>문장</span>
					<h3>STT 문장 분석</h3>
				</div>
				<label>
					목표 문장
					<textarea bind:value={targetText} rows="3"></textarea>
				</label>
				<label>
					모드
					<select bind:value={mode}>
						<option value="education">education</option>
						<option value="presentation">presentation</option>
					</select>
				</label>
				<label>
					음성 파일
					<input type="file" accept="audio/*" onchange={setSentenceFile} />
				</label>
				<button class="primary" type="submit" disabled={loading}>문장 분석 실행</button>
			</form>

			<form onsubmit={(event) => { event.preventDefault(); submitWord(); }}>
				<div class="form-title">
					<span>글자</span>
					<h3>LPC 발음 평가</h3>
				</div>
				<label>
					기준 이름
					<input bind:value={vowel} placeholder="아, 어, 오, 우" />
				</label>
				<label>
					음성 파일
					<input type="file" accept="audio/*" onchange={setWordFile} />
				</label>
				<div class="reference-note">
					<small>백엔드 `reference_lpc/{vowel}.json`과 비교합니다.</small>
				</div>
				<button class="primary dark" type="submit" disabled={loading}>LPC 평가 실행</button>
			</form>
		</div>
	</div>

	<div class="result-panel">
		<div class="result-summary">
			<ScoreDial score={mainScore} />
			<div>
				<p>Result Preview</p>
				<h2>{sentenceResult?.transcript ?? wordResult?.feedback ?? '분석 결과가 여기에 표시됩니다.'}</h2>
				{#if sentenceResult?.feedback.summary}
					<span>{sentenceResult.feedback.summary}</span>
				{:else if errorMessage}
					<span class="error">{errorMessage}</span>
				{:else}
					<span>문장 결과는 오류 위치와 조음 Tip을, 글자 결과는 LPC 곡선을 반환합니다.</span>
				{/if}
			</div>
		</div>

		{#if sentenceResult?.wordResults?.length}
			<div class="issue-list">
				{#each sentenceResult.wordResults as issue}
					<article>
						<strong>{issue.location?.displayLabel ?? `${issue.expected ?? ''} -> ${issue.recognized ?? ''}`}</strong>
						<p>{issue.observation?.message}</p>
						<small>{issue.practice?.tip}</small>
					</article>
				{/each}
			</div>
		{/if}

		<LpcChart user={wordResult?.graph.user ?? []} target={wordResult?.graph.target ?? []} />
	</div>
</section>

<style>
	.analyzer {
		display: grid;
		grid-template-columns: minmax(340px, 0.95fr) minmax(420px, 1.35fr);
		gap: 24px;
		align-items: start;
	}

	.control-panel,
	.result-panel {
		border-radius: 24px;
		background: rgba(255, 255, 255, 0.86);
		box-shadow: 0 24px 80px rgba(7, 1, 0, 0.1);
	}

	.control-panel {
		display: grid;
		gap: 20px;
		padding: 24px;
	}

	.result-panel {
		display: grid;
		gap: 20px;
		padding: 24px;
	}

	.panel-heading p,
	.result-summary p {
		margin: 0 0 6px;
		color: #59d26b;
		font-size: 13px;
		font-weight: 800;
	}

	.panel-heading h2,
	.result-summary h2 {
		margin: 0;
		color: #070100;
		font-size: 28px;
		font-weight: 800;
		letter-spacing: 0;
		line-height: 1.18;
	}

	.status-strip {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		border-radius: 18px;
		background: #f5ffd6;
		padding: 12px 14px;
	}

	.status-strip span {
		border-radius: 999px;
		background: #daff1c;
		padding: 7px 10px;
		color: #070100;
		font-size: 12px;
		font-weight: 800;
	}

	.status-strip strong {
		flex: 1;
		color: rgba(7, 1, 0, 0.68);
		font-size: 14px;
	}

	button {
		border: 0;
		border-radius: 999px;
		background: #070100;
		color: #fff;
		cursor: pointer;
		font: inherit;
		font-size: 14px;
		font-weight: 800;
		letter-spacing: 0;
		padding: 11px 16px;
	}

	button:disabled {
		cursor: progress;
		opacity: 0.5;
	}

	.form-grid {
		display: grid;
		gap: 16px;
	}

	form {
		display: grid;
		gap: 14px;
		border: 1px solid rgba(7, 1, 0, 0.08);
		border-radius: 20px;
		background: #fff;
		padding: 18px;
	}

	.form-title {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.form-title span {
		border-radius: 999px;
		background: #eefcef;
		color: #168f2d;
		font-size: 13px;
		font-weight: 800;
		padding: 7px 12px;
	}

	.form-title h3 {
		margin: 0;
		color: #070100;
		font-size: 18px;
		font-weight: 800;
	}

	label {
		display: grid;
		gap: 8px;
		color: rgba(7, 1, 0, 0.66);
		font-size: 13px;
		font-weight: 800;
	}

	input,
	select,
	textarea {
		width: 100%;
		border: 1px solid rgba(7, 1, 0, 0.12);
		border-radius: 14px;
		background: #fafafa;
		color: #070100;
		font: inherit;
		font-size: 15px;
		letter-spacing: 0;
		padding: 12px 13px;
	}

	textarea {
		resize: vertical;
	}

	.primary {
		background: linear-gradient(135deg, #daff1c, #ffffff);
		color: #070100;
	}

	.primary.dark {
		background: #070100;
		color: #daff1c;
	}

	.reference-note {
		min-height: 42px;
		border-radius: 14px;
		background: #f8faf4;
		color: rgba(7, 1, 0, 0.54);
		display: flex;
		align-items: center;
		padding: 0 12px;
	}

	.result-summary {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 22px;
		align-items: center;
	}

	.result-summary span {
		display: block;
		margin-top: 10px;
		color: rgba(7, 1, 0, 0.58);
		font-size: 15px;
		font-weight: 600;
		line-height: 1.55;
	}

	.result-summary .error {
		color: #ff3938;
	}

	.issue-list {
		display: grid;
		gap: 10px;
	}

	.issue-list article {
		border-radius: 16px;
		background: #ffebea;
		padding: 14px 16px;
	}

	.issue-list strong {
		color: #ff3938;
		font-size: 15px;
	}

	.issue-list p {
		margin: 8px 0 4px;
		color: #070100;
		font-size: 15px;
		font-weight: 700;
	}

	.issue-list small {
		color: rgba(7, 1, 0, 0.62);
		font-size: 13px;
		line-height: 1.45;
	}

	@media (max-width: 980px) {
		.analyzer {
			grid-template-columns: 1fr;
		}

		.result-summary {
			grid-template-columns: 1fr;
		}
	}
</style>
