<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AuraReportEditor from '$lib/personal-project/aura/components/AuraReportEditor.svelte';
	import { fromRich, toRich } from '$lib/personal-project/editor/document';
	import { progressStageLabels } from '$lib/personal-project/aura/stages';
	import { createDocument, normalizeDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import {
		request,
		personalApi,
		PersonalApiError,
		type ReportAttachment
	} from '$lib/personal-project/shared/api';
	import { deliveryView, type DeliveryResult } from '$lib/personal-project/aura/delivery-result';
	import { privateCacheUser } from '$lib/personal-project/shared/auth';
	import type {
		AiReportModel,
		AiReportResult,
		TargetReport
	} from '$lib/personal-project/shared/types';

	let report = $state<TargetReport | null>(null);
	let initialDocument = $state<EditorDocument>(createDocument());
	let draftDocument = $state<EditorDocument>(createDocument());
	let editor = $state<AuraReportEditor>();
	let sourceNotes = $state('');
	let questionChecks = $state<Record<string, boolean>>({});
	let saving = $state(false);
	let saveStatus = $state<'saved' | 'pending' | 'saving' | 'failed'>('saved');
	let switching = $state(false);
	let message = $state('');
	let error = $state('');
	let autosaveTimer: number | undefined;

	let aiModels = $state<AiReportModel[]>([]);
	let selectedModel = $state('');
	let aiResults = $state<AiReportResult[]>([]);
	let aiHistoryLoaded = $state(false);
	let generatingTargets = $state<Record<number, boolean>>({});
	let generationNotices = $state<Record<number, string>>({});
	let aiGenerating = $derived(Boolean(report && generatingTargets[report.targetId]));
	let scoreMode = $state<'auto' | 'none'>('auto');
	type HighlightMeaning = 'fixed' | 'unfixed' | 'not_reasked';
	let highlightSemantics = $state<{
		yellow: HighlightMeaning;
		orange: HighlightMeaning;
		peach: HighlightMeaning;
	}>({
		yellow: 'fixed',
		orange: 'unfixed',
		peach: 'not_reasked'
	});
	let includeQuestionChecks = $state(false);
	let generatedReport = $state<AiReportResult['output'] | null>(null);
	let selectedAiRunId = $state('');
	let aiModel = $state<string | null>(null);
	let modalStage = $state<'closed' | 'generate' | 'final'>('closed');

	let lectureProgress = $state(5);
	let lectureComprehension = $state(5);
	let memoryBefore = $state(4);
	let memoryAfter = $state(5);
	let assessmentCsv = $state('');
	let finalParagraphs = $state<string[]>([]);
	let problemSolvingNote = $state('');
	type AttachmentPreview = ReportAttachment & { url: string };
	let blankTestImages = $state<AttachmentPreview[]>([]);
	let problemImages = $state<AttachmentPreview[]>([]);
	let attachmentBusy = $state(false);
	let attachmentNotice = $state('');
	let pdfBusy = $state(false);
	let kakaoBusy = $state(false);
	let nativeKakaoBusy = $state(false);
	type ScheduledDelivery = {
		id: string;
		targetId: number;
		state:
			| 'queued'
			| 'generating'
			| 'ready'
			| 'sending'
			| 'sent'
			| 'failed'
			| 'unknown'
			| 'partial'
			| 'cancelled';
		requestedAt: number;
		sendAfter: number;
		errorCode: string | null;
	};
	let scheduledDelivery = $state<ScheduledDelivery | null>(null);
	let scheduleReady = $state(false);
	let scheduleBusy = $state(false);
	let scheduleNotice = $state('');
	let scheduleTimer: number | undefined;
	let scheduleReadVersion = 0;
	let scheduleOutcomeUncertain = $state(false);
	let immediateOutcomeUncertain = $state(false);
	let deliveryRecoveryVersion = 0;
	let deliveryNotice = $state('');
	let replacedScheduleNotice = $state('');
	const immediateOutcomeKey = (targetId: number) => `aura-clinic-send-uncertain:${targetId}`;
	function applyDeliveryResult(targetId: number, result: DeliveryResult) {
		if (loadingTargetId !== targetId || destroyed) return;
		const view = deliveryView(result);
		deliveryNotice = view.message;
		if (view.unlock) {
			try {
				localStorage.removeItem(immediateOutcomeKey(targetId));
				immediateOutcomeUncertain = false;
			} catch {
				immediateOutcomeUncertain = true;
			}
		}
		if (view.verified && result.completionStatus !== 'pending' && report?.targetId === targetId) {
			cancelAutosave();
			report = { ...report, status: 'submitted' };
		}
	}
	async function recoverDelivery(targetId: number, requestId: string, revision: number) {
		const recoveryVersion = deliveryRecoveryVersion;
		try {
			const result = await personalApi.clinicDeliveryResult(targetId, requestId);
			if (revision === loadRevision && recoveryVersion === deliveryRecoveryVersion) applyDeliveryResult(targetId, result);
		} catch {
			if (revision === loadRevision && recoveryVersion === deliveryRecoveryVersion && loadingTargetId === targetId)
				deliveryNotice = deliveryView({}).message;
		}
	}
	const scheduleLabels: Record<ScheduledDelivery['state'], string> = {
		queued: '예약 대기',
		generating: '리포트 생성 중',
		ready: '전송 준비 완료',
		sending: '전송 중',
		sent: '전송 완료',
		failed: '예약 실패',
		unknown: '전송 결과 확인 필요',
		partial: '일부 전송 · 확인 필요',
		cancelled: '예약 취소됨'
	};
	async function refreshSchedule(targetId: number, revision: number) {
		const readVersion = ++scheduleReadVersion;
		try {
			const result = await request<ScheduledDelivery | null>(
				`/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`
			);
			if (
				destroyed ||
				revision !== loadRevision ||
				loadingTargetId !== targetId ||
				readVersion !== scheduleReadVersion
			)
				return;
			if (
				scheduleOutcomeUncertain &&
				(!result ||
					((scheduledDelivery?.state === 'failed' || scheduledDelivery?.state === 'cancelled') &&
						result.id === scheduledDelivery.id))
			) {
				scheduleReady = false;
				scheduleNotice = '예약 결과가 아직 확인되지 않았습니다. 잠시 후 상태를 확인하세요.';
				return;
			}
			scheduleOutcomeUncertain = false;
			scheduledDelivery = result;
			scheduleReady = true;
			scheduleNotice = '';
		} catch {
			if (destroyed || revision !== loadRevision || loadingTargetId !== targetId) return;
			scheduleReady = false;
			scheduleNotice = '예약 상태를 확인하지 못했습니다. 연결을 확인한 뒤 다시 확인하세요.';
		}
	}
	async function scheduleDelivery() {
		if (
			!report ||
			scheduleBusy ||
			nativeKakaoBusy ||
			!scheduleReady ||
			(scheduledDelivery &&
				scheduledDelivery.state !== 'failed' &&
				scheduledDelivery.state !== 'cancelled')
		)
			return;
		const targetId = report.targetId;
		const revision = loadRevision;
		scheduleBusy = true;
		try {
			if (!(await save(false, true))) {
				scheduleNotice = '저장하지 못해 예약하지 않았습니다.';
				return;
			}
			if (destroyed || revision !== loadRevision || report?.targetId !== targetId) return;
			scheduleReady = false;
			++scheduleReadVersion;
			scheduleOutcomeUncertain = true;
			const result = await request<ScheduledDelivery>(
				`/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`,
				{ method: 'POST' }
			);
			if (destroyed || revision !== loadRevision) return;
			scheduleOutcomeUncertain = false;
			scheduledDelivery = result;
			scheduleReady = true;
			scheduleNotice = '';
		} catch {
			if (!destroyed && revision === loadRevision) {
				scheduleReady = false;
				scheduleNotice = '예약 결과를 확인하지 못했습니다. 상태를 다시 확인하세요.';
			}
		} finally {
			scheduleBusy = false;
		}
	}
	async function cancelScheduledDelivery() {
		if (
			!report ||
			scheduleBusy ||
			!scheduleReady ||
			!scheduledDelivery ||
			!['queued', 'generating', 'ready'].includes(scheduledDelivery.state)
		)
			return;
		const targetId = report.targetId,
			id = scheduledDelivery.id,
			revision = loadRevision;
		scheduleBusy = true;
		scheduleReady = false;
		++scheduleReadVersion;
		try {
			const result = await request<ScheduledDelivery>(
				`/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries/${id}`,
				{ method: 'DELETE' }
			);
			if (destroyed || revision !== loadRevision) return;
			scheduledDelivery = result;
			scheduleReady = true;
			scheduleNotice = '';
		} catch {
			if (!destroyed && revision === loadRevision)
				scheduleNotice = '취소 결과를 확인하지 못했습니다. 상태를 다시 확인하세요.';
		} finally {
			scheduleBusy = false;
		}
	}
	let nativeKakaoAvailable = $state(false);
	let nativeKakaoChecked = $state(false);
	let preparedShareFiles = $state<File[]>([]);
	let shareStatus = $state('');
	let finalControlsCollapsed = $state(false);
	let noteCollapsed = $state(false);
	let recoveryDraft = $state<Record<string, any> | null>(null);
	let recoveryInitialized = $state(false);
	let lastSavedFingerprint = '';
	let loadingTargetId = 0;
	let loadRevision = 0;
	let savePromise: Promise<boolean> | null = null;
	let destroyed = false;
	function recoveryKey(targetId: number) {
		const userId = privateCacheUser();
		return userId ? `ondo-private:aura-report:${userId}:${targetId}` : '';
	}
	function recoverySnapshot() {
		if (!report) return '';
		return JSON.stringify({
			targetId: report.targetId,
			savedAt: Date.now(),
			document: editor?.getJSON() ?? draftDocument,
			sourceNotes,
			questionChecks,
			lectureProgress,
			lectureComprehension,
			memoryBefore,
			memoryAfter,
			assessmentCsv,
			generatedReport,
			aiModel,
			finalParagraphs,
			problemSolvingNote,
			scoreMode
		});
	}
	function recoveryFingerprint(savedSnapshot?: Record<string, any>) {
		const snapshot = savedSnapshot ? JSON.stringify(savedSnapshot) : recoverySnapshot();
		if (!snapshot) return '';
		const value = JSON.parse(snapshot);
		delete value.savedAt;
		if (value.document) delete value.document.updatedAt;
		return JSON.stringify(value);
	}
	function persistRecovery() {
		if (!report || report.status === 'submitted') return;
		const key = recoveryKey(report.targetId);
		if (!key) return;
		try {
			const fingerprint = recoveryFingerprint();
			if (lastSavedFingerprint && fingerprint === lastSavedFingerprint)
				localStorage.removeItem(key);
			else {
				const snapshot = recoverySnapshot();
				localStorage.setItem(key, snapshot);
			}
		} catch {
			/* local recovery is best effort */
		}
	}
	function cancelAutosave() {
		if (autosaveTimer) window.clearTimeout(autosaveTimer);
		autosaveTimer = undefined;
	}
	onDestroy(() => {
		destroyed = true;
		cancelAutosave();
		if (scheduleTimer) window.clearInterval(scheduleTimer);
	});
	onMount(() => {
		const handleSaveShortcut = (event: KeyboardEvent) => {
			if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === 's') {
				event.preventDefault();
				if (report) void save(false);
			}
		};
		window.addEventListener('keydown', handleSaveShortcut);
		return () => window.removeEventListener('keydown', handleSaveShortcut);
	});

	function hasAppendixContent(document: EditorDocument) {
		return document.blocks.some((block) => {
			if (block.type === 'table') {
				return block.rows.some((row) =>
					row.some((cell) =>
						cell.blocks.some((child) => child.children.some((chunk) => chunk.text.trim()))
					)
				);
			}
			return block.children.some((chunk) => chunk.text.trim());
		});
	}

	let assessmentLocked = $derived(aiResults.length > 0 || Boolean(report?.generatedReportJson));
	let hasSavedGeneration = $derived(aiResults.length > 0 || Boolean(generatedReport));
	let includeAppendix = $derived(hasAppendixContent(draftDocument));

	async function load(targetId: number) {
		loadingTargetId = targetId;
		const revision = ++loadRevision;
		scheduledDelivery = null;
		scheduleReady = false;
		scheduleOutcomeUncertain = false;
		deliveryNotice = '';
		replacedScheduleNotice = '';
		try {
			const pending = localStorage.getItem(immediateOutcomeKey(targetId));
			immediateOutcomeUncertain = Boolean(pending);
			if (pending && pending !== '1') void recoverDelivery(targetId, pending, revision);
			else if (pending) deliveryNotice = deliveryView({}).message;
		} catch {
			immediateOutcomeUncertain = true;
			deliveryNotice = deliveryView({}).message;
		}
		scheduleNotice = '';
		recoveryInitialized = false;
		cancelAutosave();
		report = null;
		message = '';
		error = '';
		modalStage = 'closed';
		aiResults = [];
		aiHistoryLoaded = false;
		try {
			const [nextReport, attachments] = await Promise.all([
				personalApi.targetReport(targetId),
				personalApi.targetReportAttachments(targetId)
			]);
			if (destroyed || loadingTargetId !== targetId || revision !== loadRevision) return;
			report = nextReport;
			loadUnitTemplates();
			const document = normalizeDocument(nextReport.contentJson);
			initialDocument = document;
			draftDocument = document;
			sourceNotes = nextReport.sourceNotes;
			questionChecks = nextReport.questionChecks ?? {};
			lectureProgress = nextReport.lectureProgress ?? 5;
			lectureComprehension = nextReport.lectureComprehension ?? 5;
			memoryBefore = nextReport.memoryBefore ?? 4;
			memoryAfter = nextReport.memoryAfter ?? 5;
			assessmentCsv = (nextReport.assessmentJson?.items ?? [])
				.map((item) => `${item.name},${item.score}`)
				.join('\n');
			generatedReport = nextReport.generatedReportJson;
			finalParagraphs = [...(generatedReport?.learningContent.paragraphs ?? [])];
			problemSolvingNote = generatedReport?.problemSolvingNote ?? '';
			if (generatedReport) {
				assessmentCsv = (generatedReport.assessment?.items ?? [])
					.map((item) => `${item.name},${item.score}`)
					.join('\n');
				scoreMode = generatedReport.assessment ? 'auto' : 'none';
			}
			aiModel = nextReport.aiModel;
			blankTestImages = attachments
				.filter((item) => item.kind === 'blank_test')
				.map((item) => ({ ...item, url: personalApi.targetReportAttachmentUrl(item.id) }));
			problemImages = attachments
				.filter((item) => item.kind === 'problem_solving')
				.map((item) => ({ ...item, url: personalApi.targetReportAttachmentUrl(item.id) }));
			recoveryDraft = null;
			const key = recoveryKey(targetId);
			if (key) {
				try {
					const cached = JSON.parse(localStorage.getItem(key) || 'null');
					if (cached?.targetId === targetId && cached.document) recoveryDraft = cached;
				} catch {
					localStorage.removeItem(key);
				}
			}
			void refreshSchedule(targetId, revision);
			if (scheduleTimer) window.clearInterval(scheduleTimer);
			scheduleTimer = window.setInterval(() => {
				if (!scheduleBusy && !nativeKakaoBusy) void refreshSchedule(targetId, revision);
			}, 15000);
			await loadAi(targetId, revision);
			if (destroyed || loadingTargetId !== targetId || revision !== loadRevision) return;
			lastSavedFingerprint = recoveryFingerprint();
			if (recoveryDraft) {
				if (recoveryFingerprint(recoveryDraft) === lastSavedFingerprint) {
					if (key) localStorage.removeItem(key);
					recoveryDraft = null;
				} else {
					applyRecovery(recoveryDraft);
					const savedGeneration = report.generatedReportJson;
					if (savedGeneration && recoveryDraft.generatedReport?.runId !== savedGeneration.runId) {
						// A stale local draft must not replace the server's durable AI
						// generation with an older or empty result.
						generatedReport = savedGeneration;
						finalParagraphs = [...(savedGeneration.learningContent?.paragraphs ?? [])];
						problemSolvingNote = savedGeneration.problemSolvingNote ?? '';
					}
					recoveryDraft = null;
					message = '이 기기에 남아 있던 작성 내용을 복구해 서버에 저장하고 있습니다.';
				}
			}
			recoveryInitialized = true;
			// Show the saved report by default. A saved generation opens its final
			// editor/preview; never send it back through AI generation.
			modalStage = generatedReport ? 'final' : 'closed';
			if (page.url.searchParams.get('pdf') === '1' && !hasSavedGeneration) modalStage = 'generate';
		} catch (cause) {
			if (!destroyed && loadingTargetId === targetId && revision === loadRevision)
				error = cause instanceof Error ? cause.message : '리포트를 불러오지 못했습니다.';
		}
	}

	function parseAssessmentCsv() {
		if (!assessmentCsv.trim())
			return { formatName: '', items: [] as Array<{ name: string; score: number }> };
		const items = assessmentCsv
			.split(/\r?\n/)
			.filter((line) => line.trim())
			.map((line, index) => {
				const comma = line.lastIndexOf(',');
				if (comma < 1) throw new Error(`${index + 1}번째 줄은 ‘항목,점수’ 형식이어야 합니다.`);
				const name = line.slice(0, comma).trim();
				const score = Number(line.slice(comma + 1).trim());
				if (!name || !Number.isInteger(score) || score < 1 || score > 5)
					throw new Error(`${index + 1}번째 줄의 항목 또는 1~5점 점수를 확인해주세요.`);
				return { name, score };
			});
		return { formatName: '학습 내용 및 암기 정도 평가', items };
	}

	function lockedAssessmentRows() {
		try {
			return parseAssessmentCsv().items;
		} catch {
			return [];
		}
	}

	function updateLockedScore(index: number, score: number) {
		const rows = lockedAssessmentRows();
		if (!rows[index]) return;
		rows[index].score = Math.max(1, Math.min(5, score || 1));
		assessmentCsv = rows.map((item) => `${item.name},${item.score}`).join('\n');
	}

	async function loadAi(targetId: number, revision: number) {
		const [options, saved] = await Promise.all([
			personalApi.aiReportModels(),
			personalApi.aiReportResults(targetId)
		]);
		if (destroyed || loadingTargetId !== targetId || revision !== loadRevision) return;
		aiModels = options.models;
		selectedModel = aiModels.some((item) => item.id === aiModel)
			? (aiModel as string)
			: options.defaultModel;
		aiResults = saved.results;
		aiHistoryLoaded = true;
		const savedRunId = report?.generatedReportJson?.runId;
		const activeRun = savedRunId
			? saved.results.find((item) => item.runId === savedRunId)
			: saved.results.find(
					(item) => JSON.stringify(item.output) === JSON.stringify(generatedReport)
				);
		selectedAiRunId = activeRun
			? String(activeRun.runId)
			: saved.results[0]
				? String(saved.results[0].runId)
				: '';
		if (!generatedReport && saved.results[0]) {
			generatedReport = { ...saved.results[0].output, runId: saved.results[0].runId };
			aiModel = saved.results[0].model;
			finalParagraphs = [...generatedReport.learningContent.paragraphs];
			problemSolvingNote = generatedReport.problemSolvingNote ?? '';
			assessmentCsv = (generatedReport.assessment?.items ?? [])
				.map((item) => `${item.name},${item.score}`)
				.join('\n');
			// Keep the newest durable generation on the report itself. The report
			// row is the default source for PDFs and survives reloads independently
			// of whether the generation-history request is available later.
			await save(false, true);
		}
		if (
			!generatedReport?.assessment &&
			saved.results.length &&
			!saved.results[0].output.assessment
		) {
			scoreMode = 'none';
		}
	}

	async function restoreAiGeneration(runId: string) {
		const result = aiResults.find((item) => String(item.runId) === runId);
		if (!result) return;
		generatedReport = { ...structuredClone(result.output), runId: result.runId };
		aiModel = result.model;
		finalParagraphs = [...(result.output.learningContent?.paragraphs ?? [])];
		problemSolvingNote = result.output.problemSolvingNote ?? '';
		assessmentCsv = (result.output.assessment?.items ?? [])
			.map((item) => `${item.name},${item.score}`)
			.join('\n');
		scoreMode = result.output.assessment ? 'auto' : 'none';
		modalStage = 'final';
		message = `저장된 ${new Date(result.completedAt ?? Date.now()).toLocaleString('ko-KR')} 생성본을 불러왔습니다. 새 AI 생성을 하지 않았습니다.`;
		await save(false, true);
	}

	async function save(submit = false, silent = false): Promise<boolean> {
		const targetId = report?.targetId;
		cancelAutosave();
		while (savePromise) await savePromise;
		if (destroyed || !targetId || report?.targetId !== targetId) return false;
		const pending = saveSnapshot(submit, silent);
		savePromise = pending;
		try {
			return await pending;
		} finally {
			if (savePromise === pending) savePromise = null;
		}
	}

	async function saveSnapshot(submit = false, silent = false) {
		if (!report) return false;
		const reportId = report.id;
		const targetId = report.targetId;
		const revision = loadRevision;
		saving = true;
		saveStatus = 'saving';
		if (!silent) {
			message = '';
			error = '';
		}
		try {
			let assessment = report.assessmentJson ?? { formatName: '', items: [] };
			let assessmentIsValid = false;
			try {
				assessment = parseAssessmentCsv();
				assessmentIsValid = true;
			} catch (cause) {
				if (!silent) throw cause;
			}
			draftDocument = editor?.getJSON() ?? draftDocument;
			if (generatedReport) {
				generatedReport = {
					...generatedReport,
					problemSolvingNote: problemSolvingNote.trim(),
					assessment:
						scoreMode === 'none'
							? null
							: assessmentIsValid
								? {
										formatName: '학습 내용 및 암기 정도 평가',
										items: assessment.items ?? []
									}
								: generatedReport.assessment,
					learningContent: { paragraphs: finalParagraphs.filter((item) => item.trim()) }
				};
			}
			const recoveryText = recoverySnapshot();
			const recoverySavedAt = JSON.parse(recoveryText).savedAt as number;
			const savedFingerprint = recoveryFingerprint();
			const recoveryStorageKey = recoveryKey(targetId);
			if (recoveryStorageKey) {
				try {
					localStorage.setItem(recoveryStorageKey, recoveryText);
				} catch {
					/* server save still proceeds */
				}
			}
			let savedReport = await personalApi.updateTargetReport(reportId, {
				content_json: draftDocument,
				source_notes: sourceNotes,
				question_checks: questionChecks,
				lecture_progress: lectureProgress,
				lecture_comprehension: lectureComprehension,
				memory_before: memoryBefore,
				memory_after: memoryAfter,
				assessment_json: assessmentIsValid ? assessment : report.assessmentJson,
				...(generatingTargets[targetId]
					? {}
					: {
							generated_report_json: generatedReport,
							ai_model: aiModel
						}),
				status: submit ? 'ready' : report.status === 'submitted' ? 'submitted' : 'draft'
			});
			if (submit) savedReport = await personalApi.submitTargetReport(reportId);
			if (
				destroyed ||
				report?.targetId !== targetId ||
				loadingTargetId !== targetId ||
				revision !== loadRevision
			)
				return true;
			report = savedReport;
			lastSavedFingerprint = savedFingerprint;
			saveStatus = recoveryFingerprint() === savedFingerprint ? 'saved' : 'pending';
			const key = recoveryKey(targetId);
			if (key) {
				try {
					const current = localStorage.getItem(key);
					if (current && JSON.parse(current).savedAt <= recoverySavedAt)
						localStorage.removeItem(key);
				} catch {
					/* keep server save successful even if local storage is unavailable */
				}
			}
			message = submit
				? 'PDF 생성용 리포트를 확정했습니다.'
				: silent
					? '자동 저장했습니다.'
					: '임시저장했습니다.';
			return true;
		} catch (cause) {
			saveStatus = 'failed';
			if (!destroyed && report?.targetId === targetId && revision === loadRevision)
				error = cause instanceof Error ? cause.message : '리포트를 저장하지 못했습니다.';
			return false;
		} finally {
			saving = false;
		}
	}

	async function completeReport() {
		if (!report || report.status === 'submitted' || saving) return;
		if (!(await save(true))) return;
		// Submission intentionally removes only temporary image attachments. The
		// saved editor content and generated report remain available for PDF output.
		blankTestImages = [];
		problemImages = [];
		preparedShareFiles = [];
		shareStatus = '';
	}

	function queueAutosave(value: EditorDocument) {
		draftDocument = value;
		saveStatus = 'pending';
		persistRecovery();
	}

	function applyRecovery(saved: Record<string, any>) {
		draftDocument = normalizeDocument(saved.document);
		initialDocument = draftDocument;
		if (editor) editor.setJSON(draftDocument);
		sourceNotes = saved.sourceNotes ?? sourceNotes;
		questionChecks = saved.questionChecks ?? questionChecks;
		lectureProgress = saved.lectureProgress ?? lectureProgress;
		lectureComprehension = saved.lectureComprehension ?? lectureComprehension;
		memoryBefore = saved.memoryBefore ?? memoryBefore;
		memoryAfter = saved.memoryAfter ?? memoryAfter;
		assessmentCsv = saved.assessmentCsv ?? assessmentCsv;
		generatedReport = saved.generatedReport ?? generatedReport;
		aiModel = saved.aiModel ?? aiModel;
		finalParagraphs = saved.finalParagraphs ?? finalParagraphs;
		problemSolvingNote = saved.problemSolvingNote ?? problemSolvingNote;
		scoreMode = saved.scoreMode ?? scoreMode;
	}

	$effect(() => {
		if (!report || !recoveryInitialized || loadingTargetId !== report.targetId) return;
		void draftDocument;
		const fingerprint = recoveryFingerprint();
		persistRecovery();
		if (fingerprint === lastSavedFingerprint) return;
		cancelAutosave();
		const targetId = report.targetId;
		const runAutosave = () => {
			if (nativeKakaoBusy) {
				autosaveTimer = window.setTimeout(runAutosave, 2_500);
				return;
			}
			autosaveTimer = undefined;
			if (!destroyed && report?.targetId === targetId && loadingTargetId === targetId)
				void save(false, true);
		};
		autosaveTimer = window.setTimeout(runAutosave, 2_500);
		return cancelAutosave;
	});

	async function openGenerateModal() {
		if (!report || saving) return;
		draftDocument = editor?.getJSON() ?? draftDocument;
		if (report.status !== 'submitted' && !(await save(false, true))) return;
		if (!generatedReport && aiResults[0]) {
			await restoreAiGeneration(String(aiResults[0].runId));
			return;
		}
		finalParagraphs = [...(generatedReport?.learningContent.paragraphs ?? finalParagraphs)];
		modalStage = generatedReport ? 'final' : 'generate';
	}

	async function openRegenerationOptions() {
		if (!report || saving || aiGenerating) return;
		if (
			hasSavedGeneration &&
			!window.confirm(
				'저장된 리포트 대신 새 AI 리포트를 생성할까요? 기존 생성본은 저장 기록에 남습니다.'
			)
		)
			return;
		modalStage = 'generate';
	}

	async function closeReportModal() {
		if (generatedReport && modalStage === 'final') {
			let assessment = generatedReport.assessment;
			try {
				const parsed = parseAssessmentCsv();
				assessment =
					scoreMode === 'none'
						? null
						: { formatName: '학습 내용 및 암기 정도 평가', items: parsed.items };
			} catch {
				// 형식이 덜 작성된 상태에서도 다른 최종 편집 내용은 보존한다.
			}
			generatedReport = {
				...generatedReport,
				assessment,
				problemSolvingNote: problemSolvingNote.trim(),
				learningContent: { paragraphs: finalParagraphs.filter((item) => item.trim()) }
			};
			await save(false, true);
		}
		modalStage = generatedReport ? 'final' : 'closed';
	}

	async function generateAi(force = false) {
		if (!report || aiGenerating || !selectedModel) return;
		let assessment;
		try {
			assessment = parseAssessmentCsv();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '평가 항목을 확인해주세요.';
			return;
		}
		const targetId = report.targetId;
		const reportId = report.id;
		const options = {
			model: selectedModel,
			score_mode: scoreMode,
			assessment_items: assessment.items,
			highlight_semantics: { ...highlightSemantics },
			include_question_checks: includeQuestionChecks,
			force
		};
		generatingTargets[targetId] = true;
		delete generationNotices[targetId];
		error = '';
		try {
			if (!(await save(false, true))) {
				generationNotices[targetId] = '생성 전 저장에 실패해 AI 생성을 시작하지 못했습니다.';
				return;
			}
			const response = await personalApi.generateAiReports(targetId, options);
			const result = response.results[0];
			if (!result) throw new Error(response.errors[0]?.message ?? 'AI 결과가 없습니다.');

			// Persist only generation fields to the original report, never a snapshot
			// of whichever student's editor happens to be visible on completion.
			while (savePromise) await savePromise;
			const resultSave = personalApi
				.updateTargetReport(reportId, {
					generated_report_json: { ...result.output, runId: result.runId },
					ai_model: result.model
				})
				.then(
					() => true,
					() => false
				);
			savePromise = resultSave;
			try {
				if (!(await resultSave)) throw new Error('AI 결과를 저장하지 못했습니다.');
			} finally {
				if (savePromise === resultSave) savePromise = null;
			}
			generationNotices[targetId] = 'AI 생성 결과를 저장했습니다.';
			if (destroyed || report?.targetId !== targetId || loadingTargetId !== targetId) return;
			const activeRevision = loadRevision;
			let historyRefreshFailed = false;
			let results: AiReportResult[];
			try {
				results = (await personalApi.aiReportResults(targetId)).results;
			} catch {
				historyRefreshFailed = true;
				results = [result];
			}
			if (destroyed || report?.targetId !== targetId || activeRevision !== loadRevision) return;
			aiResults = historyRefreshFailed
				? [result, ...aiResults.filter((item) => item.runId !== result.runId)]
				: results;

			selectedAiRunId = String(result.runId);
			generatedReport = { ...result.output, runId: result.runId };
			aiModel = result.model;
			assessmentCsv = (result.output.assessment?.items ?? [])
				.map((item) => `${item.name},${item.score}`)
				.join('\n');
			finalParagraphs = [...result.output.learningContent.paragraphs];
			problemSolvingNote = result.output.problemSolvingNote ?? problemSolvingNote;
			const generatedMessage = result.reused
				? '동일한 입력의 저장된 AI 결과를 불러왔습니다.'
				: 'AI 리포트를 생성했습니다.';
			modalStage = 'final';
			const reportSaved = await save(false, true);
			if (destroyed || report?.targetId !== targetId || activeRevision !== loadRevision) return;
			message = `${generatedMessage} ${reportSaved ? '서버에 저장했습니다.' : '다만 서버 저장에 실패해 이 기기에 복구본을 남겼습니다.'}${historyRefreshFailed ? ' 생성 기록을 불러오지 못했지만 결과 생성은 성공했습니다. 중복 생성을 피하고 나중에 다시 확인해주세요.' : ''}`;
		} catch (cause) {
			generationNotices[targetId] =
				'AI 생성 또는 결과 저장을 확인하지 못했습니다. 중복 생성을 피하려면 생성 기록을 확인해주세요.';
			if (destroyed || report?.targetId !== targetId || loadingTargetId !== targetId) return;
			if (cause instanceof PersonalApiError && cause.code === 'ai_report_provider_blocked') {
				error =
					'AI 제공자가 이 자료의 생성을 제한했습니다. 입력 자료를 검토해 주세요. 같은 자료로 다시 시도해도 해결되지 않을 수 있습니다.';
			} else if (
				cause instanceof PersonalApiError &&
				cause.code === 'ai_report_provider_unavailable'
			) {
				error = 'AI 제공자가 일시적으로 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.';
			} else if (cause instanceof PersonalApiError && cause.status === 0) {
				error =
					'서버에 연결하지 못해 AI 리포트 생성 결과를 확인할 수 없습니다. 중복 생성을 피하려면 연결을 확인하고 생성 기록을 확인한 뒤 다시 시도해 주세요.';
			} else if (cause instanceof PersonalApiError && cause.status >= 500) {
				error = `AI 리포트를 생성하지 못했습니다. 원인은 확인되지 않았습니다 (오류 ${cause.status}). 중복 생성을 피하려면 생성 기록을 확인한 뒤 다시 시도해 주세요.`;
			} else {
				error =
					cause instanceof Error
						? cause.message
						: 'AI 리포트를 생성하지 못했습니다. 입력 내용을 확인해 주세요.';
			}
		} finally {
			delete generatingTargets[targetId];
		}
	}

	function blobToDataUrl(blob: Blob) {
		return new Promise<string>((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(String(reader.result));
			reader.onerror = () => reject(new Error('사진 파일을 읽지 못했습니다.'));
			reader.readAsDataURL(blob);
		});
	}

	async function compressImageBlob(blob: Blob) {
		if (!('createImageBitmap' in globalThis)) return blob;
		try {
			const bitmap = await createImageBitmap(blob);
			const maxSide = 2400;
			const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
			const canvas = document.createElement('canvas');
			canvas.width = Math.max(1, Math.round(bitmap.width * scale));
			canvas.height = Math.max(1, Math.round(bitmap.height * scale));
			const context = canvas.getContext('2d');
			if (!context) return blob;
			context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
			bitmap.close();
			return await new Promise<Blob>((resolve) =>
				canvas.toBlob((compressed) => resolve(compressed ?? blob), 'image/jpeg', 0.82)
			);
		} catch {
			return blob;
		}
	}

	function withImageTimeout<T>(promise: Promise<T>, filename: string) {
		return new Promise<T>((resolve, reject) => {
			const timer = window.setTimeout(
				() => reject(new Error(`${filename}: 20초 안에 이미지 변환이 끝나지 않았습니다.`)),
				20_000
			);
			promise.then(resolve, reject).finally(() => window.clearTimeout(timer));
		});
	}

	async function imageFileToDataUrl(file: File) {
		const isHeic =
			/\.(heic|heif)$/i.test(file.name) ||
			/image\/(heic|heif|heic-sequence|heif-sequence)/i.test(file.type);
		if (isHeic) {
			try {
				const { default: heic2any } = await import('heic2any');
				const converted = await withImageTimeout(
					heic2any({ blob: file, toType: 'image/jpeg', quality: 0.9 }),
					file.name
				);
				const jpeg = Array.isArray(converted) ? converted[0] : converted;
				if (!jpeg) throw new Error('변환 결과가 비어 있습니다.');
				return await blobToDataUrl(await compressImageBlob(jpeg));
			} catch (cause) {
				throw new Error(
					`HEIC 변환 실패: ${cause instanceof Error ? cause.message : '지원하지 않는 파일입니다.'}`
				);
			}
		}
		if (!file.type.startsWith('image/')) throw new Error('이미지 파일이 아닙니다.');
		return blobToDataUrl(await compressImageBlob(file));
	}

	async function pdfToImageFiles(file: File) {
		const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs');
		pdfjs.GlobalWorkerOptions.workerSrc = new URL(
			'pdfjs-dist/legacy/build/pdf.worker.mjs',
			import.meta.url
		).toString();
		const pdfDocument = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
		if (pdfDocument.numPages > 30) throw new Error('PDF는 최대 30페이지까지 첨부할 수 있습니다.');
		const files: File[] = [];
		for (let pageNumber = 1; pageNumber <= pdfDocument.numPages; pageNumber++) {
			const page = await pdfDocument.getPage(pageNumber);
			const viewport = page.getViewport({ scale: 1.6 });
			const canvas = document.createElement('canvas');
			canvas.width = Math.ceil(viewport.width);
			canvas.height = Math.ceil(viewport.height);
			const context = canvas.getContext('2d');
			if (!context) throw new Error('PDF 페이지를 그릴 수 없습니다.');
			await page.render({ canvasContext: context, viewport }).promise;
			const blob = await new Promise<Blob>((resolve, reject) =>
				canvas.toBlob(
					(value: Blob | null) =>
						value ? resolve(value) : reject(new Error('PDF 이미지 변환에 실패했습니다.')),
					'image/jpeg',
					0.88
				)
			);
			files.push(
				new File([blob], `${file.name.replace(/\.pdf$/i, '')}-${pageNumber}.jpg`, {
					type: 'image/jpeg'
				})
			);
		}
		return files;
	}

	async function addAttachmentImages(files: FileList | null, kind: 'blank' | 'problem') {
		if (!files?.length || attachmentBusy) return;
		attachmentBusy = true;
		attachmentNotice = `${files.length}개 사진을 처리하는 중입니다…`;
		const added: AttachmentPreview[] = [];
		const failures: string[] = [];
		const sourceFiles: File[] = [];
		for (const file of Array.from(files)) {
			try {
				if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name))
					sourceFiles.push(...(await pdfToImageFiles(file)));
				else sourceFiles.push(file);
			} catch (cause) {
				failures.push(`${file.name}: ${cause instanceof Error ? cause.message : 'PDF 변환 실패'}`);
			}
		}
		for (const file of sourceFiles) {
			try {
				const dataUrl = await imageFileToDataUrl(file);
				const blob = await fetch(dataUrl).then((response) => response.blob());
				if (!report) throw new Error('리포트를 불러오는 중입니다.');
				const saved = await personalApi.uploadTargetReportAttachment(
					report.targetId,
					kind === 'blank' ? 'blank_test' : 'problem_solving',
					new File([blob], file.name.replace(/\.(heic|heif)$/i, '.jpg') || 'image.jpg', {
						type: blob.type || 'image/jpeg'
					})
				);
				added.push({
					...saved,
					kind: saved.kind as 'blank_test' | 'problem_solving',
					byteSize: blob.size,
					createdAt: new Date().toISOString(),
					url: personalApi.targetReportAttachmentUrl(saved.id)
				});
			} catch (cause) {
				failures.push(`${file.name}: ${cause instanceof Error ? cause.message : '처리 실패'}`);
			}
		}
		if (kind === 'blank') blankTestImages = [...blankTestImages, ...added];
		else problemImages = [...problemImages, ...added];
		preparedShareFiles = [];
		shareStatus = '';
		attachmentNotice = failures.length
			? `${added.length}개 추가됨 · 실패 ${failures.length}개 — ${failures.join(' / ')}`
			: `${added.length}개 사진을 추가했습니다.`;
		attachmentBusy = false;
	}

	async function removeAttachmentImage(kind: 'blank' | 'problem', index: number) {
		const item = (kind === 'blank' ? blankTestImages : problemImages)[index];
		if (!item) return;
		await personalApi.deleteTargetReportAttachment(item.id);
		if (kind === 'blank')
			blankTestImages = blankTestImages.filter((_, itemIndex) => itemIndex !== index);
		else problemImages = problemImages.filter((_, itemIndex) => itemIndex !== index);
		preparedShareFiles = [];
		shareStatus = '';
	}

	async function pasteAttachmentImages(event: ClipboardEvent, kind: 'blank' | 'problem') {
		const images = Array.from(event.clipboardData?.files ?? []).filter((file) =>
			file.type.startsWith('image/')
		);
		if (!images.length) return;
		event.preventDefault();
		const transfer = new DataTransfer();
		images.forEach((image) => transfer.items.add(image));
		await addAttachmentImages(transfer.files, kind);
	}

	async function downloadPdf() {
		if (!report || pdfBusy) return;
		pdfBusy = true;
		error = '';
		try {
			const assessment = parseAssessmentCsv();
			if (generatedReport) {
				generatedReport = {
					...generatedReport,
					problemSolvingNote: problemSolvingNote.trim(),
					assessment:
						scoreMode === 'none'
							? null
							: {
									formatName: '학습 내용 및 암기 정도 평가',
									items: assessment.items
								},
					learningContent: { paragraphs: finalParagraphs.filter((item) => item.trim()) }
				};
			}
			if (!(await save(false, true))) return;
			const pdf = await personalApi.targetReportPdf(report.targetId);
			const safeName =
				`${report.schoolName}_${progressStageLabels[report.progressStage]}_${report.roundLabel}_${report.studentName}`.replace(
					/[\\/:*?"<>|]/g,
					'_'
				);
			const url = URL.createObjectURL(pdf);
			const link = document.createElement('a');
			link.href = url;
			link.download = `${safeName}_클리닉리포트.pdf`;
			link.click();
			URL.revokeObjectURL(url);
			message = 'PDF 다운로드를 시작했습니다.';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'PDF를 만들지 못했습니다.';
		} finally {
			pdfBusy = false;
		}
	}

	async function prepareKakaoShare() {
		if (!report || kakaoBusy) return;
		kakaoBusy = true;
		error = '';
		shareStatus = '서버에서 리포트 PDF를 만드는 중입니다…';
		try {
			const assessment = parseAssessmentCsv();
			if (generatedReport) {
				generatedReport = {
					...generatedReport,
					problemSolvingNote: problemSolvingNote.trim(),
					assessment:
						scoreMode === 'none'
							? null
							: { formatName: '학습 내용 및 암기 정도 평가', items: assessment.items },
					learningContent: { paragraphs: finalParagraphs.filter((item) => item.trim()) }
				};
			}
			if (!(await save(false, true))) return;
			const pdf = await personalApi.targetReportPdf(report.targetId);
			const file = new File([pdf], `clinic-report-${report.targetId}.pdf`, {
				type: 'application/pdf'
			});
			const shareData: ShareData = { files: [file] };
			if (!navigator.share || !navigator.canShare?.(shareData)) {
				throw new Error(
					'이 브라우저는 이미지 묶음 공유를 지원하지 않습니다. 모바일 Chrome 또는 Safari에서 열어주세요.'
				);
			}
			preparedShareFiles = [file];
			shareStatus = '서버에서 만든 PDF가 준비되었습니다. 아래 버튼을 한 번 더 눌러주세요.';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '카카오톡으로 보내지 못했습니다.';
			shareStatus = '';
		} finally {
			kakaoBusy = false;
		}
	}

	function sharePreparedImages() {
		if (!preparedShareFiles.length || !navigator.share) return;
		// 사용자 탭과 같은 이벤트 안에서 즉시 호출해야 모바일 공유 권한이 유지된다.
		const files = preparedShareFiles;
		navigator.share({ files }).then(
			() => {
				message = '서버에서 만든 클리닉 리포트 PDF를 공유했습니다.';
				preparedShareFiles = [];
				shareStatus = '';
			},
			(cause: unknown) => {
				if (cause instanceof DOMException && cause.name === 'AbortError') {
					shareStatus = '공유가 취소되었습니다. 준비된 버튼을 다시 누르면 됩니다.';
					return;
				}
				error = cause instanceof Error ? cause.message : '공유창을 열지 못했습니다.';
			}
		);
	}

	async function checkNativeKakao() {
		if (nativeKakaoChecked) return;
		nativeKakaoChecked = true;
		try {
			const status = await personalApi.nativeKakaoStatus();
			nativeKakaoAvailable = status.enabled && status.destination === '나와의 채팅';
		} catch {
			// 서버가 허용한 단일 계정 외에는 버튼 자체를 표시하지 않는다.
			nativeKakaoAvailable = false;
		}
	}

	async function sendToNativeKakao() {
		if (
			!report ||
			nativeKakaoBusy ||
			scheduleBusy ||
			kakaoBusy ||
			(scheduledDelivery && ['generating', 'sending'].includes(scheduledDelivery.state))
		)
			return;

		nativeKakaoBusy = true;
		++scheduleReadVersion;
		deliveryRecoveryVersion++;
		deliveryNotice = '';
		replacedScheduleNotice = '';
		error = '';
		message = '';
		shareStatus = '서버에서 리포트를 만들고 카카오톡 전송을 준비하는 중입니다…';
		try {
			const assessment = parseAssessmentCsv();
			if (generatedReport) {
				generatedReport = {
					...generatedReport,
					problemSolvingNote: problemSolvingNote.trim(),
					assessment:
						scoreMode === 'none'
							? null
							: { formatName: '학습 내용 및 암기 정도 평가', items: assessment.items },
					learningContent: { paragraphs: finalParagraphs.filter((item) => item.trim()) }
				};
			}
			if (!(await save(false, true)))
				throw new Error('리포트를 저장하지 못해 전송을 중단했습니다.');
			shareStatus = 'Mac mini에서 서버 PDF 생성과 카카오톡 전송을 진행하는 중입니다…';
			const sendingTargetId = report.targetId;
			const sendingRevision = loadRevision;
			const replacedScheduleId = scheduledDelivery && ['queued', 'ready'].includes(scheduledDelivery.state)
				? scheduledDelivery.id : null;
			const requestId = crypto.randomUUID();
			try {
				localStorage.setItem(immediateOutcomeKey(sendingTargetId), requestId);
			} catch {
				throw new Error('전송 상태를 안전하게 저장할 수 없어 전송하지 않았습니다.');
			}
			immediateOutcomeUncertain = true;
			try {
				const result = await personalApi.sendServerGeneratedClinicReport(
					sendingTargetId,
					requestId
				);
				applyDeliveryResult(sendingTargetId, result);
			} catch (cause) {
				const detail = cause instanceof PersonalApiError ? cause.detail : null;
				if (detail && typeof detail === 'object' && 'deliveryStatus' in detail)
					applyDeliveryResult(sendingTargetId, detail as DeliveryResult);
				else await recoverDelivery(sendingTargetId, requestId, loadRevision);
			}
			if (replacedScheduleId) {
				try {
					const previous = await request<ScheduledDelivery>(`/aura/targets/${sendingTargetId}/kakao-clinic/scheduled-deliveries/${encodeURIComponent(replacedScheduleId)}`);
					if (!destroyed && sendingRevision === loadRevision && loadingTargetId === sendingTargetId) {
						if (previous.state === 'cancelled' && previous.errorCode === 'superseded_by_immediate') {
							replacedScheduleNotice = '기존 예약이 취소되었습니다. 즉시 전송이 실패해도 예약은 복원되지 않습니다.';
							scheduledDelivery = previous;
						} else {
							replacedScheduleNotice = '기존 예약이 즉시 전송으로 취소되었는지 확인되지 않았습니다.';
						}
					}
				} catch {
					if (!destroyed && sendingRevision === loadRevision && loadingTargetId === sendingTargetId)
						replacedScheduleNotice = '기존 예약이 즉시 전송으로 취소되었는지 확인되지 않았습니다.';
				}
			}
			shareStatus = '';
			preparedShareFiles = [];
		} catch (cause) {
			error = immediateOutcomeUncertain
				? '전송 결과를 확인할 수 없습니다.'
				: cause instanceof Error
					? cause.message
					: '클리닉 리포트 전송에 실패했습니다.';
			shareStatus = '';
		} finally {
			nativeKakaoBusy = false;
		}
	}

	async function switchStudent(targetId: number) {
		templateConfirm = false;
		previousDraft = null;
		if (!report || targetId === report.targetId || switching) return;
		switching = true;
		try {
			if (!(await save(false, true))) return;
			await goto(`/personal-project/aura/reports/${targetId}`, {
				replaceState: true,
				noScroll: true,
				keepFocus: false
			});
		} finally {
			switching = false;
		}
	}

	let templateConfirm = $state(false);
	let previousDraft = $state<EditorDocument | null>(null);
	type UnitTemplate = { id: string; name: string; document: EditorDocument; updatedAt: string };
	let unitTemplates = $state<UnitTemplate[]>([]);
	let unitTemplateName = $state('');
	let selectedUnitTemplate = $state('');
	let unitTemplateNotice = $state('');
	function unitTemplateKey() {
		const userId = privateCacheUser();
		return userId ? `ondo-private:aura-unit-templates:${userId}` : '';
	}
	function loadUnitTemplates() {
		const key = unitTemplateKey();
		if (!key) return;
		try {
			const stored = JSON.parse(localStorage.getItem(key) || '[]');
			unitTemplates = Array.isArray(stored)
				? stored.filter((item): item is UnitTemplate =>
						Boolean(
							item && typeof item.id === 'string' && typeof item.name === 'string' && item.document
						)
					)
				: [];
		} catch {
			unitTemplates = [];
		}
	}
	function saveUnitTemplate() {
		const name = unitTemplateName.trim();
		if (!name || !report || report.status === 'submitted') return;
		const key = unitTemplateKey();
		if (!key) return;
		loadUnitTemplates();
		if (
			unitTemplates.some((item) => item.name === name) &&
			!confirm(`‘${name}’ 단원 양식을 현재 내용으로 덮어쓸까요?`)
		)
			return;
		const entry: UnitTemplate = {
			id: crypto.randomUUID(),
			name,
			document: editor?.getJSON() ?? draftDocument,
			updatedAt: new Date().toISOString()
		};
		const next = [entry, ...unitTemplates.filter((item) => item.name !== name)];
		try {
			localStorage.setItem(key, JSON.stringify(next));
			unitTemplates = next;
		} catch {
			unitTemplateNotice = '기기 저장 공간에 양식을 저장하지 못했습니다.';
			return;
		}
		selectedUnitTemplate = entry.id;
		unitTemplateName = '';
		unitTemplateNotice = `‘${name}’ 단원 양식을 저장했습니다.`;
	}
	function applyUnitTemplate() {
		const template = unitTemplates.find((item) => item.id === selectedUnitTemplate);
		if (!template) {
			unitTemplateNotice = '단원 양식을 다시 선택해주세요.';
			return;
		}
		if (!editor) {
			unitTemplateNotice = '편집기가 준비되면 다시 눌러주세요.';
			return;
		}
		if (!report || report.status === 'submitted') {
			unitTemplateNotice = '작성 중인 리포트에서만 내용을 추가할 수 있습니다.';
			return;
		}
		const current = editor.getJSON();
		const templateRich = JSON.parse(JSON.stringify(toRich(template.document))) as ReturnType<
			typeof toRich
		>;
		const renewIds = (node: typeof templateRich) => {
			if (node.attrs?.id) node.attrs.id = crypto.randomUUID();
			node.content?.forEach(renewIds);
		};
		templateRich.content?.forEach(renewIds);
		const rich = toRich(current);
		const next = fromRich(
			{
				type: 'doc',
				content: [
					...(rich.content ?? []),
					{
						type: 'heading',
						attrs: { id: crypto.randomUUID(), level: 2, indent: 0 },
						content: [{ type: 'text', text: template.name }]
					},
					...(templateRich.content ?? [])
				]
			},
			current
		);
		editor.setJSON(next);
		queueAutosave(next);
		unitTemplateNotice = `‘${template.name}’ 내용을 뒤에 추가했습니다. 필요에 따라 수정하세요.`;
	}
	async function useTemplate() {
		if (!report || saving || switching) return;
		const targetId = report.targetId;
		if (!(await save(false, true))) return;
		try {
			const result = await request<{ document: EditorDocument }>(
				`/aura/targets/${targetId}/template`
			);
			if (report?.targetId !== targetId) return;
			previousDraft = editor?.getJSON() ?? draftDocument;
			editor?.setJSON(result.document);
			questionChecks = {};
			queueAutosave(editor?.getJSON() ?? result.document);
			message = '기본양식으로 전환했습니다. 이전 내용으로 되돌릴 수 있습니다.';
		} catch (cause) {
			error = String(cause);
		}
	}

	async function saveAsTemplate() {
		if (!report || saving || report.roundNumbers.length > 1) return;
		templateConfirm = false;
		saving = true;
		try {
			draftDocument = editor?.getJSON() ?? draftDocument;
			const result = await personalApi.saveRoundTemplate(
				report.schoolId,
				report.progressStage,
				report.roundNumber,
				draftDocument
			);
			message = `기본 양식 v${result.version}으로 저장했습니다.`;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '기본 양식을 저장하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	$effect(() => {
		const targetId = Number(page.params.targetId);
		if (targetId && targetId !== loadingTargetId) void load(targetId);
		void checkNativeKakao();
	});
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Student report</p>
		<h1>{report?.studentName ?? '리포트 불러오는 중'}</h1>
		<p>
			{report
				? `${report.schoolName} · ${progressStageLabels[report.progressStage]} · ${report.roundLabel} · 기본 양식 ${report.templateVersion ? `v${report.templateVersion}` : '회차별 결합'}`
				: '잠시만 기다려주세요.'}
		</p>
	</div>
	<div class="page-head-actions">
		<a
			class="ghost-button back"
			href={report
				? `/personal-project/aura/schools/${report.schoolId}`
				: '/personal-project/aura/schools'}>← 회차 목록</a
		>
	</div>
</div>

{#if error}<div class="error-banner">{error}</div>{/if}
{#if message}<div class="success-banner">{message}</div>{/if}
{#if report}
	<nav class="student-switcher card" aria-label="같은 클리닉 학생 전환">
		<div>
			<strong>{report.roundLabel} 클리닉 학생</strong><small
				>학생을 바꿔도 현재 스크롤 위치를 유지합니다.</small
			>
		</div>
		<div class="student-tabs">
			{#each report.clinicTargets as target (target.id)}
				<button
					type="button"
					class:active={target.id === report.targetId}
					onclick={() => switchStudent(target.id)}
					disabled={switching}
				>
					{target.studentName}<span
						>{generatingTargets[target.id]
							? 'AI 생성 중'
							: generationNotices[target.id] ||
								(target.status === 'submitted'
									? '완료'
									: target.status === 'unwritten'
										? '미작성'
										: '작성 중')}</span
					>
				</button>
			{/each}
		</div>
	</nav>

	<div class="report-layout" class:note-hidden={noteCollapsed}>
		<aside class="card note-panel" class:note-collapsed={noteCollapsed}>
			<div class="note-heading">
				<div>
					<p class="eyebrow">Report tools</p>
					<h2>리포트 도구</h2>
				</div>
				<button class="note-toggle" onclick={() => (noteCollapsed = !noteCollapsed)}
					>{noteCollapsed ? '열기' : '접기'}</button
				>
			</div>
			{#if !noteCollapsed}<div class="quick-actions">
					<button
						disabled={!aiHistoryLoaded || aiGenerating || saving}
						onclick={async () => {
							await openGenerateModal();
							if (!hasSavedGeneration) await generateAi(false);
						}}>{hasSavedGeneration ? '저장된 리포트 열기' : 'AI 리포트 생성'}</button
					>
					<button disabled={saving} onclick={useTemplate}>기본양식으로 전환</button>
				</div>
				{#if previousDraft}<button
						onclick={() => {
							if (previousDraft) {
								editor?.setJSON(previousDraft);
								previousDraft = null;
								queueAutosave(editor?.getJSON() ?? draftDocument);
							}
						}}>양식 전환 되돌리기</button
					>{/if}
				{@render attachments()}
				<div class="highlight-guide">
					<span></span><strong>형광 표시 단축키</strong>
					<small>Ctrl/Cmd+Alt+1 살구 · +2 노랑 · +3 주황 · +H 최근 색</small>
				</div>
				<details class="note-shortcuts">
					<summary>에디터 단축키 보기</summary>
					<div>
						<span><kbd>Ctrl/Cmd+B</kbd> 굵게</span>
						<span><kbd>Ctrl/Cmd+S</kbd> 수동 저장</span>
						<span><kbd>Ctrl/Cmd+Z</kbd> 실행 취소</span>
						<span><kbd>Ctrl/Cmd+Shift+Z</kbd> 다시 실행</span>
						<span><kbd>Ctrl/Cmd+Shift+B</kbd> 인용 전환</span>
						<span><kbd>Ctrl/Cmd+Alt+H</kbd> 최근 형광색</span>
						<span><kbd>Ctrl/Cmd+Alt+1/2/3</kbd> 살구/노랑/주황</span>
						<span><kbd>Tab / Shift+Tab</kbd> 들여쓰기/내어쓰기</span>
					</div>
				</details>
				{@render reportTools()}
			{/if}
		</aside>

		<section class="card editor-panel">
			<header>
				<div>
					<p class="eyebrow">Report editor</p>
					<h2>{report.studentName} 리포트</h2>
				</div>
				<div class="editor-header-actions">
					{#if noteCollapsed}<button class="note-toggle" onclick={() => (noteCollapsed = false)}
							>퀵메모 열기</button
						>{/if}
					<button class="ghost-button" onclick={() => void save(false)} disabled={saving}
						>저장 · Ctrl/Cmd+S</button
					>
					<button class="ghost-button" onclick={downloadPdf} disabled={pdfBusy || saving}
						>{pdfBusy ? 'PDF 준비 중…' : 'PDF 받기'}</button
					>
					{#if report.status !== 'submitted'}<button
							class="complete-status-button"
							onclick={completeReport}
							disabled={saving}>작성 완료</button
						>{/if}
					<span class={`status-pill ${report.status}`}
						>{saving
							? '저장 중…'
							: saveStatus === 'failed'
								? '저장 실패 · 다시 저장하세요'
								: saveStatus === 'pending'
									? '저장 대기 중…'
									: report.status === 'submitted'
										? '제출 완료'
										: '저장됨'}</span
					>
				</div>
			</header>
			<div class="editor-wrap">
				<div class="schedule-panel" aria-label="카카오 예약 전송">
					<div class="schedule-actions">
						<button
							class="schedule-primary"
							onclick={scheduleDelivery}
							disabled={scheduleBusy ||
								nativeKakaoBusy ||
								saving ||
													!scheduleReady ||
								(!!scheduledDelivery &&
									scheduledDelivery.state !== 'failed' &&
									scheduledDelivery.state !== 'cancelled')}
						>
							{scheduleBusy
								? '예약 중…'
								: scheduledDelivery?.state === 'failed'
									? '90분 후 다시 예약'
									: '90분 후 전송 예약'}
						</button>
						{#if scheduleReady && scheduledDelivery && ['queued', 'generating', 'ready'].includes(scheduledDelivery.state)}<button
								onclick={cancelScheduledDelivery}
								disabled={scheduleBusy}>예약 취소</button
							>{/if}

						{#if !scheduleReady && !scheduleBusy}<button
								onclick={() => void refreshSchedule(report!.targetId, loadRevision)}
								>상태 다시 확인</button
							>{/if}
					</div>
					<div class="schedule-status" role="status">
						{#if scheduledDelivery}<strong>{scheduleLabels[scheduledDelivery.state]}</strong
							>{#if !['cancelled', 'failed'].includes(scheduledDelivery.state)}<span
									>예정 시각: {new Date(scheduledDelivery.sendAfter * 1000).toLocaleString(
										'ko-KR'
									)}</span
								>{/if}{/if}
						{#if scheduleNotice}<span>{scheduleNotice}</span>{/if}
						{#if immediateOutcomeUncertain && !nativeKakaoBusy}<span
								>이전 전송 결과를 확인할 수 없습니다.</span
							>{/if}
					</div>
				</div>
				<p class="question-check-guide">
					질문이나 참고 문구는 인용으로 구분하세요. Ctrl/Cmd+Shift+B로 전환합니다.
				</p>
				<div class="unit-template-tools" aria-label="단원 양식">
					<strong>단원 양식</strong>
					<p>
						지금 편집기에 적힌 단원 내용 전체를 이름 붙여 저장합니다. 다른 리포트에서는 양식을 골라
						기존 내용 뒤에 추가할 수 있습니다.
					</p>
					<div class="unit-template-actions">
						<input
							aria-label="저장할 단원 양식 이름"
							placeholder="단원 이름, 예: 세포호흡"
							bind:value={unitTemplateName}
						/>
						<button
							class="template-button"
							onclick={saveUnitTemplate}
							disabled={saving || report.status === 'submitted' || !unitTemplateName.trim()}
							>현재 내용으로 양식 저장</button
						>
						<select
							aria-label="적용할 단원 양식"
							bind:value={selectedUnitTemplate}
							onfocus={loadUnitTemplates}
						>
							<option value="">저장된 단원 양식 선택</option>
							{#each unitTemplates as template (template.id)}<option value={template.id}
									>{template.name}</option
								>{/each}
						</select>
						<button
							class="template-button"
							onclick={applyUnitTemplate}
							disabled={saving || report.status === 'submitted' || !selectedUnitTemplate}
							>선택 내용 추가</button
						>
					</div>
					{#if unitTemplateNotice}<small role="status">{unitTemplateNotice}</small>{/if}
				</div>
				{#key report.targetId}
					<AuraReportEditor
						bind:this={editor}
						initialValue={initialDocument}
						readonly={switching}
						placeholder="회차 기본 양식을 바탕으로 리포트를 작성하세요."
						onchange={queueAutosave}
						{questionChecks}
						onquestionchange={(blockId, checked) => {
							if (switching) return;
							questionChecks = { ...questionChecks, [blockId]: checked };
							queueAutosave(editor?.getJSON() ?? draftDocument);
						}}
					/>
				{/key}
			</div>
			{#if templateConfirm}<section
					class="template-confirm"
					role="group"
					aria-label="학교·회차 기본 양식 저장 확인"
				>
					<button class="template-button" disabled={saving} onclick={saveAsTemplate}>저장</button
					><button class="template-cancel" onclick={() => (templateConfirm = false)}>취소</button>
				</section>{/if}
			<footer>
				<button
					class="template-button"
					onclick={() => (templateConfirm = true)}
					disabled={saving || report.roundNumbers.length > 1}
				>
					{report.roundNumbers.length > 1
						? '복수 회차 결합 리포트'
						: '이 학교·회차 기본 양식 저장'}</button
				>
			</footer>
		</section>
	</div>
{/if}

{#snippet attachments()}<div class="attachment-fields">
		{#if attachmentNotice}<p
				class="attachment-notice"
				class:attachment-error={attachmentNotice.includes('실패')}
			>
				{attachmentNotice}
			</p>{/if}
		<label
			><strong>백지테스트 사진</strong><small>JPG, PNG, WebP와 아이폰 HEIC/HEIF를 지원합니다.</small
			><input
				type="file"
				accept="image/*,.heic,.heif,application/pdf"
				multiple
				capture="environment"
				onchange={async (event) => {
					const input = event.currentTarget;
					await addAttachmentImages(input.files, 'blank');
					input.value = '';
				}}
				disabled={attachmentBusy}
			/></label
		>
		<button
			type="button"
			class="paste-image-button"
			onpaste={(event) => pasteAttachmentImages(event, 'blank')}
			>복사한 사진 붙여넣기: 이 버튼을 누른 뒤 Ctrl/Cmd+V</button
		>
		{#if blankTestImages.length}<div class="attachment-list">
				{#each blankTestImages as image, index}<figure>
						<img src={image.url} alt={`백지테스트 ${index + 1}`} /><button
							aria-label={`백지테스트 ${index + 1} 삭제`}
							onclick={() => removeAttachmentImage('blank', index)}>×</button
						>
						<figcaption>백지테스트 {index + 1}</figcaption>
					</figure>{/each}
			</div>{/if}
		<label
			><strong>문제 풀이 사진</strong><small
				>추가한 사진을 아래에서 확인하고 개별 삭제할 수 있습니다.</small
			><input
				type="file"
				accept="image/*,.heic,.heif,application/pdf"
				multiple
				capture="environment"
				onchange={async (event) => {
					const input = event.currentTarget;
					await addAttachmentImages(input.files, 'problem');
					input.value = '';
				}}
				disabled={attachmentBusy}
			/></label
		>
		<button
			type="button"
			class="paste-image-button"
			onpaste={(event) => pasteAttachmentImages(event, 'problem')}
			>복사한 사진 붙여넣기: 이 버튼을 누른 뒤 Ctrl/Cmd+V</button
		>
		{#if problemImages.length}<div class="attachment-list">
				{#each problemImages as image, index}<figure>
						<img src={image.url} alt={`문제풀이 ${index + 1}`} /><button
							aria-label={`문제풀이 ${index + 1} 삭제`}
							onclick={() => removeAttachmentImage('problem', index)}>×</button
						>
						<figcaption>문제풀이 {index + 1}</figcaption>
					</figure>{/each}
			</div>{/if}
	</div>{/snippet}

{#snippet reportTools()}{#if report}
		<div class="inline-report-tools">
			{#if modalStage === 'closed'}
				{#if aiHistoryLoaded && !hasSavedGeneration}<button
						class="primary-button"
						onclick={openGenerateModal}>AI 리포트 생성</button
					>{/if}
			{:else}
				<section class="report-modal" aria-label="클리닉 리포트 생성">
					<header>
						<div>
							<p class="eyebrow">Clinic report</p>
							<h2>{modalStage !== 'final' ? '리포트 생성' : '생성된 리포트'}</h2>
						</div>
						<div class="modal-actions">
							{#if modalStage !== 'final'}
								<select bind:value={selectedModel} aria-label="AI 모델 선택">
									{#each aiModels as model}<option
											value={model.id}
											disabled={model.available === false}
											>{model.label}{model.available === false ? ' · API 키 필요' : ''}</option
										>{/each}
								</select>
								<button
									class="primary-button"
									onclick={() => generateAi(hasSavedGeneration)}
									disabled={aiGenerating}
									>{aiGenerating
										? '생성 중…'
										: hasSavedGeneration
											? '새 AI 리포트 생성'
											: 'AI 생성하기'}</button
								>
							{/if}
						</div>
					</header>

					{#if modalStage !== 'final'}
						<div class="generate-columns">
							<section class="generate-input">
								<div class="student-summary">
									<strong>{report.studentName}</strong><span
										>{report.schoolName} · {progressStageLabels[report.progressStage]} · {report.roundLabel}</span
									>
								</div>
								<label class="score-mode"
									><span>평가 항목</span><select
										bind:value={scoreMode}
										disabled={assessmentLocked && lockedAssessmentRows().length === 0}
										><option value="auto">평가 포함</option><option value="none">학습 내용만</option
										></select
									></label
								>
								<section class="generation-rules">
									<strong>형광색 의미</strong>
									<small>이번 AI 생성에서만 적용됩니다.</small>
									<label
										><span>노랑</span><select bind:value={highlightSemantics.yellow}>
											<option value="fixed">고침</option><option value="unfixed">못고침</option
											><option value="not_reasked">재질문 못함</option>
										</select></label
									>
									<label
										><span>주황</span><select bind:value={highlightSemantics.orange}>
											<option value="fixed">고침</option><option value="unfixed">못고침</option
											><option value="not_reasked">재질문 못함</option>
										</select></label
									>
									<label
										><span>살구</span><select bind:value={highlightSemantics.peach}>
											<option value="fixed">고침</option><option value="unfixed">못고침</option
											><option value="not_reasked">재질문 못함</option>
										</select></label
									>
									<label class="question-rule"
										><input type="checkbox" bind:checked={includeQuestionChecks} />
										<span>과거 리포트의 질문 표시도 AI에 전달</span></label
									>
								</section>
								<div class="rating-grid">
									<label
										><span>강의 수강도</span><input
											type="number"
											min="1"
											max="5"
											bind:value={lectureProgress}
										/></label
									>
									<label
										><span>강의 이해도</span><input
											type="number"
											min="1"
											max="5"
											bind:value={lectureComprehension}
										/></label
									>
									<label
										><span>클리닉 전 암기</span><input
											type="number"
											min="1"
											max="5"
											bind:value={memoryBefore}
										/></label
									>
									<label
										><span>클리닉 후 암기</span><input
											type="number"
											min="1"
											max="5"
											bind:value={memoryAfter}
										/></label
									>
								</div>
								{#if scoreMode === 'auto'}
									<div class="assessment-entry">
										<strong>학습 내용 및 암기 정도 평가</strong>
										{#if assessmentLocked && lockedAssessmentRows().length}
											<p>이미 생성된 항목명은 유지하고 점수만 수정합니다.</p>
											<div class="fixed-scores">
												{#each lockedAssessmentRows() as item, index}<label
														><span>{item.name}</span><input
															type="number"
															min="1"
															max="5"
															value={item.score}
															onchange={(event) =>
																updateLockedScore(index, Number(event.currentTarget.value))}
														/></label
													>{/each}
											</div>
										{:else}
											<p>
												첫 생성에만 사용됩니다. 비워두면 AI가 항목을 만들고, 입력하면 그 항목과
												점수를 그대로 기준으로 사용합니다.
											</p>
											<textarea
												bind:value={assessmentCsv}
												placeholder="광합성 명반응,4&#10;캘빈 회로,3"
											></textarea>
										{/if}
									</div>
								{/if}
							</section>
						</div>
					{:else}
						<div class="quick-report-actions">
							<div class="quick-score-controls">
								<strong>단원별 점수</strong>
								{#if scoreMode === 'auto'}<label class="final-assessment">
										<small>한 줄에 `항목,점수`로 입력하세요.</small>
										<textarea
											bind:value={assessmentCsv}
											placeholder="광합성 명반응,4&#10;캘빈 회로,3"
										></textarea>
									</label>{:else}<button class="ghost-button" onclick={() => (scoreMode = 'auto')}
										>단원별 점수 입력</button
									>{/if}
							</div>
							<button
								class="native-kakao-button"
								onclick={sendToNativeKakao}
								disabled={!nativeKakaoAvailable ||
									nativeKakaoBusy ||
									scheduleBusy ||
									kakaoBusy ||
									pdfBusy ||
										(!!scheduledDelivery &&
										['generating', 'sending'].includes(scheduledDelivery.state))}
								>{nativeKakaoBusy
									? '클리닉 리포트 전송 중…'
									: nativeKakaoAvailable
										? '카카오톡으로 받기'
										: nativeKakaoChecked
											? '카카오톡 전송 연결 확인 필요'
											: '카카오톡 연결 확인 중…'}</button
							><small class="share-status" role="status" aria-live="polite"
								>{deliveryNotice || shareStatus}</small
							>
							{#if replacedScheduleNotice}<small class="share-status" role="status">{replacedScheduleNotice}</small>{/if}
						</div>
						<div class="final-columns" class:controls-collapsed={finalControlsCollapsed}>
							<section class="final-controls">
								<div class="final-controls-heading">
									<h3>학습 내용 최종 수정</h3>
									{#if aiResults.length > 0}<label class="saved-generation-picker">
											<span>저장된 AI 생성본</span>
											<select
												bind:value={selectedAiRunId}
												onchange={() => restoreAiGeneration(selectedAiRunId)}
											>
												{#each aiResults as result (result.runId)}<option
														value={String(result.runId)}
													>
														{new Date(result.completedAt ?? Date.now()).toLocaleString('ko-KR')} · {result.model}
													</option>{/each}
											</select>
										</label>{/if}
									<button class="panel-collapse" onclick={() => (finalControlsCollapsed = true)}
										>접기</button
									>
								</div>
								<p>PDF에 들어가기 전에 문장을 한 번 더 고칠 수 있습니다.</p>
								{#each finalParagraphs as paragraph, index}<div class="paragraph-row">
										<textarea bind:value={finalParagraphs[index]}></textarea><button
											aria-label="문단 삭제"
											onclick={() =>
												(finalParagraphs = finalParagraphs.filter((_, i) => i !== index))}>×</button
										>
									</div>{/each}
								<button
									class="ghost-button"
									onclick={() => (finalParagraphs = [...finalParagraphs, ''])}>+ 문단 추가</button
								>
								<label class="problem-note-field">
									<strong>문제풀이 설명</strong>
									<small>입력한 문장은 문제풀이 사진 위에 표시됩니다.</small>
									<textarea
										bind:value={problemSolvingNote}
										placeholder="이해한 내용을 정리할 겸 문제를 풀게 했고 잘 풀어주었습니다."
									></textarea>
								</label>

								<div class="final-buttons">
									<button class="ghost-button" onclick={openRegenerationOptions}
										>새 AI 리포트 다시 생성</button
									>
									<div class="export-group">
										<div class="export-actions">
											<button
												class="ghost-button"
												onclick={preparedShareFiles.length
													? sharePreparedImages
													: prepareKakaoShare}
												disabled={kakaoBusy || nativeKakaoBusy || pdfBusy}
												>{kakaoBusy
													? 'PDF 준비 중…'
													: preparedShareFiles.length
														? 'PDF 공유하기'
														: 'PDF 공유 준비'}</button
											>
										</div>
									</div>
								</div>
							</section>
							<section class="pdf-scroll">
								{#if finalControlsCollapsed}<button
										class="panel-expand"
										onclick={() => (finalControlsCollapsed = false)}>최종 수정 열기</button
									>{/if}
								<article class="pdf-preview">
									<h1>⊙ {report.studentName} 클리닉 리포트</h1>
									<table class="summary-table">
										<tbody>
											<tr
												><th>구분</th><td
													>{report.schoolName}
													{progressStageLabels[report.progressStage]}
													{report.roundLabel}</td
												><th>강의수강도</th><td>{lectureProgress}</td></tr
											>
											<tr
												><th>이름</th><td>{report.studentName}</td><th>강의이해도</th><td
													>{lectureComprehension}</td
												></tr
											>
											<tr
												><th>수업날짜</th><td
													>{new Intl.DateTimeFormat('ko-KR', {
														month: 'numeric',
														day: 'numeric'
													}).format(new Date(report.startTime))}</td
												><th>클리닉 전 암기</th><td>{memoryBefore}</td></tr
											>
											<tr
												><th>시간</th><td
													>{new Intl.DateTimeFormat('ko-KR', {
														hour: '2-digit',
														minute: '2-digit',
														hour12: false
													}).format(new Date(report.startTime))}~{new Intl.DateTimeFormat('ko-KR', {
														hour: '2-digit',
														minute: '2-digit',
														hour12: false
													}).format(new Date(report.endTime))}</td
												><th>클리닉 후 암기</th><td>{memoryAfter}</td></tr
											>
										</tbody>
									</table>
									{#if scoreMode === 'auto' && lockedAssessmentRows().length}<section
											class="report-section assessment-section"
										>
											<h2>학습내용 암기 정도 평가</h2>
											<table>
												<tbody
													><tr
														><th
															>{#each lockedAssessmentRows() as item}<div>
																	{item.name}
																</div>{/each}</th
														><td
															>{#each lockedAssessmentRows() as item}<div>
																	{item.score}
																</div>{/each}</td
														></tr
													></tbody
												>
											</table>
										</section>{/if}
									<section class="report-section learning-section">
										<h2>클리닉 학습 내용, 부족한 점</h2>
										<div>
											{#each finalParagraphs as paragraph}<p>{paragraph}</p>{/each}
										</div>
									</section>
									<section class="report-section image-section">
										<h2>백지 테스트 결과</h2>
										{#if blankTestImages.length}<div class="image-grid">
												{#each blankTestImages as image}<img
														src={image.url}
														alt="백지테스트"
													/>{/each}
											</div>{:else}<p class="not-submitted">
												백지테스트를 제출하지 않았습니다.
											</p>{/if}
									</section>
									{#if problemImages.length || problemSolvingNote.trim()}<section
											class="report-section image-section"
										>
											<h2>문제풀이</h2>
											<div class="image-grid problem-image-grid">
												{#each problemImages as image}<img src={image.url} alt="문제 풀이" />{/each}
												{#if problemSolvingNote.trim()}<p class="problem-note">
														{problemSolvingNote}
													</p>{/if}
											</div>
										</section>{/if}
									{#if includeAppendix}<section class="report-section pdf-appendix">
											<h2>(부록) 이번 단원 학습 내용</h2>
											<p class="appendix-notice">
												제가 개인적으로 수업 내용을 정리했으나 사소한 오류가 있을 수 있습니다.<br
												/>클리닉을 진행하며 학생이 잘 모르는 부분을 형광으로 표시해뒀습니다.
											</p>
											<AuraReportEditor
												initialValue={draftDocument}
												readonly={true}
												{questionChecks}
											/>
										</section>{/if}
								</article>
							</section>
						</div>
					{/if}
				</section>
			{/if}
		</div>
	{/if}
{/snippet}

<style>
	.schedule-panel {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 12px 18px;
		padding: 14px 16px;
		margin-bottom: 12px;
		border: 1px solid #d8e1ed;
		border-radius: 12px;
		background: #f7faff;
	}
	.schedule-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.schedule-actions button {
		min-height: 42px;
		padding: 9px 16px;
		border: 1px solid #bdcbe0;
		border-radius: 8px;
		background: white;
		color: #273d60;
		font-weight: 600;
		cursor: pointer;
	}
	.schedule-actions button.schedule-primary {
		border-color: #285cc5;
		background: #285cc5;
		color: white;
	}
	.schedule-actions button:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}
	.schedule-actions button:focus-visible {
		outline: 3px solid #85aaf4;
		outline-offset: 2px;
	}
	.schedule-status {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 12px;
		color: #52637a;
		font-size: 0.9rem;
	}
	.schedule-status strong {
		color: #263c5b;
	}
	.inline-report-tools {
		margin-top: 12px;
		min-width: 0;
	}
	.note-panel,
	.editor-panel {
		min-width: 0;
	}
	.note-panel :global(input[type='file']) {
		width: 100%;
		min-width: 0;
	}
	.inline-report-tools .generate-input,
	.inline-report-tools .final-controls {
		min-width: 0;
		padding: 12px 0;
		overflow: visible;
	}
	.inline-report-tools .report-modal > header {
		height: auto;
		padding: 12px 0;
		flex-wrap: wrap;
	}
	.inline-report-tools .modal-actions {
		flex-wrap: wrap;
		min-width: 0;
	}
	.inline-report-tools .report-modal {
		position: static;
		width: 100%;
		height: auto;
		max-width: none;
		max-height: none;
		padding: 0;
		border: 0;
		box-shadow: none;
		overflow: visible;
	}
	.inline-report-tools .generate-columns,
	.inline-report-tools .final-columns {
		display: flex;
		flex-direction: column;
		height: auto;
	}
	.inline-report-tools .final-columns {
		flex-direction: column;
	}
	.quick-report-actions {
		margin: 8px 0 14px;
		display: grid;
		align-items: start;
		gap: 8px;
	}
	.quick-score-controls {
		display: grid;
		gap: 5px;
	}
	.quick-score-controls .final-assessment {
		margin-top: 0;
	}
	.inline-report-tools .pdf-scroll {
		overflow: visible;
		max-height: none;
	}
	.quick-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.back {
		display: inline-flex;
		align-items: center;
		text-decoration: none;
	}
	.success-banner {
		margin-bottom: 18px;
		padding: 12px 15px;
		border: 1px solid #b9d2bf;
		border-radius: 9px;
		background: #eff7f0;
		color: #4e6c57;
		font-size: 14px;
	}
	.report-layout {
		display: grid;
		grid-template-columns: minmax(340px, 40%) minmax(0, 1fr);
		gap: 18px;
		align-items: start;
	}
	.report-layout.note-hidden {
		grid-template-columns: minmax(0, 1fr);
	}
	.report-layout.note-hidden .note-panel {
		display: none;
	}
	.editor-header-actions {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.complete-status-button {
		padding: 7px 10px;
		border: 1px solid #b9d2bf;
		border-radius: 8px;
		background: #eef7f0;
		color: #4e6c57;
		font-size: 10px;
		cursor: pointer;
	}
	.page-head-actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 8px;
		flex-wrap: wrap;
	}
	.complete-status-button:disabled {
		opacity: 0.55;
		cursor: wait;
	}
	.note-panel {
		position: static;
		top: 18px;
		padding: 20px;
	}
	.note-heading {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 8px;
	}
	.note-toggle {
		flex: 0 0 auto;
		padding: 6px 9px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: #fff;
		color: var(--pp-muted);
		font-size: 10px;
		cursor: pointer;
	}
	.note-collapsed {
		padding-bottom: 12px;
	}
	.note-panel h2 {
		margin: 6px 0;
	}
	.note-panel p:not(.eyebrow) {
		color: var(--pp-muted);
		font-size: 9px;
		line-height: 1.6;
	}
	.note-panel textarea {
		width: 100%;
		min-height: 190px;
		margin-top: 12px;
		padding: 11px;
		resize: vertical;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
	}
	.highlight-guide {
		margin-top: 14px;
		padding: 11px;
		display: grid;
		grid-template-columns: 8px 1fr;
		gap: 5px 8px;
		border-radius: 8px;
		background: #fff8d7;
		font-size: 8px;
	}
	.highlight-guide span {
		width: 8px;
		height: 8px;
		border-radius: 2px;
		background: #f59e7a;
	}
	.highlight-guide small {
		grid-column: 2;
		color: var(--pp-muted);
	}
	.note-shortcuts {
		margin-top: 12px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		background: #fff;
	}
	.note-shortcuts summary {
		padding: 10px;
		font-size: 9px;
		font-weight: 800;
		cursor: pointer;
	}
	.note-shortcuts > div {
		padding: 0 10px 10px;
		display: grid;
		gap: 6px;
	}
	.note-shortcuts span {
		display: flex;
		justify-content: space-between;
		gap: 7px;
		font-size: 8px;
	}
	.note-shortcuts kbd {
		font:
			7px ui-monospace,
			monospace;
	}
	.editor-panel :global(.shortcut-guide) {
		display: none;
	}
	.editor-panel {
		min-width: 0;
		overflow: visible;
	}
	.editor-panel > header,
	.editor-panel > footer {
		padding: 18px 20px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.editor-panel > header {
		border-bottom: 1px solid var(--pp-line);
	}
	.editor-panel > footer {
		border-top: 1px solid var(--pp-line);
	}
	.editor-panel > footer {
		justify-content: flex-end;
	}
	.template-button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 40px;
		padding: 8px 14px;
		border: 1px solid #b7b9b4;
		border-radius: 7px;
		background: #fff;
		color: #303330;
		font: inherit;
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
	}
	.template-button:disabled {
		opacity: 0.5;
		cursor: wait;
	}
	.template-confirm {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		padding: 12px 20px;
		border-top: 1px solid var(--pp-line);
	}
	.unit-template-tools {
		width: 100%;
		margin-right: auto;
		padding: 14px 16px;
		border: 1px solid var(--pp-line);
		border-radius: 10px;
	}
	.unit-template-tools > p {
		margin: 4px 0 10px;
		color: var(--pp-muted);
		font-size: 13px;
	}
	.unit-template-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.unit-template-actions input,
	.unit-template-actions select {
		min-height: 38px;
		padding: 7px 10px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
		background: var(--pp-surface);
		color: inherit;
		font: inherit;
	}
	.unit-template-actions input {
		flex: 1 1 150px;
	}
	.unit-template-actions select {
		flex: 1 1 190px;
	}
	.unit-template-tools small {
		display: block;
		margin-top: 8px;
		color: var(--pp-muted);
	}
	.template-cancel {
		min-height: 40px;
		padding: 8px 12px;
		border: 1px solid transparent;
		border-radius: 7px;
		background: transparent;
		color: var(--pp-muted);
		font: inherit;
		cursor: pointer;
	}
	.editor-wrap {
		padding: 14px 20px 20px;
	}
	.question-check-guide {
		color: var(--pp-muted);
		font-size: 8px;
	}
	.student-switcher {
		margin-bottom: 18px;
		padding: 12px 16px;
		display: flex;
		justify-content: space-between;
		gap: 14px;
	}
	.student-switcher strong,
	.student-switcher small {
		display: block;
	}
	.student-switcher small {
		margin-top: 3px;
		color: var(--pp-muted);
		font-size: 8px;
	}
	.student-tabs {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	.student-tabs button {
		padding: 7px 10px;
		border: 1px solid var(--pp-line);
		border-radius: 999px;
		background: #fff;
		cursor: pointer;
	}
	.student-tabs button.active {
		background: var(--pp-sage-dark);
		color: #fff;
	}
	.student-tabs span {
		margin-left: 5px;
		opacity: 0.7;
		font-size: 7px;
	}
	.modal-backdrop {
		position: fixed;
		z-index: 100;
		inset: 0;
		padding: 18px;
		display: grid;
		place-items: center;
		background: rgb(22 29 27 / 48%);
		overflow: auto;
		touch-action: pan-y;
	}
	.report-modal {
		position: fixed;
		inset: 8px;
		width: calc(100vw - 16px);
		height: calc(100dvh - 16px);
		max-height: calc(100dvh - 16px);
		max-width: 1760px;
		margin: auto;
		padding: 0;
		border: 0;
		border-radius: 16px;
		overflow: hidden;
		background: #fff;
		box-shadow: 0 24px 70px rgb(0 0 0 / 25%);
	}
	.report-modal > header {
		position: sticky;
		top: 0;
		z-index: 10;
		height: 72px;
		padding: 14px 20px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		border-bottom: 1px solid var(--pp-line);
	}
	.report-modal h2 {
		margin: 3px 0 0;
	}
	.modal-actions {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.mobile-modal-close {
		display: none;
	}
	.modal-actions select,
	.score-mode select {
		padding: 8px 10px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: #fff;
	}
	.generate-columns,
	.final-columns {
		height: calc(100% - 72px);
		min-height: 0;
		display: grid;
		grid-template-columns: minmax(430px, 38%) minmax(0, 62%);
	}
	.generate-columns {
		grid-template-columns: minmax(0, 1fr);
	}
	.final-controls-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}
	.final-controls-heading h3 {
		margin: 0;
	}
	.panel-collapse,
	.panel-expand {
		padding: 7px 10px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: #fff;
		color: var(--pp-ink);
		font-size: 10px;
		cursor: pointer;
	}
	.panel-expand {
		position: sticky;
		top: 14px;
		z-index: 2;
		margin: 0 0 10px auto;
		display: block;
	}
	.final-columns.controls-collapsed {
		grid-template-columns: 0 minmax(0, 100%);
	}
	.final-columns.controls-collapsed .final-controls {
		display: none;
	}
	.generate-input,
	.source-compare,
	.final-controls,
	.pdf-scroll {
		min-height: 0;
		overflow-y: auto;
	}
	.generate-input,
	.final-controls {
		padding: 22px;
		border-right: 1px solid var(--pp-line);
	}
	.source-compare {
		padding: 16px;
		background: #faf9f5;
	}
	.source-compare :global(.text-editor-toolbar) {
		display: none;
	}
	.source-compare :global(.text-editor-surface) {
		height: auto;
		min-height: calc(100vh - 150px);
		overflow: visible;
	}
	.pane-title {
		margin-bottom: 10px;
		display: flex;
		justify-content: space-between;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.student-summary {
		padding: 14px;
		display: flex;
		justify-content: space-between;
		border-radius: 10px;
		background: #f3f5f1;
	}
	.student-summary span {
		color: var(--pp-muted);
		font-size: 9px;
	}
	.score-mode {
		margin: 18px 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		font-size: 10px;
		font-weight: 700;
	}
	.generation-rules {
		padding: 12px;
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 7px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		background: #fbfaf6;
		font-size: 9px;
	}
	.generation-rules > strong,
	.generation-rules > small,
	.generation-rules .question-rule {
		grid-column: 1 / -1;
	}
	.generation-rules > small {
		color: var(--pp-muted);
		font-size: 8px;
	}
	.generation-rules label {
		display: grid;
		gap: 4px;
	}
	.generation-rules select {
		width: 100%;
		padding: 6px;
		border: 1px solid var(--pp-line);
		border-radius: 6px;
		background: #fff;
	}
	.generation-rules .question-rule {
		display: flex;
		align-items: center;
		gap: 6px;
		padding-top: 4px;
	}
	.rating-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 8px;
	}
	.rating-grid label {
		padding: 10px;
		display: grid;
		grid-template-columns: 1fr 54px;
		align-items: center;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		font-size: 9px;
	}
	.rating-grid input,
	.fixed-scores input {
		width: 100%;
		padding: 7px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
		text-align: center;
	}
	.assessment-entry {
		margin-top: 20px;
	}
	.assessment-entry > p {
		color: var(--pp-muted);
		font-size: 8px;
		line-height: 1.6;
	}
	.locked-none {
		margin-top: 18px;
		padding: 12px;
		border-radius: 9px;
		background: #f3f5f1;
		color: var(--pp-muted);
		font-size: 9px;
		line-height: 1.6;
	}
	.assessment-entry textarea {
		width: 100%;
		min-height: 180px;
		padding: 12px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		resize: vertical;
		font:
			11px ui-monospace,
			monospace;
	}
	.fixed-scores {
		margin-top: 10px;
		display: grid;
		gap: 7px;
	}
	.fixed-scores label {
		display: grid;
		grid-template-columns: 1fr 62px;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		font-size: 9px;
	}
	.final-controls h3 {
		margin: 0;
	}
	.final-controls > p {
		color: var(--pp-muted);
		font-size: 9px;
	}
	.paragraph-row {
		margin: 8px 0;
		display: grid;
		grid-template-columns: 1fr 34px;
		gap: 6px;
	}
	.paragraph-row textarea {
		min-height: 88px;
		padding: 10px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		resize: vertical;
		line-height: 1.7;
	}
	.paragraph-row button {
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: #fff;
		cursor: pointer;
	}
	.final-assessment {
		margin-top: 20px;
		display: grid;
		gap: 6px;
	}
	.final-assessment small {
		color: var(--pp-muted);
		font-size: 8px;
	}
	.final-assessment textarea {
		min-height: 150px;
		padding: 11px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		resize: vertical;
		font:
			14px ui-monospace,
			monospace;
		line-height: 1.6;
	}
	.problem-note-field {
		margin-top: 16px;
		display: grid;
		gap: 6px;
	}
	.problem-note-field small {
		color: var(--pp-muted);
		font-size: 8px;
	}
	.problem-note-field textarea {
		min-height: 90px;
		padding: 10px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		resize: vertical;
		line-height: 1.6;
	}
	.attachment-fields {
		margin-top: 22px;
		display: grid;
		gap: 10px;
	}
	.attachment-fields label {
		padding: 12px;
		display: grid;
		gap: 5px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
	}
	.attachment-fields small {
		color: var(--pp-muted);
		font-size: 8px;
	}
	.paste-image-button {
		justify-self: start;
		padding: 7px 9px;
		border: 1px dashed var(--pp-line);
		border-radius: 7px;
		background: #fff;
		font-size: 10px;
		cursor: pointer;
	}
	.attachment-list {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
		gap: 8px;
	}
	.attachment-list figure {
		position: relative;
		margin: 0;
		padding: 5px;
		border: 1px solid var(--pp-line);
		border-radius: 10px;
		background: #fff;
	}
	.attachment-list img {
		display: block;
		width: 100%;
		aspect-ratio: 1;
		border-radius: 7px;
		object-fit: cover;
	}
	.attachment-list figcaption {
		padding: 5px 2px 1px;
		overflow: hidden;
		color: var(--pp-muted);
		font-size: 8px;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.attachment-list button {
		position: absolute;
		top: 9px;
		right: 9px;
		width: 28px;
		height: 28px;
		border: 0;
		border-radius: 50%;
		background: rgb(24 30 28 / 78%);
		color: #fff;
		font-size: 18px;
		line-height: 1;
		cursor: pointer;
	}
	.attachment-notice {
		margin: 0;
		padding: 8px 10px;
		border-radius: 8px;
		background: #eef4f0;
		color: #526a60;
		font-size: 10px;
		line-height: 1.5;
	}
	.attachment-notice.attachment-error {
		background: #fff0eb;
		color: #a34e38;
	}
	.final-buttons {
		margin-top: 20px;
		display: flex;
		justify-content: space-between;
		gap: 12px;
		padding-bottom: 36px;
		flex-wrap: wrap;
	}
	.export-actions {
		display: flex;
		gap: 8px;
	}
	.native-kakao-button {
		padding: 9px 13px;
		border: 1px solid #d7bd00;
		border-radius: 8px;
		background: #fee500;
		color: #191919;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}
	.native-kakao-button:disabled {
		opacity: 0.58;
		cursor: wait;
	}
	.export-group {
		display: grid;
		justify-items: end;
		gap: 6px;
	}
	.share-status {
		color: var(--pp-muted);
		font-size: 10px;
	}
	.pdf-scroll {
		padding: 24px;
		background: #e9e9e6;
		overflow-x: auto;
	}
	.pdf-preview {
		box-sizing: border-box;
		width: 100%;
		min-height: 0;
		margin: 0 auto;
		padding: 24px;
		background: #fff;
		color: #171717;
		font-family: Arial, 'Noto Sans KR', sans-serif;
		box-shadow: 0 3px 18px rgb(0 0 0 / 12%);
	}
	.pdf-preview,
	.pdf-preview :global(*) {
		color: #111 !important;
	}
	.pdf-preview h1 {
		margin: 0 0 18px;
		font-size: 32px;
		font-weight: 500;
	}
	.pdf-preview .summary-table,
	.pdf-preview .report-section {
		margin: 0;
	}
	.pdf-preview h2 {
		margin: 0;
		padding: 8px 9px;
		border: 1px solid #9a9a9a;
		border-top: 0;
		font-size: 16px;
		font-weight: 500;
	}
	.pdf-preview p {
		margin: 0 0 5px;
		font-size: 13px;
		line-height: 1.7;
		white-space: pre-wrap;
	}
	.pdf-preview table {
		width: 100%;
		border-collapse: collapse;
	}
	.pdf-preview th,
	.pdf-preview td {
		padding: 7px 8px;
		border: 1px solid #9a9a9a;
		font-size: 13px;
		font-weight: 400;
	}
	.summary-table th:nth-child(1) {
		width: 90px;
	}
	.summary-table th:nth-child(3) {
		width: 150px;
	}
	.summary-table td:nth-child(4) {
		width: 42px;
		text-align: center;
	}
	.assessment-section table th {
		text-align: left;
	}
	.assessment-section table td {
		width: 48px;
		text-align: center;
	}
	.assessment-section table div {
		min-height: 21px;
		line-height: 1.55;
	}
	.learning-section > div,
	.image-section > .image-grid,
	.pdf-appendix > .appendix-notice,
	.image-section > .not-submitted {
		padding: 9px;
		border: 1px solid #9a9a9a;
		border-top: 0;
	}
	.pdf-preview img {
		display: block;
		max-width: 100%;
		margin: 12px auto;
	}
	.pdf-appendix :global(.text-editor-toolbar) {
		display: none;
	}
	.pdf-appendix :global(.text-editor-card) {
		padding: 9px;
		border: 1px solid #9a9a9a;
		border-top: 0;
		border-radius: 0;
		box-shadow: none;
	}
	.pdf-appendix :global(.text-editor-surface) {
		height: auto;
		min-height: 0;
		padding: 4px 10px;
		overflow: visible;
		font-size: 12px;
	}
	.saved-generation-picker {
		display: flex;
		align-items: center;
		gap: 7px;
		font-size: 12px;
	}
	.saved-generation-picker select {
		max-width: 260px;
		padding: 6px 8px;
		border: 1px solid #c9c9c4;
		border-radius: 7px;
		background: #fff;
		color: #171717;
	}
	.image-grid {
		display: grid;
		grid-template-columns: 1fr;
		align-items: start;
		gap: 4px;
	}
	.image-grid img {
		width: 100%;
		height: auto;
		object-fit: contain;
		margin: 0;
		break-inside: avoid;
		page-break-inside: avoid;
	}
	.problem-image-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		align-items: start;
		gap: 8px;
	}
	.problem-image-grid img {
		width: 100%;
		max-height: 420px;
		height: auto;
		object-fit: contain;
	}
	.problem-note {
		grid-column: 1 / -1;
		padding: 2px 0 8px;
	}
	.not-submitted {
		padding: 30px;
		text-align: center;
		color: #8a928e;
		background: #f6f6f3;
	}
	@media (max-width: 850px) {
		.editor-panel > header {
			flex-wrap: wrap;
		}
		.editor-header-actions {
			width: 100%;
			flex-wrap: wrap;
		}
		.editor-header-actions > button {
			flex: 1 1 auto;
			white-space: nowrap;
		}
		.editor-header-actions .status-pill {
			margin-left: auto;
			white-space: nowrap;
		}
		.mobile-modal-close {
			position: absolute;
			top: 10px;
			right: 10px;
			z-index: 5;
			display: grid;
			width: 40px;
			height: 40px;
			place-items: center;
			border: 1px solid var(--pp-line);
			border-radius: 10px;
			background: #fff;
			color: #172023;
			font-size: 24px;
			line-height: 1;
		}
		.report-modal > header {
			padding-right: 58px;
		}
		.report-layout {
			grid-template-columns: minmax(0, 1fr);
		}
		.note-panel {
			position: static;
		}
		.generate-columns,
		.final-columns {
			grid-template-columns: 1fr;
		}
		.report-modal {
			inset: 0;
			width: 100vw;
			height: 100dvh;
			max-height: none;
			border-radius: 0;
		}
		.modal-backdrop {
			padding: 0;
		}
		.source-compare,
		.pdf-scroll {
			display: none;
		}
		.generate-input,
		.final-controls {
			border-right: 0;
			padding-bottom: 140px;
			-webkit-overflow-scrolling: touch;
			overscroll-behavior: contain;
		}
		.generate-columns,
		.final-columns {
			height: calc(100dvh - 72px);
			min-height: 0;
		}
		.final-buttons {
			flex-direction: column;
			align-items: stretch;
		}
		.export-actions {
			flex-wrap: wrap;
		}
		.modal-actions select {
			max-width: 160px;
		}
	}
</style>
