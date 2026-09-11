<script lang="ts">
	import Modal from './Modal.svelte';
	import Button from '$lib/odi/components/common/Button.svelte';
	import { odiuser } from '$lib/odi/stores';
	import {
		DEFAULT_REPORT_VIEW_VERSION,
		resolveReportViewVersion,
		resolveSTTProviderPreference,
		resolveTimelineVideoPreference,
		type AvailableReportViewVersion,
		type STTProviderPreference
	} from '$lib/odi/components/report/reportPreferences';

	const titleId = 'report-settings-modal-title';

	let { onClose }: { onClose?: () => void } = $props();

	let selectedVersion = $state<AvailableReportViewVersion>(DEFAULT_REPORT_VIEW_VERSION);
	let showTimelineVideo = $state(true);
	let sttProvider = $state<STTProviderPreference>('deepgram');
	let initialized = $state(false);
	let saving = $state(false);
	let message = $state('');
	let errorMessage = $state('');

	$effect(() => {
		if (initialized || !$odiuser) return;
		selectedVersion = resolveReportViewVersion($odiuser.config?.preferences?.report_view_version);
		showTimelineVideo = resolveTimelineVideoPreference(
			$odiuser.config?.preferences?.show_timeline_video
		);
		sttProvider = resolveSTTProviderPreference($odiuser.config?.preferences?.stt_provider);
		initialized = true;
	});

	async function save() {
		const user = odiuser.get();
		if (!user || saving) return;

		saving = true;
		message = '';
		errorMessage = '';

		try {
			await odiuser.updateConfig({
				...user.config,
				updated_at: new Date().toISOString(),
				preferences: {
					...(user.config.preferences ?? {}),
					report_view_version: selectedVersion,
					show_timeline_video: showTimelineVideo,
					stt_provider: sttProvider
				}
			});
			message = '계정 설정을 저장했습니다. 다음 XR 세션부터 적용됩니다.';
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '설정을 저장하지 못했습니다.';
		} finally {
			saving = false;
		}
	}
</script>

<Modal width="680px" minHeight="0px" labelledby={titleId} {onClose}>
	<div class="settings-modal">
		<header>
			<p>Settings</p>
			<h2 id={titleId}>Re:hear 계정 설정</h2>
			<span>리포트 표시 방식과 XR 세션 음성 인식 공급자를 선택하세요.</span>
		</header>

		<fieldset>
			<legend>리포트 버전</legend>
			<label class:selected={selectedVersion === 'v1'}>
				<input type="radio" name="report-version" value="v1" bind:group={selectedVersion} />
				<span><strong>버전 1 · 기본형</strong><small>기존 카드 중심의 리포트 배치</small></span>
			</label>
			<label class:selected={selectedVersion === 'v2'}>
				<input type="radio" name="report-version" value="v2" bind:group={selectedVersion} />
				<span
					><strong>버전 2 · 개선형</strong><small>결과와 행동을 순서대로 읽는 정보 위계</small
					></span
				>
			</label>
			<label class:selected={selectedVersion === 'v3'}>
				<input type="radio" name="report-version" value="v3" bind:group={selectedVersion} />
				<span
					><strong>버전 3 · 최종형</strong><small>최종 UX/UI 시안의 탭형 분석 리포트</small></span
				>
			</label>
		</fieldset>

		<label class="video-setting">
			<input type="checkbox" bind:checked={showTimelineVideo} />
			<span>
				<strong>타임라인 연동 영상 표시</strong>
				<small>영상이 연결된 리포트에서 문제 구간과 함께 재생 화면을 표시합니다.</small>
			</span>
		</label>

		<fieldset>
			<legend>XR 음성 인식</legend>
			<label class:selected={sttProvider === 'deepgram'}>
				<input type="radio" name="stt-provider" value="deepgram" bind:group={sttProvider} />
				<span><strong>Deepgram</strong><small>발표와 Q&A 답변을 Deepgram으로 인식합니다.</small></span>
			</label>
			<label class:selected={sttProvider === 'azure'}>
				<input type="radio" name="stt-provider" value="azure" bind:group={sttProvider} />
				<span><strong>Azure Speech</strong><small>발표와 Q&A 답변을 Azure Speech로 인식합니다.</small></span>
			</label>
			<p class="provider-note">서버에 선택한 공급자의 API 키가 없으면 XR 세션 시작이 차단되며 자동 전환되지 않습니다.</p>
		</fieldset>

		{#if message}<p class="message" role="status">{message}</p>{/if}
		{#if errorMessage}<p class="error-message" role="alert">{errorMessage}</p>{/if}

		<footer>
			<Button variant="secondary" width="140px" onclick={onClose}>취소</Button>
			<Button variant="primary" width="180px" disabled={saving} onclick={save}>
				{saving ? '저장 중' : '설정 저장'}
			</Button>
		</footer>
	</div>
</Modal>

<style>
	.settings-modal {
		width: 100%;
		padding: clamp(24px, 5vw, 42px);
		display: grid;
		gap: var(--space-6);
		background: var(--surface);
	}

	header {
		display: grid;
		gap: var(--space-2);
	}

	header p {
		color: var(--primary);
		font-size: 13px;
		font-weight: var(--font-bold);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	header h2 {
		color: var(--brand-black);
		font-size: 28px;
	}

	header span,
	label small {
		color: var(--text-secondary);
	}

	fieldset {
		min-width: 0;
		display: grid;
		gap: var(--space-3);
		border: 0;
	}

	legend {
		margin-bottom: var(--space-3);
		color: var(--brand-black);
		font-weight: var(--font-bold);
	}

	fieldset label,
	.video-setting {
		min-width: 0;
		padding: 16px;
		display: flex;
		align-items: center;
		gap: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		cursor: pointer;
	}

	fieldset label.selected {
		border-color: var(--primary);
		background: rgba(0, 51, 255, 0.04);
	}

	fieldset label span,
	.video-setting span {
		min-width: 0;
		display: grid;
		gap: 3px;
	}

	fieldset label strong,
	.video-setting strong {
		color: var(--brand-black);
	}

	.video-setting {
		background: var(--cool-grey-light);
	}

	.provider-note {
		color: var(--text-secondary);
		font-size: 13px;
		line-height: 1.5;
	}

	.message,
	.error-message {
		padding: 12px 14px;
		border-radius: var(--radius-sm);
	}

	.message {
		background: rgba(68, 198, 153, 0.15);
		color: #238b66;
	}

	.error-message {
		background: var(--accent-light);
		color: var(--accent);
	}

	footer {
		display: flex;
		justify-content: flex-end;
		gap: var(--space-3);
	}

	@media (max-width: 560px) {
		footer {
			flex-direction: column-reverse;
		}

		footer :global(.button) {
			width: 100% !important;
		}
	}
</style>
