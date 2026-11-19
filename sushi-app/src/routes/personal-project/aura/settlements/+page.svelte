<script lang="ts">
	import { onMount } from 'svelte';
	import {
		personalApi,
		settlementRegenerationApproval,
		PersonalApiError
	} from '$lib/personal-project/shared/api';
	import type { SettlementRequestPlan } from '$lib/personal-project/shared/api';
	import type {
		ClinicRound,
		ParentSettlementItem,
		SchoolSettlement
	} from '$lib/personal-project/shared/types';

	const now = new Date();
	let year = $state(now.getFullYear());
	let month = $state(now.getMonth() + 1);
	let data = $state<SchoolSettlement | null>(null);
	let loading = $state(true);
	let generating = $state(false);
	let error = $state('');
	let assistantName = $state('김지후');
	let copiedStudent = $state('');
	let requestPreviewError = $state('');
	let requestBusy = $state(false);
	let blockedRequestTargets = $state<Record<string, boolean>>({});
	let requestResult = $state('');
	let requestFeedbackKey = $state('');
	let sentSettlementTargets = $state<Record<string, boolean>>({});
	let manualDeliveryStates = $state<
		Record<
			string,
			Pick<ParentSettlementItem, 'manualDeliveryConfirmed' | 'manualDeliveryConfirmedAt'>
		>
	>({});
	let manualDeliveryBusyKey = $state('');
	let manualDeliveryLoadError = $state('');
	let manualDeliveryErrorKey = $state('');

	type StudentMessage = {
		key: string;
		schoolName: string;
		studentName: string;
		sessions: string[];
		cumulative: string;
		amount: number;
		message: string;
		parentBillingRequired: boolean;
	};

	const studentMessages = $derived.by(() => {
		const grouped = new Map<
			string,
			{ schoolName: string; studentName: string; items: ClinicRound[] }
		>();
		for (const item of data?.items ?? []) {
			if (item.progressStage === 'accepted' || parentCharge(item) <= 0) continue;
			for (const target of item.targets) {
				const key = `${item.schoolId}:${target.studentName}`;
				const group = grouped.get(key) ?? {
					schoolName: item.schoolName,
					studentName: target.studentName,
					items: []
				};
				group.items.push(item);
				grouped.set(key, group);
			}
		}
		return [...grouped.entries()]
			.map(([key, group]) =>
				buildStudentMessage(key, group.schoolName, group.studentName, group.items)
			)
			.sort((left, right) => left.studentName.localeCompare(right.studentName, 'ko'));
	});

	function durationHours(item: ClinicRound) {
		return Math.max(0, (+new Date(item.endTime) - +new Date(item.startTime)) / 3_600_000);
	}

	function hoursText(hours: number) {
		const minutes = Math.round(hours * 60);
		return minutes % 60
			? `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`
			: `${minutes / 60}시간`;
	}

	function sessionText(item: ClinicRound) {
		const start = new Date(item.startTime);
		const end = new Date(item.endTime);
		const time = new Intl.DateTimeFormat('ko-KR', {
			hour: '2-digit',
			minute: '2-digit',
			hour12: false
		});
		return `${start.getMonth() + 1}월 ${start.getDate()}일 ${time.format(start)}~${time.format(end)}`;
	}

	function parentCharge(item: ClinicRound) {
		const participantCount = Math.max(1, item.targets.length);
		if (item.parentFreeForThreePlus && participantCount >= 3) return 0;
		const hourlyCost =
			item.progressStage === 'deep'
				? 40_000
				: participantCount <= 3
					? 30_000
					: participantCount * 10_000;
		return Math.round((durationHours(item) * hourlyCost) / participantCount);
	}

	function fullStudentName(schoolName: string, studentName: string) {
		const displaySchool = schoolDisplayName(schoolName);
		return studentName.startsWith(displaySchool) ? studentName : `${displaySchool} ${studentName}`;
	}

	function schoolDisplayName(schoolName: string) {
		return schoolName.replace(/^(서울|경기|한성)(\d{2})(.*)$/, '$2$1$3');
	}

	function buildStudentMessage(
		key: string,
		schoolName: string,
		studentName: string,
		entries: ClinicRound[]
	): StudentMessage {
		const items = [...entries].sort(
			(left, right) => +new Date(left.startTime) - +new Date(right.startTime)
		);
		const billedItems = items.filter((item) => parentCharge(item) > 0);
		const hoursByRatio = new Map<string, number>();
		for (const item of billedItems) {
			const ratio = `${Math.max(1, item.targets.length)}:1`;
			hoursByRatio.set(ratio, (hoursByRatio.get(ratio) ?? 0) + durationHours(item));
		}
		const cumulative =
			[...hoursByRatio.entries()]
				.map(([ratio, hours]) => `${ratio} ${hoursText(hours)}`)
				.join(' / ') || '학부모 청구 없음';
		const amount = items.reduce((total, item) => total + parentCharge(item), 0);
		const sessions = items.map(sessionText);
		const fullName = fullStudentName(schoolName, studentName);
		const billedSessions = billedItems.map(sessionText);
		const message = billedItems.length
			? `안녕하세요? ${assistantName.trim() || '김지후'} 조교입니다. ${month}월 클리닉 비용 안내드립니다.\n\n[클리닉 시간]\n${billedSessions.map((value) => `- ${value}`).join('\n')}\n\n[누적 시간]\n${cumulative}\n\n입금해주셔야 할 금액은 ${amount.toLocaleString()}원입니다.\n학생 이름인 ${fullName}(으)로 입금해주시면 감사하겠습니다.\n\n[클리닉 계좌]\n테라스터디 주식회사\n신한은행 140-015-133968`
			: '학부모 청구 없음 (3:1 이상 무료 클리닉 · 비용 학원 부담)';
		return {
			key,
			schoolName: schoolDisplayName(schoolName),
			studentName: fullName,
			sessions,
			cumulative,
			amount,
			message,
			parentBillingRequired: billedItems.length > 0
		};
	}

	let loadGeneration = 0;

	async function load() {
		const selectedYear = year;
		const selectedMonth = month;
		const generation = ++loadGeneration;
		const isCurrentLoad = () =>
			generation === loadGeneration && year === selectedYear && month === selectedMonth;
		loading = true;
		data = null;
		error = '';
		sentSettlementTargets = {};
		manualDeliveryStates = {};
		manualDeliveryBusyKey = '';
		manualDeliveryLoadError = '';
		manualDeliveryErrorKey = '';
		try {
			try {
				const response = await personalApi.settlements(selectedYear, selectedMonth);
				if (!isCurrentLoad()) return;
				data = response;
				if (response.generatedAt) {
					try {
						const parentSettlements = await personalApi.parentSettlements(
							selectedYear,
							selectedMonth
						);
						if (!isCurrentLoad()) return;
						const nextStates: Record<
							string,
							Pick<ParentSettlementItem, 'manualDeliveryConfirmed' | 'manualDeliveryConfirmedAt'>
						> = {};
						for (const item of parentSettlements.items) {
							nextStates[manualDeliveryStateKey(item.studentKey, selectedYear, selectedMonth)] = {
								manualDeliveryConfirmed: item.manualDeliveryConfirmed === true,
								manualDeliveryConfirmedAt: item.manualDeliveryConfirmedAt ?? null
							};
						}
						manualDeliveryStates = nextStates;
					} catch {
						if (!isCurrentLoad()) return;
						manualDeliveryLoadError = '수동 확인 상태를 불러오지 못했습니다.';
					}
				}
			} catch (cause) {
				if (!isCurrentLoad()) return;
				error = cause instanceof Error ? cause.message : '정산을 불러오지 못했습니다.';
			}
		} finally {
			if (isCurrentLoad()) loading = false;
		}
	}

	function moveMonth(step: number) {
		if (generating || requestBusy || manualDeliveryBusyKey) return;
		requestPreviewError = '';
		requestResult = '';
		const date = new Date(year, month - 1 + step, 1);
		year = date.getFullYear();
		month = date.getMonth() + 1;
		load();
	}

	async function download() {
		if (!data?.generatedAt) return;
		const response = await fetch(
			personalApi.settlementExportUrl(year, month, assistantName, data.generatedAt),
			{
				credentials: 'include',
				cache: 'no-store'
			}
		);
		if (!response.ok) {
			error = '엑셀 파일을 만들지 못했습니다.';
			return;
		}
		const url = URL.createObjectURL(await response.blob());
		const anchor = document.createElement('a');
		anchor.href = url;
		const name = assistantName.trim() || '김지후';
		anchor.download = `${name.endsWith('조교') ? name : `${name}조교`} ${month}월 클리닉 정산.xlsx`;
		anchor.click();
		URL.revokeObjectURL(url);
	}

	async function generate() {
		if (generating) return;
		const selectedYear = year;
		const selectedMonth = month;
		generating = true;
		error = '';
		try {
			try {
				await personalApi.generateSettlements(selectedYear, selectedMonth);
			} catch (cause) {
				const approval = settlementRegenerationApproval(cause);
				if (!approval) throw cause;
				try {
					await personalApi.generateSettlements(selectedYear, selectedMonth, approval);
				} catch (retryCause) {
					if (settlementRegenerationApproval(retryCause)) {
						error =
							'정산 내용이 계속 변경되어 생성하지 못했습니다. 버튼을 다시 눌러 최신 내용으로 시도해주세요.';
						return;
					}
					throw retryCause;
				}
			}
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '월별 정산을 생성하지 못했습니다.';
		} finally {
			generating = false;
		}
	}

	function requestBlocked(
		studentKey: string | null = null,
		selectedYear = year,
		selectedMonth = month
	) {
		const prefix = `${selectedYear}:${selectedMonth}:`;
		return studentKey === null
			? !!blockedRequestTargets[`${prefix}all`]
			: !!blockedRequestTargets[`${prefix}${studentKey}`];
	}

	function blockRequestTarget(
		studentKey: string | null,
		selectedYear: number,
		selectedMonth: number
	) {
		blockedRequestTargets[`${selectedYear}:${selectedMonth}:${studentKey ?? 'all'}`] = true;
	}

	function markRequestSent(studentKey: string | null, selectedYear: number, selectedMonth: number) {
		const keys = studentKey
			? [studentKey]
			: studentMessages.filter((item) => item.parentBillingRequired).map((item) => item.key);
		const next = { ...sentSettlementTargets };
		for (const key of keys) next[`${selectedYear}:${selectedMonth}:${key}`] = true;
		sentSettlementTargets = next;
	}

	function requestSent(item: StudentMessage) {
		return !!sentSettlementTargets[`${year}:${month}:${item.key}`];
	}

	function manualDeliveryStateKey(studentKey: string, selectedYear = year, selectedMonth = month) {
		return `${selectedYear}:${selectedMonth}:${studentKey}`;
	}

	function manualDeliveryConfirmed(item: StudentMessage) {
		return manualDeliveryStates[manualDeliveryStateKey(item.key)]?.manualDeliveryConfirmed === true;
	}

	function manualDeliveryConfirmedAt(item: StudentMessage) {
		return (
			manualDeliveryStates[manualDeliveryStateKey(item.key)]?.manualDeliveryConfirmedAt ?? null
		);
	}

	async function confirmManualDelivery(item: StudentMessage) {
		const selectedYear = year;
		const selectedMonth = month;
		const key = manualDeliveryStateKey(item.key, selectedYear, selectedMonth);
		if (
			!data?.generatedAt ||
			!item.parentBillingRequired ||
			generating ||
			requestBusy ||
			manualDeliveryBusyKey ||
			manualDeliveryStates[key]?.manualDeliveryConfirmed
		)
			return;
		manualDeliveryBusyKey = key;
		manualDeliveryErrorKey = '';
		try {
			const updated = await personalApi.confirmParentDelivery(
				selectedYear,
				selectedMonth,
				item.key
			);
			if (year !== selectedYear || month !== selectedMonth) return;
			if (updated.studentKey !== item.key || updated.manualDeliveryConfirmed !== true) {
				throw new Error('수동 확인 응답을 검증하지 못했습니다.');
			}
			manualDeliveryStates = {
				...manualDeliveryStates,
				[key]: {
					manualDeliveryConfirmed: true,
					manualDeliveryConfirmedAt: updated.manualDeliveryConfirmedAt ?? null
				}
			};
		} catch {
			if (year === selectedYear && month === selectedMonth) manualDeliveryErrorKey = key;
		} finally {
			if (manualDeliveryBusyKey === key) manualDeliveryBusyKey = '';
		}
	}

	async function sendSettlementRequest(studentKey: string | null = null) {
		if (
			requestBusy ||
			requestBlocked(studentKey) ||
			generating ||
			manualDeliveryBusyKey ||
			!data?.generatedAt
		)
			return;
		requestBusy = true;
		requestPreviewError = '';
		requestResult = '';
		requestFeedbackKey = studentKey ?? 'all';
		const senderName = assistantName.trim() || '김지후';
		const selectedYear = year;
		const selectedMonth = month;
		try {
			const plan = await personalApi.previewSettlementRequest(
				selectedYear,
				selectedMonth,
				crypto.randomUUID(),
				senderName,
				studentKey ?? undefined
			);
			if (
				plan?.status === 'succeeded' ||
				plan?.status === 'manual_check' ||
				plan?.status === 'sending'
			) {
				blockRequestTarget(studentKey, selectedYear, selectedMonth);
				if (plan.status === 'succeeded') markRequestSent(studentKey, selectedYear, selectedMonth);
				requestResult =
					plan.status === 'succeeded' ? '전송 완료' : '이전 전송 결과 확인이 필요해요.';
				return;
			}
			const blockReason = requestBlockReason(plan);
			if (blockReason) {
				requestPreviewError = '보내지 못했어요.';
				return;
			}
			if (
				year !== selectedYear ||
				month !== selectedMonth ||
				(assistantName.trim() || '김지후') !== senderName
			) {
				requestPreviewError = '보내지 못했어요.';
				return;
			}
			const result = await personalApi.confirmSettlementRequest(
				plan.requestId,
				plan.planDigest,
				senderName
			);
			if (
				result.status === 'retryable' &&
				result.retryable === true &&
				Number.isSafeInteger(result.sentCount) &&
				result.sentCount >= 0 &&
				result.sentCount < plan.messageCount &&
				(result.alreadySentCount === undefined ||
					(Number.isSafeInteger(result.alreadySentCount) &&
						result.alreadySentCount >= 0 &&
						result.sentCount + result.alreadySentCount < plan.messageCount))
			) {
				requestResult =
					studentKey === null && result.sentCount > 0
						? '일부 전송 전에 중단됐어요. 다시 누르면 재시도해요.'
						: '전송 전에 중단됐어요. 다시 누르면 재시도해요.';
				return;
			}
			const alreadySent = result.alreadySentCount ?? 0;
			if (
				result.status !== 'succeeded' ||
				!Number.isSafeInteger(result.sentCount) ||
				result.sentCount < 0 ||
				!Number.isSafeInteger(alreadySent) ||
				alreadySent < 0 ||
				result.sentCount + alreadySent !== plan.messageCount
			) {
				blockRequestTarget(studentKey, selectedYear, selectedMonth);
				requestResult = '전송 결과를 확인할 수 없어요.';
				return;
			}
			blockRequestTarget(studentKey, selectedYear, selectedMonth);
			markRequestSent(studentKey, selectedYear, selectedMonth);
			requestResult = '전송 완료';
		} catch (cause) {
			if (cause instanceof PersonalApiError && cause.code === 'snapshot_changed') {
				requestPreviewError = '보내지 못했어요.';
			} else if (cause instanceof PersonalApiError && cause.code === 'recipient_unverified') {
				requestPreviewError = '대화방을 확인하지 못해 전송하지 않았어요.';
			} else if (cause instanceof PersonalApiError && cause.code === 'manual_check_only') {
				blockRequestTarget(studentKey, selectedYear, selectedMonth);
				requestPreviewError = '이전 전송 결과 확인이 필요해요.';
			} else {
				blockRequestTarget(studentKey, selectedYear, selectedMonth);
				requestPreviewError = '전송 결과를 확인할 수 없어요.';
			}
		} finally {
			requestBusy = false;
		}
	}

	function requestBlockReason(plan: SettlementRequestPlan | null) {
		if (!plan || !['awaiting_confirmation', 'retryable'].includes(plan.status))
			return '미리보기 상태를 확인할 수 없어 발송할 수 없습니다.';
		const summary = plan.exclusionSummary;
		const counts = summary && [
			summary.acceptedStageStudents,
			summary.unknownStageStudents,
			summary.zeroParentChargeStudents,
			plan.excludedStudentCount,
			plan.messageCount
		];
		if (!counts || !counts.every((value) => Number.isSafeInteger(value) && value >= 0)) {
			return '미리보기 응답이 불완전하여 발송할 수 없습니다.';
		}
		if (summary.unknownStageStudents > 0) return '확인되지 않은 회차가 있어 발송할 수 없습니다.';
		if (
			plan.excludedStudentCount !==
			summary.acceptedStageStudents +
				summary.unknownStageStudents +
				summary.zeroParentChargeStudents
		) {
			return '제외 집계가 일치하지 않아 발송할 수 없습니다.';
		}
		if (
			!plan.requestId?.trim() ||
			!plan.planDigest?.trim() ||
			!plan.snapshotDigest?.trim() ||
			!Number.isSafeInteger(plan.snapshotId) ||
			plan.snapshotId <= 0
		) {
			return '승인 정보가 불완전하여 발송할 수 없습니다.';
		}
		if (plan.messageCount === 0) return '발송할 수 있는 부모 부담 대상이 없습니다.';
		if (
			!Array.isArray(plan.matchedRooms) ||
			!Array.isArray(plan.messagePreviews) ||
			plan.matchedRooms.length !== plan.messageCount ||
			plan.messagePreviews.length !== plan.messageCount
		) {
			return '방 확인 상태가 불완전하여 발송할 수 없습니다.';
		}
		const rooms = new Set<string>();
		for (let index = 0; index < plan.messageCount; index++) {
			const matched = plan.matchedRooms[index];
			const message = plan.messagePreviews[index];
			if (
				!matched ||
				!message ||
				matched.evidence !== 'unique_exact' ||
				typeof matched.room !== 'string' ||
				!matched.room.trim() ||
				typeof message.room !== 'string' ||
				message.room !== matched.room ||
				rooms.has(matched.room) ||
				!Number.isSafeInteger(matched.parentCharge) ||
				matched.parentCharge <= 0 ||
				!Number.isSafeInteger(message.parentCharge) ||
				message.parentCharge <= 0 ||
				matched.parentCharge !== message.parentCharge ||
				typeof message.text !== 'string' ||
				!message.text.trim()
			) {
				return '방 확인 상태가 불완전하여 발송할 수 없습니다.';
			}
			rooms.add(matched.room);
		}
		return '';
	}

	async function copyMessage(item: StudentMessage) {
		try {
			await navigator.clipboard.writeText(item.message);
			copiedStudent = item.studentName;
		} catch {
			error = '자동 복사에 실패했습니다. 아래 문구를 직접 복사해주세요.';
		}
	}

	onMount(load);
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Monthly settlement</p>
		<h1>학교별 월 정산</h1>
		<p>취소되지 않은 회차를 기준으로, 리포트 완료 여부와 무관하게 정산을 확인합니다.</p>
	</div>
	<div class="export-controls">
		<label>보내는 조교명 <input bind:value={assistantName} placeholder="예: 김지후" /></label>
		<div class="request-action">
			<button
				class="ghost-button settlement-request-button"
				onclick={() => sendSettlementRequest()}
				disabled={!data?.generatedAt ||
					generating ||
					requestBusy ||
					!!manualDeliveryBusyKey ||
					requestBlocked()}
				aria-busy={requestBusy}
				>{#if requestBusy}<span
						class="loading-spinner"
						data-testid="settlement-send-spinner"
						aria-hidden="true"
					></span>{/if}{requestBusy ? '전송 중…' : '정산 요청'}</button
			>
			{#if requestFeedbackKey === 'all' && (requestPreviewError || requestResult)}
				<small class="request-feedback" role="status" aria-live="polite"
					>{requestResult || requestPreviewError}</small
				>
			{/if}
		</div>
		<button
			class="primary-button settlement-generate-button"
			onclick={() => generate()}
			disabled={generating || requestBusy || !!manualDeliveryBusyKey}
			>{generating
				? '정산 생성 중…'
				: data?.generatedAt
					? '↻ 월별 정산 다시 생성'
					: '＋ 월별 정산 생성하기'}</button
		>
		<button
			class="ghost-button settlement-export-button"
			onclick={download}
			disabled={!data?.generatedAt}>↓ 엑셀 내보내기</button
		>
	</div>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}

<div class="settlement-top">
	<div class="month-picker">
		<button
			aria-label="이전 달"
			disabled={generating || requestBusy || !!manualDeliveryBusyKey}
			onclick={() => moveMonth(-1)}>‹</button
		><strong>{year}년 {month}월</strong><button
			aria-label="다음 달"
			disabled={generating || requestBusy || !!manualDeliveryBusyKey}
			onclick={() => moveMonth(1)}>›</button
		>
	</div>
	<div class="summary card">
		<span>정산 대상 {data?.settlementCount ?? 0}회 · 완료 {data?.completedCount ?? 0}회</span
		><strong>{(data?.totalAmount ?? 0).toLocaleString()}원</strong>
	</div>
</div>
{#if data?.generatedAt}
	<p class="generated-at">
		마지막 생성: {new Date(data.generatedAt).toLocaleString('ko-KR')} · 일정이 바뀌면 다시 생성하세요.
	</p>
{:else if !loading}
	<p class="generated-at">아직 생성된 정산이 없습니다. 위 버튼을 눌러 이 달의 정산을 확정하세요.</p>
{/if}

<section class="card table" aria-busy={loading}>
	<div class="table-head">
		<span>일시</span><span>학교</span><span>회차</span><span>인원</span><span>조교 정산</span><span
			>학부모 1인</span
		><span>부담</span><span>지급</span>
	</div>
	{#each data?.items ?? [] as item (item.id)}
		<a href={`/personal-project/aura/schools/${item.schoolId}`} class="table-row">
			<time>{new Date(item.startTime).toLocaleString('ko-KR')}</time>
			<strong>{schoolDisplayName(item.schoolName)}</strong>
			<span>{item.roundLabel}</span>
			<span>{item.targets.length}명</span>
			<b>{item.amount.toLocaleString()}원</b>
			<b>{parentCharge(item).toLocaleString()}원</b>
			<span>{parentCharge(item) === 0 ? '학원 부담' : '학부모 부담'}</span>
			<span class={`status-pill ${item.paymentStatus}`}
				>{item.paymentStatus === 'paid' ? '지급 완료' : '미지급'}</span
			>
		</a>
	{:else}
		<div class="empty">{loading ? '불러오는 중…' : '정산 대상 회차가 없습니다.'}</div>
	{/each}
</section>

<section class="card message-panel">
	<header>
		<div>
			<p class="eyebrow">Parent message</p>
			<h2>학생별 클리닉 비용 안내문</h2>
			<p>학기·시즌 표기 없이 학생의 학교 이름으로 바로 보낼 문구입니다.</p>
			{#if manualDeliveryLoadError}<p class="manual-delivery-error" role="status">
					{manualDeliveryLoadError}
				</p>{/if}
		</div>
	</header>
	{#each studentMessages as item (item.key)}
		<article
			class="message-row"
			class:sent-success={requestSent(item) || manualDeliveryConfirmed(item)}
		>
			<div>
				<strong>{item.studentName}</strong>
				<span>{item.cumulative} · {item.amount.toLocaleString()}원</span>
			</div>
			<pre class:no-charge={!item.parentBillingRequired}>{item.message}</pre>
			<div class="message-actions">
				{#if item.parentBillingRequired}
					<button class="ghost-button" onclick={() => copyMessage(item)}>복사</button>
					<button
						class="ghost-button send-student-button"
						onclick={() => sendSettlementRequest(item.key)}
						disabled={generating || requestBusy || requestBlocked(item.key)}
						aria-busy={requestBusy && requestFeedbackKey === item.key}
					>
						{#if requestBusy && requestFeedbackKey === item.key}<span
								class="loading-spinner"
								data-testid="settlement-send-spinner"
								aria-hidden="true"
							></span>{/if}
						{requestBusy && requestFeedbackKey === item.key ? '전송 중…' : '학생별 정산 보내기'}
					</button>
					{#if requestFeedbackKey === item.key && (requestPreviewError || requestResult)}
						<small
							class="request-feedback"
							class:sent-status={requestResult === '전송 완료'}
							role="status"
							aria-live="polite">{requestResult || requestPreviewError}</small
						>
					{/if}
				{:else}
					{#if copiedStudent === item.studentName}<small>복사됨</small>{/if}
					<small>합격자반 또는 0원 회차: 학부모 정산 제외</small>
				{/if}
				{#if item.parentBillingRequired && data?.generatedAt}
					{#if manualDeliveryConfirmed(item)}
						<small
							class="manual-delivery-status"
							role="status"
							title={manualDeliveryConfirmedAt(item) ?? '수동 전송 확인'}>수동 확인 완료</small
						>
					{:else}
						<button
							class="manual-delivery-button"
							onclick={() => confirmManualDelivery(item)}
							disabled={generating || requestBusy || !!manualDeliveryBusyKey || !data?.generatedAt}
							aria-busy={manualDeliveryBusyKey === manualDeliveryStateKey(item.key)}
							title="카카오 재전송 없이 전송 완료 확인만 기록합니다"
						>
							{#if manualDeliveryBusyKey === manualDeliveryStateKey(item.key)}<span
									class="loading-spinner"
									aria-hidden="true"
								></span>{/if}
							{manualDeliveryBusyKey === manualDeliveryStateKey(item.key)
								? '기록 중…'
								: '전송 완료로 기록'}
						</button>
					{/if}
					{#if manualDeliveryErrorKey === manualDeliveryStateKey(item.key)}
						<small class="manual-delivery-error" role="status"
							>확인 기록에 실패했습니다. 다시 시도해 주세요.</small
						>
					{/if}
				{/if}
				{#if copiedStudent === item.studentName && item.parentBillingRequired}<small>복사됨</small
					>{/if}
			</div>
		</article>
	{:else}
		<div class="empty">
			{loading ? '안내문을 준비하는 중…' : '학생이 등록된 정산 대상 회차가 없습니다.'}
		</div>
	{/each}
</section>

<style>
	.request-feedback {
		color: var(--pp-muted);
		font-size: 11px;
		font-weight: 600;
	}
	.sent-status {
		color: #34724a;
		font-weight: 700;
	}
	.manual-delivery-button {
		min-height: 28px;
		padding: 4px 7px;
		border: 1px solid var(--pp-line);
		border-radius: 6px;
		background: rgb(255 255 255 / 65%);
		color: var(--pp-muted);
		font: inherit;
		font-size: 9px;
		white-space: nowrap;
		cursor: pointer;
	}
	.manual-delivery-button:focus-visible {
		outline: 2px solid var(--pp-sage-dark);
		outline-offset: 2px;
	}
	.manual-delivery-button:disabled {
		cursor: wait;
		opacity: 0.65;
	}
	.manual-delivery-status {
		color: #34724a !important;
		font-weight: 700;
	}
	.manual-delivery-error {
		color: #a56545 !important;
	}
	.loading-spinner {
		width: 12px;
		height: 12px;
		flex: 0 0 12px;
		border: 2px solid currentColor;
		border-right-color: transparent;
		border-radius: 50%;
		animation: settlement-spin 0.7s linear infinite;
	}
	.settlement-request-button,
	.send-student-button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 7px;
	}
	.send-student-button {
		min-width: 132px;
	}
	@keyframes settlement-spin {
		to {
			transform: rotate(360deg);
		}
	}
	.request-action {
		display: contents;
	}
	.page-head {
		flex-wrap: wrap;
		align-items: flex-start;
	}
	.page-head > div:first-child {
		flex: 1 1 280px;
		min-width: 0;
	}
	.export-controls {
		flex: 1 1 620px;
		min-width: 0;
		max-width: 100%;
		flex-wrap: wrap;
		justify-content: flex-end;
		display: flex;
		align-items: center;
		gap: 9px;
	}
	.export-controls button,
	.export-controls label {
		flex: 0 0 auto;
		white-space: nowrap;
	}
	.export-controls label {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.export-controls input {
		flex: 0 0 84px;
		width: 84px;
		height: 32px;
		box-sizing: border-box;
		padding: 0 8px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
		background: white;
	}
	.generated-at {
		margin: -9px 0 17px;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.settlement-top {
		margin-bottom: 18px;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-start;
		gap: 18px;
	}
	.month-picker {
		flex: 0 0 auto;
		max-width: 100%;
		white-space: nowrap;
		display: flex;
		align-items: center;
		gap: 13px;
	}
	.month-picker button {
		width: 34px;
		height: 34px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: white;
		cursor: pointer;
	}
	.month-picker strong {
		min-width: 105px;
		font:
			500 16px Georgia,
			'Noto Sans KR',
			serif;
		text-align: center;
	}
	.summary {
		box-sizing: border-box;
		flex: 1 1 280px;
		min-width: 0;
		max-width: 100%;
		padding: 14px 19px;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 20px;
		align-items: center;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.summary > span {
		min-width: 0;
	}
	.summary strong {
		flex: 0 0 auto;
		white-space: nowrap;
		color: var(--pp-sage-dark);
		font:
			500 18px Georgia,
			serif;
	}
	.table {
		overflow: hidden;
	}
	.table-head,
	.table-row {
		padding: 14px 21px;
		display: grid;
		grid-template-columns: 1.25fr 0.85fr 0.55fr 0.45fr 0.75fr 0.75fr 0.7fr 0.7fr;
		align-items: center;
		gap: 13px;
	}
	.table-head {
		background: #efede7;
		color: var(--pp-muted);
		font-size: 9px;
		font-weight: 700;
	}
	.table-row {
		border-top: 1px solid var(--pp-line);
		color: inherit;
		font-size: 10px;
		text-decoration: none;
	}
	.table-row time {
		color: var(--pp-muted);
		font-size: 9px;
	}
	.table-row > b {
		color: var(--pp-sage-dark);
		text-align: right;
	}
	.empty {
		padding: 65px;
		color: var(--pp-muted);
		font-size: 11px;
		text-align: center;
	}
	.message-panel {
		margin-top: 18px;
		overflow: hidden;
	}
	.message-panel header {
		padding: 19px 21px;
		border-bottom: 1px solid var(--pp-line);
	}
	.message-panel h2 {
		margin: 0;
		font:
			500 17px Georgia,
			'Noto Sans KR',
			serif;
	}
	.message-panel header p:last-child {
		margin: 6px 0 0;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.message-row {
		padding: 16px 21px;
		display: grid;
		grid-template-columns: 150px minmax(0, 1fr) auto;
		gap: 16px;
		align-items: start;
		border-top: 1px solid var(--pp-line);
	}
	.message-row.sent-success {
		background-color: #edf6ef;
		box-shadow: inset 3px 0 #7caf89;
	}
	.message-row > div:first-child strong,
	.message-row > div:first-child span {
		display: block;
	}
	.message-row > div:first-child strong {
		font-size: 12px;
	}
	.message-row > div:first-child span {
		margin-top: 5px;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.message-row pre {
		margin: 0;
		white-space: pre-wrap;
		font:
			10px/1.55 'Noto Sans KR',
			sans-serif;
	}
	.message-row pre.no-charge {
		color: #a56545;
		font-weight: 700;
	}
	.message-actions {
		display: grid;
		gap: 5px;
		justify-items: center;
	}
	.message-actions small {
		color: var(--pp-sage-dark);
		font-size: 9px;
	}
	@media (prefers-reduced-motion: reduce) {
		.loading-spinner {
			animation-duration: 1.6s;
		}
	}
	@media (max-width: 820px) {
		.page-head > div:first-child {
			flex: 0 1 auto;
		}
		.export-controls {
			flex: 0 1 auto;
			width: 100%;
		}
	}
	@media (max-width: 720px) {
		.page-head > div:first-child {
			flex: 0 0 100%;
		}
		.export-controls {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			align-items: stretch;
			gap: 8px;
			width: 100%;
		}
		.export-controls > label {
			grid-column: 1 / -1;
			width: 100%;
			box-sizing: border-box;
			justify-content: space-between;
		}
		.request-action {
			display: flex;
			grid-column: 1;
			grid-row: 2;
			flex-direction: column;
			align-items: stretch;
			gap: 4px;
			min-width: 0;
			min-height: 64px;
		}
		.request-action > .request-feedback {
			display: block;
			min-height: 13px;
			line-height: 13px;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.request-action button,
		.settlement-generate-button,
		.settlement-export-button {
			width: 100%;
			min-width: 0;
			box-sizing: border-box;
			padding-inline: 8px;
			white-space: normal;
			justify-content: center;
		}
		.settlement-generate-button {
			grid-column: 2;
			grid-row: 2;
			align-self: start;
		}
		.settlement-export-button {
			grid-column: 1 / -1;
			grid-row: 3;
		}
		.settlement-top {
			align-items: stretch;
			flex-direction: column;
		}
		.summary {
			flex: 0 1 auto;
			width: 100%;
		}
		.table-head {
			display: none;
		}
		.table-row {
			grid-template-columns: 1fr auto;
		}
		.table-row > *:nth-child(1),
		.table-row > *:nth-child(3),
		.table-row > *:nth-child(4),
		.table-row > *:nth-child(5) {
			display: none;
		}
		.message-row {
			grid-template-columns: 1fr auto;
		}
		.message-row pre {
			grid-column: 1 / -1;
		}
	}
</style>
