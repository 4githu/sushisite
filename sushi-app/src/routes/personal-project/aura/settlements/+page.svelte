<script lang="ts">
	import { onMount } from 'svelte';
	import { personalApi } from '$lib/personal-project/shared/api';
	import type { ClinicRound, SchoolSettlement } from '$lib/personal-project/shared/types';

	const now = new Date();
	let year = $state(now.getFullYear());
	let month = $state(now.getMonth() + 1);
	let data = $state<SchoolSettlement | null>(null);
	let loading = $state(true);
	let generating = $state(false);
	let error = $state('');
	let assistantName = $state('김지후');
	let copiedStudent = $state('');

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
		const grouped = new Map<string, { schoolName: string; studentName: string; items: ClinicRound[] }>();
		for (const item of data?.items ?? []) {
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
			.map(([key, group]) => buildStudentMessage(key, group.schoolName, group.studentName, group.items))
			.sort((left, right) => left.studentName.localeCompare(right.studentName, 'ko'));
	});

	function durationHours(item: ClinicRound) {
		return Math.max(0, (+new Date(item.endTime) - +new Date(item.startTime)) / 3_600_000);
	}

	function hoursText(hours: number) {
		const minutes = Math.round(hours * 60);
		return minutes % 60 ? `${Math.floor(minutes / 60)}시간 ${minutes % 60}분` : `${minutes / 60}시간`;
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

	function buildStudentMessage(key: string, schoolName: string, studentName: string, entries: ClinicRound[]): StudentMessage {
		const items = [...entries].sort((left, right) => +new Date(left.startTime) - +new Date(right.startTime));
		const billedItems = items.filter((item) => parentCharge(item) > 0);
		const freeItems = items.filter((item) => parentCharge(item) === 0);
		const hoursByRatio = new Map<string, number>();
		for (const item of billedItems) {
			const ratio = `${Math.max(1, item.targets.length)}:1`;
			hoursByRatio.set(ratio, (hoursByRatio.get(ratio) ?? 0) + durationHours(item));
		}
		const cumulative = [...hoursByRatio.entries()]
			.map(([ratio, hours]) => `${ratio} ${hoursText(hours)}`)
			.join(' / ') || '학부모 청구 없음';
		const amount = items.reduce((total, item) => total + parentCharge(item), 0);
		const sessions = items.map(sessionText);
		const fullName = fullStudentName(schoolName, studentName);
		const billedSessions = billedItems.map(sessionText);
		const message = billedItems.length
			? `안녕하세요? ${assistantName.trim() || '김지후'} 조교입니다. ${month}월 클리닉 비용 안내드립니다.\n\n[클리닉 시간]\n${billedSessions.map((value) => `- ${value}`).join('\n')}\n\n[누적 시간]\n${cumulative}\n\n입금해주셔야 할 금액은 ${amount.toLocaleString()}원입니다.\n학생 이름인 ${fullName}(으)로 입금해주시면 감사하겠습니다.\n\n[클리닉 계좌]\n아우라에듀(주)\n신한은행 140-015-133968${freeItems.length ? '\n\n※ 3:1 이상 무료 클리닉은 청구 금액에서 제외했습니다.' : ''}`
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

	async function load() {
		loading = true;
		try {
			data = await personalApi.settlements(year, month);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '정산을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	function moveMonth(step: number) {
		const date = new Date(year, month - 1 + step, 1);
		year = date.getFullYear();
		month = date.getMonth() + 1;
		load();
	}

	async function download() {
		if (!data?.generatedAt) return;
		const response = await fetch(personalApi.settlementExportUrl(year, month, assistantName, data.generatedAt), {
			credentials: 'include',
			cache: 'no-store'
		});
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
		generating = true;
		error = '';
		try {
			await personalApi.generateSettlements(year, month);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '월별 정산을 생성하지 못했습니다.';
		} finally {
			generating = false;
		}
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
		<button class="primary-button" onclick={generate} disabled={generating}
			>{generating
				? '정산 생성 중…'
				: data?.generatedAt
					? '↻ 월별 정산 다시 생성'
					: '＋ 월별 정산 생성하기'}</button
		>
		<button class="ghost-button" onclick={download} disabled={!data?.generatedAt}>↓ 엑셀 내보내기</button>
	</div>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}

<div class="settlement-top">
	<div class="month-picker">
		<button onclick={() => moveMonth(-1)}>‹</button><strong>{year}년 {month}월</strong><button
			onclick={() => moveMonth(1)}>›</button
		>
	</div>
	<div class="summary card">
		<span>정산 대상 {data?.settlementCount ?? 0}회 · 완료 {data?.completedCount ?? 0}회</span><strong
			>{(data?.totalAmount ?? 0).toLocaleString()}원</strong
		>
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
		<span>일시</span><span>학교</span><span>회차</span><span>인원</span><span
			>조교 정산</span
		><span>학부모 1인</span><span>부담</span><span>지급</span>
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
		</div>
	</header>
	{#each studentMessages as item (item.key)}
		<article class="message-row">
			<div>
				<strong>{item.studentName}</strong>
				<span>{item.cumulative} · {item.amount.toLocaleString()}원</span>
			</div>
			<pre class:no-charge={!item.parentBillingRequired}>{item.message}</pre>
			<div class="message-actions">
				{#if item.parentBillingRequired}
					<button class="ghost-button" onclick={() => copyMessage(item)}>복사</button>
				{:else}
					<small>문자 미생성</small>
				{/if}
				{#if copiedStudent === item.studentName}<small>복사됨</small>{/if}
			</div>
		</article>
	{:else}
		<div class="empty">{loading ? '안내문을 준비하는 중…' : '학생이 등록된 정산 대상 회차가 없습니다.'}</div>
	{/each}
</section>

<style>
	.export-controls {
		display: flex;
		align-items: center;
		gap: 9px;
	}
	.export-controls label {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.export-controls input {
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
		justify-content: space-between;
		align-items: center;
		gap: 18px;
	}
	.month-picker {
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
		padding: 14px 19px;
		display: flex;
		gap: 20px;
		align-items: center;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.summary strong {
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
		font: 500 17px Georgia, 'Noto Sans KR', serif;
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
	.message-row > div:first-child strong,
	.message-row > div:first-child span {
		display: block;
	}
	.message-row > div:first-child strong { font-size: 12px; }
	.message-row > div:first-child span {
		margin-top: 5px;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.message-row pre {
		margin: 0;
		white-space: pre-wrap;
		font: 10px/1.55 'Noto Sans KR', sans-serif;
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
	@media (max-width: 720px) {
		.export-controls {
			align-items: flex-end;
			flex-direction: column;
		}
		.settlement-top {
			align-items: stretch;
			flex-direction: column;
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
		.message-row { grid-template-columns: 1fr auto; }
		.message-row pre { grid-column: 1 / -1; }
	}
</style>
