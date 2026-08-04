<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AuraReportEditor from '$lib/personal-project/aura/components/AuraReportEditor.svelte';
	import { createDocument, normalizeDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
import { personalApi, type ReportAttachment } from '$lib/personal-project/shared/api';
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
	let message = $state('');
	let error = $state('');

	let aiModels = $state<AiReportModel[]>([]);
	let selectedModel = $state('');
	let aiResults = $state<AiReportResult[]>([]);
	let aiGenerating = $state(false);
	let scoreMode = $state<'auto' | 'none'>('auto');
	let generatedReport = $state<AiReportResult['output'] | null>(null);
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
	let pdfPreview = $state<HTMLElement>();
	let pdfBusy = $state(false);
	let kakaoBusy = $state(false);
	let preparedShareFiles = $state<File[]>([]);
	let shareStatus = $state('');
	let finalControlsCollapsed = $state(false);
	let loadingTargetId = 0;

	function hasAppendixContent(document: EditorDocument) {
		return document.blocks.some((block) => {
			if (block.type === 'table') {
				return block.rows.some((row) =>
					row.some((cell) => cell.blocks.some((child) => child.children.some((chunk) => chunk.text.trim())))
				);
			}
			return block.children.some((chunk) => chunk.text.trim());
		});
	}

	async function reportPageFiles() {
		if (!pdfPreview) return [];
		const { captureReport } = await import('$lib/personal-project/aura/reportExport.client');
		const source = await captureReport(pdfPreview);
		const pageHeight = Math.round((source.width * 297) / 210);
		const files: File[] = [];
		for (let top = 0, pageNumber = 1; top < source.height; top += pageHeight, pageNumber++) {
			const pageCanvas = document.createElement('canvas');
			pageCanvas.width = source.width;
			pageCanvas.height = pageHeight;
			const context = pageCanvas.getContext('2d');
			if (!context) continue;
			context.fillStyle = '#ffffff';
			context.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
			context.drawImage(
				source,
				0,
				top,
				source.width,
				Math.min(pageHeight, source.height - top),
				0,
				0,
				source.width,
				Math.min(pageHeight, source.height - top)
			);
			const blob = await new Promise<Blob>((resolve, reject) =>
				pageCanvas.toBlob(
					(value) => (value ? resolve(value) : reject(new Error('리포트 이미지를 만들지 못했습니다.'))),
					'image/jpeg',
					0.9
				)
			);
			files.push(new File([blob], `clinic-report-${pageNumber}.jpg`, { type: 'image/jpeg' }));
		}
		return files;
	}

	let assessmentLocked = $derived(aiResults.length > 0 || Boolean(report?.generatedReportJson));
	let includeAppendix = $derived(hasAppendixContent(draftDocument));

	async function load(targetId: number) {
		loadingTargetId = targetId;
		try {
			const [nextReport, attachments] = await Promise.all([
				personalApi.targetReport(targetId), personalApi.targetReportAttachments(targetId)
			]);
			if (loadingTargetId !== targetId) return;
			report = nextReport;
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
			if (generatedReport && !generatedReport.assessment) scoreMode = 'none';
			aiModel = nextReport.aiModel;
			blankTestImages = attachments.filter((item) => item.kind === 'blank_test').map((item) => ({ ...item, url: personalApi.targetReportAttachmentUrl(item.id) }));
			problemImages = attachments.filter((item) => item.kind === 'problem_solving').map((item) => ({ ...item, url: personalApi.targetReportAttachmentUrl(item.id) }));
			await loadAi(targetId);
			if (page.url.searchParams.get('pdf') === '1') {
				modalStage = generatedReport ? 'final' : 'generate';
			}
		} catch (cause) {
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

	async function loadAi(targetId: number) {
		const [options, saved] = await Promise.all([
			personalApi.aiReportModels(),
			personalApi.aiReportResults(targetId)
		]);
		if (loadingTargetId !== targetId) return;
		aiModels = options.models;
		selectedModel = aiModels.some((item) => item.id === aiModel)
			? (aiModel as string)
			: options.defaultModel;
		aiResults = saved.results;
		if (!generatedReport && saved.results[0]) {
			generatedReport = saved.results[0].output;
			aiModel = saved.results[0].model;
			finalParagraphs = [...generatedReport.learningContent.paragraphs];
			problemSolvingNote = generatedReport.problemSolvingNote ?? '';
			assessmentCsv = (generatedReport.assessment?.items ?? [])
				.map((item) => `${item.name},${item.score}`)
				.join('\n');
		}
		if (
			!generatedReport?.assessment &&
			saved.results.length &&
			!saved.results[0].output.assessment
		) {
			scoreMode = 'none';
		}
	}

	async function save(submit = false, silent = false) {
		if (!report) return false;
		saving = true;
		if (!silent) {
			message = '';
			error = '';
		}
		try {
			const assessment = parseAssessmentCsv();
			draftDocument = editor?.getJSON() ?? draftDocument;
			report = await personalApi.updateTargetReport(report.id, {
				content_json: draftDocument,
				source_notes: sourceNotes,
				question_checks: questionChecks,
				lecture_progress: lectureProgress,
				lecture_comprehension: lectureComprehension,
				memory_before: memoryBefore,
				memory_after: memoryAfter,
				assessment_json: assessment,
				generated_report_json: generatedReport,
				ai_model: aiModel,
				status: submit ? 'ready' : report.status === 'submitted' ? 'submitted' : 'draft'
			});
			if (submit) report = await personalApi.submitTargetReport(report.id);
			if (!silent) message = submit ? 'PDF 생성용 리포트를 확정했습니다.' : '임시저장했습니다.';
			return true;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '리포트를 저장하지 못했습니다.';
			return false;
		} finally {
			saving = false;
		}
	}

	async function openGenerateModal() {
		if (!report || saving) return;
		draftDocument = editor?.getJSON() ?? draftDocument;
		if (report.status !== 'submitted' && !(await save(false, true))) return;
		finalParagraphs = [...(generatedReport?.learningContent.paragraphs ?? finalParagraphs)];
		modalStage = generatedReport ? 'final' : 'generate';
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
		modalStage = 'closed';
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
		if (!(await save(false, true))) return;
		aiGenerating = true;
		error = '';
		try {
			const response = await personalApi.generateAiReports(report.targetId, {
				model: selectedModel,
				score_mode: scoreMode,
				assessment_items: assessment.items,
				force
			});
			const result = response.results[0];
			if (!result) throw new Error(response.errors[0]?.message ?? 'AI 결과가 없습니다.');
			aiResults = response.results;
			generatedReport = result.output;
			aiModel = result.model;
			assessmentCsv = (result.output.assessment?.items ?? [])
				.map((item) => `${item.name},${item.score}`)
				.join('\n');
			finalParagraphs = [...result.output.learningContent.paragraphs];
			problemSolvingNote = result.output.problemSolvingNote ?? problemSolvingNote;
			message = result.reused
				? '동일한 입력의 저장된 AI 결과를 불러왔습니다.'
				: 'AI 리포트를 생성했습니다.';
			modalStage = 'final';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'AI 리포트를 생성하지 못했습니다.';
		} finally {
			aiGenerating = false;
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
			/\.(heic|heif)$/i.test(file.name) || /image\/(heic|heif|heic-sequence|heif-sequence)/i.test(file.type);
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
				throw new Error(`HEIC 변환 실패: ${cause instanceof Error ? cause.message : '지원하지 않는 파일입니다.'}`);
			}
		}
		if (!file.type.startsWith('image/')) throw new Error('이미지 파일이 아닙니다.');
		return blobToDataUrl(await compressImageBlob(file));
	}

	async function pdfToImageFiles(file: File) {
		const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs');
		pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/legacy/build/pdf.worker.mjs', import.meta.url).toString();
		const pdfDocument = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
		if (pdfDocument.numPages > 20) throw new Error('PDF는 최대 20페이지까지 첨부할 수 있습니다.');
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
			const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value: Blob | null) => value ? resolve(value) : reject(new Error('PDF 이미지 변환에 실패했습니다.')), 'image/jpeg', 0.88));
			files.push(new File([blob], `${file.name.replace(/\.pdf$/i, '')}-${pageNumber}.jpg`, { type: 'image/jpeg' }));
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
				if (file.type === 'application/pdf' || /\.pdf$/i.test(file.name)) sourceFiles.push(...await pdfToImageFiles(file));
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
					report.targetId, kind === 'blank' ? 'blank_test' : 'problem_solving',
					new File([blob], file.name.replace(/\.(heic|heif)$/i, '.jpg') || 'image.jpg', { type: blob.type || 'image/jpeg' })
				);
				added.push({ ...saved, kind: saved.kind as 'blank_test' | 'problem_solving', byteSize: blob.size, createdAt: new Date().toISOString(), url: personalApi.targetReportAttachmentUrl(saved.id) });
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
		if (kind === 'blank') blankTestImages = blankTestImages.filter((_, itemIndex) => itemIndex !== index);
		else problemImages = problemImages.filter((_, itemIndex) => itemIndex !== index);
		preparedShareFiles = [];
		shareStatus = '';
	}

	async function pasteAttachmentImages(event: ClipboardEvent, kind: 'blank' | 'problem') {
		const images = Array.from(event.clipboardData?.files ?? []).filter((file) => file.type.startsWith('image/'));
		if (!images.length) return;
		event.preventDefault();
		const transfer = new DataTransfer();
		images.forEach((image) => transfer.items.add(image));
		await addAttachmentImages(transfer.files, kind);
	}

	async function downloadPdf() {
		if (!report || !pdfPreview || pdfBusy) return;
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
			const { captureReport, jsPDF } = await import(
				'$lib/personal-project/aura/reportExport.client'
			);
			const canvas = await captureReport(pdfPreview);
			const pdf = new jsPDF('p', 'mm', 'a4');
			const margin = 10;
			const width = 210 - margin * 2;
			const pageHeight = 297 - margin * 2;
			const height = (canvas.height * width) / canvas.width;
			const image = canvas.toDataURL('image/png');
			let offset = 0;
			while (offset < height) {
				if (offset > 0) pdf.addPage();
				pdf.addImage(image, 'PNG', margin, margin - offset, width, height);
				const footerCanvas = globalThis.document.createElement('canvas');
				footerCanvas.width = 600;
				footerCanvas.height = 50;
				const footerContext = footerCanvas.getContext('2d');
				if (footerContext) {
					footerContext.fillStyle = '#ffffff';
					footerContext.fillRect(0, 0, 600, 50);
					footerContext.fillStyle = '#222222';
					footerContext.font = '20px sans-serif';
					footerContext.textAlign = 'center';
					footerContext.fillText(
						`아우라 클리닉 페이지 ${Math.floor(offset / pageHeight) + 1}`,
						300,
						31
					);
					pdf.addImage(footerCanvas.toDataURL('image/png'), 'PNG', 70, 288, 70, 6);
				}
				offset += pageHeight;
			}
			const safeName = `${report.schoolName}_${report.roundLabel}_${report.studentName}`.replace(
				/[\\/:*?"<>|]/g,
				'_'
			);
			pdf.save(`${safeName}_클리닉리포트.pdf`);
			message = 'PDF 다운로드를 시작했습니다.';
			modalStage = 'closed';
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
		shareStatus = '리포트를 이미지 묶음으로 만드는 중입니다…';
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
			const pageFiles = await reportPageFiles();
			if (!pageFiles.length) throw new Error('공유할 리포트 이미지가 없습니다.');
			const shareData: ShareData = { files: pageFiles };
			if (!navigator.share || !navigator.canShare?.(shareData)) {
				throw new Error(
					'이 브라우저는 이미지 묶음 공유를 지원하지 않습니다. 모바일 Chrome 또는 Safari에서 열어주세요.'
				);
			}
			preparedShareFiles = pageFiles;
			shareStatus = `이미지 ${pageFiles.length}장 준비 완료 — 아래 버튼을 한 번 더 눌러주세요.`;
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
				message = `리포트 이미지 ${files.length}장을 묶음 공유했습니다.`;
				preparedShareFiles = [];
				shareStatus = '';
				modalStage = 'closed';
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

	async function switchStudent(targetId: number) {
		if (!report || targetId === report.targetId || saving) return;
		if (report.status !== 'submitted' && !(await save(false, true))) return;
		await goto(`/personal-project/aura/reports/${targetId}`, {
			replaceState: true,
			noScroll: true,
			keepFocus: true
		});
	}

	async function saveAsTemplate() {
		if (
			!report ||
			!confirm(`${report.schoolName} ${report.roundLabel}의 새 기본 양식으로 저장할까요?`)
		)
			return;
		saving = true;
		try {
			draftDocument = editor?.getJSON() ?? draftDocument;
			const result = await personalApi.saveRoundTemplate(
				report.schoolId,
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
		if (targetId && targetId !== report?.targetId) void load(targetId);
	});
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Student report</p>
		<h1>{report?.studentName ?? '리포트 불러오는 중'}</h1>
		<p>
			{report
				? `${report.schoolName} · ${report.roundLabel} · 기본 양식 ${report.templateVersion ? `v${report.templateVersion}` : '회차별 결합'}`
				: '잠시만 기다려주세요.'}
		</p>
	</div>
	<a
		class="ghost-button back"
		href={report
			? `/personal-project/aura/schools/${report.schoolId}`
			: '/personal-project/aura/schools'}>← 회차 목록</a
	>
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
					disabled={saving}
				>
					{target.studentName}<span
						>{target.status === 'submitted'
							? '완료'
							: target.status === 'unwritten'
								? '미작성'
								: '작성 중'}</span
					>
				</button>
			{/each}
		</div>
	</nav>

	<div class="report-layout">
		<aside class="card note-panel">
			<p class="eyebrow">Quick notes</p>
			<h2>관찰 메모</h2>
			<p>학생에게만 해당하는 메모입니다. 기본 양식에는 자동 반영되지 않습니다.</p>
			<textarea bind:value={sourceNotes} placeholder="발음, 태도, 다음 회차에서 확인할 점…"
			></textarea>
			<div class="highlight-guide">
				<span></span><strong>형광 표시 부분을 AI가 부족한 내용으로 읽습니다.</strong>
				<small>Ctrl/Cmd+Alt+1 살구 · +2 노랑 · +3 주황 · +H 최근 색</small>
			</div>
			<details class="note-shortcuts">
				<summary>에디터 단축키 보기</summary>
				<div>
					<span><kbd>Ctrl/Cmd+B</kbd> 굵게</span>
					<span><kbd>Ctrl/Cmd+Z</kbd> 실행 취소</span>
					<span><kbd>Ctrl/Cmd+Shift+Z</kbd> 다시 실행</span>
					<span><kbd>Ctrl/Cmd+Alt+Q</kbd> 물어봤음</span>
					<span><kbd>Ctrl/Cmd+Alt+H</kbd> 최근 형광색</span>
					<span><kbd>Ctrl/Cmd+Alt+1/2/3</kbd> 살구/노랑/주황</span>
					<span><kbd>Tab / Shift+Tab</kbd> 들여쓰기/내어쓰기</span>
				</div>
			</details>
		</aside>

		<section class="card editor-panel">
			<header>
				<div>
					<p class="eyebrow">Report editor</p>
					<h2>{report.studentName} 리포트</h2>
				</div>
				<span class={`status-pill ${report.status}`}
					>{report.status === 'submitted' ? '제출 완료' : '작성 중'}</span
				>
			</header>
			<div class="editor-wrap">
				<p class="question-check-guide">
					Ctrl/Cmd+Alt+Q로 선택한 부분을 ‘물어봤음’으로 저장합니다.
				</p>
				<AuraReportEditor
					bind:this={editor}
					initialValue={initialDocument}
					readonly={false}
					placeholder="회차 기본 양식을 바탕으로 리포트를 작성하세요."
					onchange={(value) => (draftDocument = value)}
					{questionChecks}
					onquestionchange={(blockId, checked) => {
						questionChecks = { ...questionChecks, [blockId]: checked };
					}}
				/>
			</div>
			<footer>
				<button
					class="template-button"
					onclick={saveAsTemplate}
					disabled={saving || report.status === 'submitted' || report.roundNumbers.length > 1}
				>
					{report.roundNumbers.length > 1
						? '복수 회차 결합 리포트'
						: '현재 내용을 새 기본 양식으로 저장'}</button
				>
				<div>
					<button class="ghost-button" onclick={() => save(false)} disabled={saving}
						>{report.status === 'submitted' ? '수정 저장' : '임시저장'}</button
					>
					<button class="primary-button" onclick={openGenerateModal} disabled={saving}
						>{report.status === 'submitted' || generatedReport
							? 'PDF 다시 받기'
							: '클리닉 제출'}</button
					>
				</div>
			</footer>
		</section>
	</div>
{/if}

{#if report && modalStage !== 'closed'}
	<div class="modal-backdrop" role="presentation">
		<dialog open class="report-modal" aria-label="클리닉 리포트 생성">
			<button class="mobile-modal-close" onclick={closeReportModal} aria-label="창 닫기">×</button>
			<header>
				<div>
					<p class="eyebrow">Clinic report</p>
					<h2>{modalStage === 'generate' ? 'AI 리포트 생성' : '최종 PDF 편집'}</h2>
				</div>
				<div class="modal-actions">
					{#if modalStage === 'generate'}
						<select bind:value={selectedModel} aria-label="AI 모델 선택">
							{#each aiModels as model}<option value={model.id} disabled={model.available === false}
									>{model.label}{model.available === false ? ' · API 키 필요' : ''}</option
								>{/each}
						</select>
						<button class="primary-button" onclick={() => generateAi(false)} disabled={aiGenerating}
							>{aiGenerating ? '생성 중…' : 'AI 생성하기'}</button
						>
					{/if}
					<button class="ghost-button" onclick={closeReportModal}>닫기</button>
				</div>
			</header>

			{#if modalStage === 'generate'}
				<div class="generate-columns">
					<section class="generate-input">
						<div class="student-summary">
							<strong>{report.studentName}</strong><span
								>{report.schoolName} · {report.roundLabel}</span
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
										첫 생성에만 사용됩니다. 비워두면 AI가 항목을 만들고, 입력하면 그 항목과 점수를
										그대로 기준으로 사용합니다.
									</p>
									<textarea bind:value={assessmentCsv} placeholder="광합성 명반응,4&#10;캘빈 회로,3"
									></textarea>
								{/if}
							</div>
						{/if}
						{#if assessmentLocked && lockedAssessmentRows().length === 0}
							<p class="locked-none">
								최초 AI 생성에서 평가 항목을 만들지 않았으므로 이후 생성에서도 학습 내용만 만듭니다.
							</p>
						{/if}
					</section>
					<section class="source-compare">
						<div class="pane-title">
							<strong>내가 작성한 원문</strong><span>형광 표시와 비교</span>
						</div>
						<AuraReportEditor initialValue={draftDocument} readonly={true} {questionChecks} />
					</section>
				</div>
			{:else}
				<div class="final-columns" class:controls-collapsed={finalControlsCollapsed}>
					<section class="final-controls">
						<div class="final-controls-heading"><h3>학습 내용 최종 수정</h3><button class="panel-collapse" onclick={() => (finalControlsCollapsed = true)}>접기</button></div>
						<p>PDF에 들어가기 전에 문장을 한 번 더 고칠 수 있습니다.</p>
						{#each finalParagraphs as paragraph, index}<div class="paragraph-row">
								<textarea bind:value={finalParagraphs[index]}></textarea><button
									aria-label="문단 삭제"
									onclick={() => (finalParagraphs = finalParagraphs.filter((_, i) => i !== index))}
									>×</button
								>
							</div>{/each}
						<button
							class="ghost-button"
							onclick={() => (finalParagraphs = [...finalParagraphs, ''])}>+ 문단 추가</button
						>
						{#if scoreMode === 'auto'}
							<label class="final-assessment">
								<strong>평가 항목·점수 최종 수정</strong>
								<small>한 줄에 `항목,점수`로 입력하세요.</small>
								<textarea bind:value={assessmentCsv} placeholder="광합성 명반응,4&#10;캘빈 회로,3"
								></textarea>
							</label>
						{/if}
						<label class="problem-note-field">
							<strong>문제풀이 설명</strong>
							<small>입력한 문장은 문제풀이 사진 위에 표시됩니다.</small>
							<textarea
								bind:value={problemSolvingNote}
								placeholder="이해한 내용을 정리할 겸 문제를 풀게 했고 잘 풀어주었습니다."
							></textarea>
						</label>
						<div class="attachment-fields">
							{#if attachmentNotice}<p class="attachment-notice" class:attachment-error={attachmentNotice.includes('실패')}>{attachmentNotice}</p>{/if}
							<label
								><strong>백지테스트 사진</strong><small>JPG, PNG, WebP와 아이폰 HEIC/HEIF를 지원합니다.</small
								><input
									type="file"
									accept="image/*,.heic,.heif,application/pdf"
									multiple
									capture="environment"
									onchange={async (event) => {
										await addAttachmentImages(event.currentTarget.files, 'blank');
										event.currentTarget.value = '';
									}}
									disabled={attachmentBusy}
								/></label
			>
							<button type="button" class="paste-image-button" onpaste={(event) => pasteAttachmentImages(event, 'blank')}>복사한 사진 붙여넣기: 이 버튼을 누른 뒤 Ctrl/Cmd+V</button>
							{#if blankTestImages.length}<div class="attachment-list">
									{#each blankTestImages as image, index}<figure><img src={image.url} alt={`백지테스트 ${index + 1}`} /><button aria-label={`백지테스트 ${index + 1} 삭제`} onclick={() => removeAttachmentImage('blank', index)}>×</button><figcaption>백지테스트 {index + 1}</figcaption></figure>{/each}
								</div>{/if}
							<label
								><strong>문제 풀이 사진</strong><small>추가한 사진을 아래에서 확인하고 개별 삭제할 수 있습니다.</small
								><input
									type="file"
									accept="image/*,.heic,.heif,application/pdf"
									multiple
									capture="environment"
									onchange={async (event) => {
										await addAttachmentImages(event.currentTarget.files, 'problem');
										event.currentTarget.value = '';
									}}
									disabled={attachmentBusy}
								/></label
			>
							<button type="button" class="paste-image-button" onpaste={(event) => pasteAttachmentImages(event, 'problem')}>복사한 사진 붙여넣기: 이 버튼을 누른 뒤 Ctrl/Cmd+V</button>
							{#if problemImages.length}<div class="attachment-list">
									{#each problemImages as image, index}<figure><img src={image.url} alt={`문제풀이 ${index + 1}`} /><button aria-label={`문제풀이 ${index + 1} 삭제`} onclick={() => removeAttachmentImage('problem', index)}>×</button><figcaption>문제풀이 {index + 1}</figcaption></figure>{/each}
								</div>{/if}
						</div>
						<div class="final-buttons">
							<button class="ghost-button" onclick={() => (modalStage = 'generate')}>이전</button
							><div class="export-group">
								{#if shareStatus}<small class="share-status">{shareStatus}</small>{/if}
							<div class="export-actions"><button class="ghost-button" onclick={() => save(true)} disabled={saving || report?.status === 'submitted'}>{report?.status === 'submitted' ? '작성 완료됨' : '작성 완료 및 임시 사진 정리'}</button><button class="ghost-button" onclick={preparedShareFiles.length ? sharePreparedImages : prepareKakaoShare} disabled={kakaoBusy || pdfBusy}
				>{kakaoBusy ? '이미지 묶음 만드는 중…' : preparedShareFiles.length ? '카카오톡 선택하기' : '카카오톡 이미지 묶음 준비'}</button
							><button class="primary-button" onclick={downloadPdf} disabled={pdfBusy || kakaoBusy}
								>{pdfBusy ? 'PDF 만드는 중…' : 'PDF 저장 및 다운로드'}</button
							></div></div>
						</div>
					</section>
					<section class="pdf-scroll">
						{#if finalControlsCollapsed}<button class="panel-expand" onclick={() => (finalControlsCollapsed = false)}>최종 수정 열기</button>{/if}
						<article class="pdf-preview" bind:this={pdfPreview}>
							<h1>⊙ {report.studentName} 클리닉 리포트</h1>
							<table class="summary-table">
								<tbody>
									<tr
										><th>구분</th><td>{report.schoolName} {report.roundLabel}</td><th>강의수강도</th
										><td>{lectureProgress}</td></tr
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
													>{#each lockedAssessmentRows() as item}<div>{item.name}</div>{/each}</th
												><td
													>{#each lockedAssessmentRows() as item}<div>{item.score}</div>{/each}</td
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
										{#each blankTestImages as image}<img src={image.url} alt="백지테스트" />{/each}
									</div>{:else}<p class="not-submitted">백지테스트를 제출하지 않았습니다.</p>{/if}
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
									<AuraReportEditor initialValue={draftDocument} readonly={true} {questionChecks} />
								</section>{/if}
						</article>
					</section>
				</div>
			{/if}
		</dialog>
	</div>
{/if}

<style>
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
		font-size: 11px;
	}
	.report-layout {
		display: grid;
		grid-template-columns: 250px minmax(0, 1fr);
		gap: 18px;
		align-items: start;
	}
	.note-panel {
		position: sticky;
		top: 18px;
		padding: 20px;
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
	.editor-panel footer > div {
		display: flex;
		gap: 8px;
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
		overflow: hidden;
	}
	.report-modal {
		position: fixed;
		inset: 8px;
		width: calc(100vw - 16px);
		height: calc(100vh - 16px);
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
		display: grid;
		grid-template-columns: minmax(430px, 38%) minmax(0, 62%);
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
		overflow: hidden;
		padding: 0;
		border: 0;
		opacity: 0;
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
	}
	.export-actions {
		display: flex;
		gap: 8px;
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
	}
	.pdf-preview {
		box-sizing: border-box;
		width: 900px;
		min-height: 1273px;
		margin: 0 auto;
		padding: 62px 72px;
		background: #fff;
		color: #171717;
		font-family: Arial, 'Noto Sans KR', sans-serif;
		box-shadow: 0 3px 18px rgb(0 0 0 / 12%);
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
	.image-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 10px;
	}
	.image-grid img {
		width: 100%;
		margin: 0;
	}
	.problem-image-grid {
		display: flex;
		align-items: flex-start;
		flex-wrap: wrap;
	}
	.problem-image-grid img {
		width: 48%;
		max-width: 48%;
		height: auto;
	}
	.problem-note {
		flex-basis: 100%;
		order: 2;
		padding: 2px 0 8px;
	}
	.not-submitted {
		padding: 30px;
		text-align: center;
		color: #8a928e;
		background: #f6f6f3;
	}
	@media (max-width: 850px) {
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
		.modal-actions > .ghost-button {
			display: none;
		}
		.report-layout {
			grid-template-columns: 1fr;
		}
		.note-panel {
			position: static;
		}
		.generate-columns,
		.final-columns {
			grid-template-columns: 1fr;
		}
		.report-modal {
			height: calc(100vh - 16px);
		}
		.modal-backdrop {
			padding: 8px;
		}
		.source-compare,
		.pdf-scroll {
			display: none;
		}
		.generate-input,
		.final-controls {
			border-right: 0;
		}
		.modal-actions select {
			max-width: 160px;
		}
	}
</style>
