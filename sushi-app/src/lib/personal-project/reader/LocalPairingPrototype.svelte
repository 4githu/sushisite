<script lang="ts">
	import { createFakePairingTransport, type PairingTransport } from './pairing-prototype';

	let {
		transport = createFakePairingTransport()
	}: {
		transport?: PairingTransport;
	} = $props();
	let enabled = $state(false);
	let pending = $state(false);
	let message = $state<'success' | 'failure' | ''>('');

	async function runFakePairing() {
		if (!enabled || pending) return;
		pending = true;
		message = '';
		try {
			await transport.pair();
			message = 'success';
		} catch {
			message = 'failure';
		} finally {
			pending = false;
		}
	}
</script>

<section class="pairing-card" aria-labelledby="pairing-title">
	<div class="heading-row">
		<div>
			<p class="eyebrow">실험 기능 · EXPERIMENTAL</p>
			<h2 id="pairing-title">로컬 페어링 UI 미리보기</h2>
		</div>
		<span class="status-pill">실제 연결이 아닙니다</span>
	</div>
	<p class="description">
		이 화면은 결정적인 가상 전송만 사용합니다. 구독 제공자 연결이나 번역은 제공하지 않으며, 실제
		계정·인증 정보·문서 데이터를 보내지 않습니다. 실제 페어링 코드나 세션 토큰을 요청·저장하지
		않으며, 로컬 companion에도 접속하지 않습니다. 기본 상태에서는 꺼져 있습니다.
	</p>
	<p class="description english">
		This is an experimental UI prototype using a deterministic fake transport only. It does not
		connect to a subscription provider or translate content. No real account credentials or document
		data are sent; it requests/stores no real pairing code or session token and does not contact a
		local companion. The controls are off by default.
	</p>
	<label class="enable-row">
		<input type="checkbox" bind:checked={enabled} />
		<span>실험 UI 표시 · Show experimental controls</span>
	</label>
	<button class="pair-button" type="button" onclick={runFakePairing} disabled={!enabled || pending}>
		{pending ? '가상 응답 확인 중…' : '가상 페어링 확인'}
	</button>
	{#if message === 'success'}
		<p class="result success" role="status">
			가상 응답 확인 · 실제 연결 아님 · Fake response received; not a live connection.
		</p>
	{:else if message === 'failure'}
		<p class="result failure" role="alert">
			가상 요청 실패 · 민감 정보는 표시하지 않았습니다 · Fake request failed; details were
			sanitized.
		</p>
	{/if}
</section>

<style>
	.pairing-card {
		margin: 18px auto 0;
		padding: 18px 20px;
		max-width: 1000px;
		border: 1px dashed #cbd8cf;
		border-radius: 12px;
		background: #f8faf7;
		color: #35453b;
	}
	.heading-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.eyebrow {
		margin: 0 0 5px;
		color: #6b8273;
		font-size: 9px;
		font-weight: 750;
		letter-spacing: 0.12em;
	}
	h2 {
		margin: 0;
		font-family: Georgia, 'Noto Serif KR', serif;
		font-size: 18px;
		font-weight: 500;
	}
	.status-pill {
		flex: 0 0 auto;
		padding: 6px 9px;
		border-radius: 20px;
		background: #e9f0e9;
		color: #496c57;
		font-size: 10px;
		font-weight: 700;
	}
	.description {
		max-width: 780px;
		margin: 10px 0 0;
		color: #5d6d62;
		font-size: 11px;
		line-height: 1.65;
	}
	.english {
		margin-top: 4px;
		color: #7d8980;
	}
	.enable-row {
		margin-top: 13px;
		display: flex;
		align-items: flex-start;
		gap: 8px;
		color: #4a5e50;
		font-size: 11px;
		line-height: 1.5;
	}
	.enable-row input {
		margin: 2px 0 0;
		accent-color: #477764;
	}
	.pair-button {
		min-height: 36px;
		margin-top: 11px;
		padding: 0 13px;
		border: 0;
		border-radius: 7px;
		background: #315e52;
		color: white;
		font: inherit;
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
	}
	.pair-button:disabled {
		background: #aab9b0;
		cursor: not-allowed;
	}
	.result {
		margin: 11px 0 0;
		font-size: 11px;
		line-height: 1.6;
	}
	.success {
		color: #426b58;
	}
	.failure {
		color: #8b453c;
	}
	@media (max-width: 560px) {
		.pairing-card {
			margin-right: 14px;
			margin-left: 14px;
			padding: 15px;
		}
		.heading-row {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
