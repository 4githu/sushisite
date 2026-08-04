<script lang="ts">
	import type { ClinicRound } from '$lib/personal-project/shared/types';

	let {
		sessions,
		onselect,
		onedit
	}: {
		sessions: ClinicRound[];
		onselect: (start: Date, end: Date) => void;
		onedit: (session: ClinicRound) => void;
	} = $props();

	let weekCursor = $state(new Date());
	let dragging = $state(false);
	let anchor = $state<{ day: number; slot: number } | null>(null);
	let current = $state<{ day: number; slot: number } | null>(null);

	const slots = Array.from({ length: 34 }, (_, index) => index);
	const days = $derived(weekDays(weekCursor));
	const invalidSessions = $derived(
		sessions.filter((session) => {
			if (!session.endTime) return false;
			return (
				new Date(session.endTime).getTime() - new Date(session.startTime).getTime() >
				12 * 60 * 60_000
			);
		})
	);
	const weekTitle = $derived(
		`${days[0]?.getMonth()! + 1}월 ${days[0]?.getDate()}일 — ${days[6]?.getMonth()! + 1}월 ${days[6]?.getDate()}일`
	);

	function startOfWeek(date: Date) {
		const result = new Date(date);
		const day = result.getDay();
		result.setDate(result.getDate() - (day === 0 ? 6 : day - 1));
		result.setHours(0, 0, 0, 0);
		return result;
	}

	function weekDays(date: Date) {
		const monday = startOfWeek(date);
		return Array.from({ length: 7 }, (_, index) => {
			const day = new Date(monday);
			day.setDate(monday.getDate() + index);
			return day;
		});
	}

	function moveWeek(step: number) {
		const next = new Date(weekCursor);
		next.setDate(next.getDate() + step * 7);
		weekCursor = next;
	}

	function slotDate(dayIndex: number, slot: number) {
		const date = new Date(days[dayIndex]);
		date.setHours(8, slot * 30, 0, 0);
		return date;
	}

	function sessionsAt(dayIndex: number, slot: number) {
		const start = slotDate(dayIndex, slot);
		const end = new Date(start.getTime() + 30 * 60_000);
		return sessions.filter((session) => {
			const sessionStart = new Date(session.startTime);
			const rawEnd = session.endTime
				? new Date(session.endTime)
				: new Date(sessionStart.getTime() + 60 * 60_000);
			const sessionEnd =
				rawEnd.getTime() - sessionStart.getTime() > 12 * 60 * 60_000
					? new Date(sessionStart.getTime() + 60 * 60_000)
					: rawEnd;
			return sessionStart < end && sessionEnd > start;
		});
	}

	function hasCompletedReport(session: ClinicRound) {
		return session.targets.length > 0 && session.targets.every((target) =>
			target.report?.status === 'ready' || target.report?.status === 'submitted'
		);
	}

	function begin(day: number, slot: number) {
		dragging = true;
		anchor = { day, slot };
		current = { day, slot };
	}

	function extend(day: number, slot: number) {
		if (!dragging || !anchor || anchor.day !== day) return;
		current = { day, slot };
	}

	function finish() {
		if (!dragging || !anchor || !current) return;
		dragging = false;
		const first = Math.min(anchor.slot, current.slot);
		const last = Math.max(anchor.slot, current.slot);
		onselect(slotDate(anchor.day, first), slotDate(anchor.day, last + 1));
		anchor = null;
		current = null;
	}

	function selected(day: number, slot: number) {
		if (!dragging || !anchor || !current || anchor.day !== day) return false;
		return (
			slot >= Math.min(anchor.slot, current.slot) && slot <= Math.max(anchor.slot, current.slot)
		);
	}

	function timeLabel(slot: number) {
		const minutes = 8 * 60 + slot * 30;
		return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
	}
</script>

<section
	class="week-scheduler card"
	onmouseleave={finish}
	role="application"
	aria-label="주간 클리닉 시간표"
>
	<header>
		<div>
			<p class="eyebrow">Quick schedule</p>
			<h2>주간 시간표</h2>
			<span>빈 칸을 30분 단위로 드래그하면 클리닉 등록창이 열립니다.</span>
		</div>
		<div class="week-nav">
			<button onclick={() => moveWeek(-1)} aria-label="이전 주">‹</button>
			<strong>{weekTitle}</strong>
			<button onclick={() => moveWeek(1)} aria-label="다음 주">›</button>
		</div>
	</header>
	{#if invalidSessions.length}
		<div class="invalid-warning">
			<strong>시간이 비정상적으로 긴 일정 {invalidSessions.length}건</strong>
			<span>
				{invalidSessions.map((item) => item.schoolName).join(', ')} 일정은 시간표에서 임시로 1시간만 표시합니다.
				목록이나 상세 화면에서 시간을 수정해주세요.
			</span>
		</div>
	{/if}

	<div class="scheduler-scroll">
		<div
			class="scheduler-grid"
			onmouseup={finish}
			role="grid"
			tabindex="0"
			aria-label="30분 일정 선택"
		>
			<div class="corner"></div>
			{#each days as day}
				<div class:today={day.toDateString() === new Date().toDateString()} class="day-head">
					<span>{new Intl.DateTimeFormat('ko-KR', { weekday: 'short' }).format(day)}</span>
					<strong>{day.getDate()}</strong>
				</div>
			{/each}

			{#each slots as slot}
				<div class:majorBoundary={slot === 8 || slot === 20} class="time-label">
					{slot % 2 === 0 ? timeLabel(slot) : ''}
				</div>
				{#each days as _, dayIndex}
					{@const busy = sessionsAt(dayIndex, slot)}
					<button
						class:busy={busy.length > 0}
						class:reportDone={busy.length > 0 && hasCompletedReport(busy[0])}
						class:selected={selected(dayIndex, slot)}
						class:majorBoundary={slot === 8 || slot === 20}
						class="slot"
						title={busy.map((item) => item.schoolName).join(', ')}
						onmousedown={(event) => {
							event.preventDefault();
							if (busy.length) {
								onedit(busy[0]);
								return;
							}
							begin(dayIndex, slot);
						}}
						onmouseenter={() => extend(dayIndex, slot)}
						aria-label={`${days[dayIndex].toLocaleDateString('ko-KR')} ${timeLabel(slot)}`}
					>
						{#if busy.length && slot % 2 === 0}<span>{busy[0].schoolName} {busy[0].roundLabel}</span
							>{/if}
					</button>
				{/each}
			{/each}
		</div>
	</div>
</section>

<style>
	.week-scheduler {
		margin-top: 18px;
		overflow: hidden;
	}

	header {
		padding: 20px 23px;
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 20px;
		border-bottom: 1px solid var(--pp-line);
	}

	h2 {
		margin: 0;
		font-family: Georgia, 'Noto Sans KR', serif;
		font-size: 18px;
		font-weight: 500;
	}

	header > div:first-child > span {
		color: var(--pp-muted);
		font-size: 9px;
	}

	.week-nav {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.week-nav button {
		width: 30px;
		height: 30px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
		background: white;
		cursor: pointer;
	}

	.week-nav strong {
		min-width: 150px;
		font-size: 10px;
		text-align: center;
	}

	.scheduler-scroll {
		overflow: visible;
	}

	.invalid-warning {
		padding: 11px 20px;
		display: flex;
		gap: 10px;
		background: #fff1e9;
		color: #965840;
		font-size: 9px;
	}

	.invalid-warning strong {
		flex: 0 0 auto;
	}

	.scheduler-grid {
		min-width: 0;
		display: grid;
		grid-template-columns: 58px repeat(7, minmax(0, 1fr));
		user-select: none;
	}

	.corner,
	.day-head {
		position: sticky;
		top: 0;
		z-index: 3;
		background: #f8f7f2;
		border-bottom: 1px solid var(--pp-line);
	}

	.day-head {
		height: 52px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		border-left: 1px solid var(--pp-line);
	}

	.day-head span {
		color: var(--pp-muted);
		font-size: 9px;
	}

	.day-head strong {
		font-family: Georgia, serif;
		font-size: 15px;
	}

	.day-head.today strong {
		width: 25px;
		height: 25px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: var(--pp-sage-dark);
		color: white;
	}

	.time-label {
		min-height: 24px;
		padding: 3px 8px 0 0;
		border-top: 1px solid #eeece6;
		color: var(--pp-muted);
		font-size: 8px;
		text-align: right;
	}

	.slot {
		position: relative;
		min-height: 24px;
		padding: 0;
		border: 0;
		border-top: 1px solid #eeece6;
		border-left: 1px solid #eeece6;
		background: white;
		cursor: crosshair;
	}

	.slot:nth-child(16n) {
		border-top-color: #d8d5cd;
	}

	.slot:hover {
		background: #edf2ed;
	}

	.slot.selected {
		background: #cddccf;
	}

	.slot.busy {
		background: #f1dcd1;
	}

	.slot.busy.reportDone {
		background: #d8ebdd;
	}

	.slot.busy span {
		position: absolute;
		inset: 2px 4px;
		overflow: hidden;
		color: #875b48;
		font-size: 8px;
		font-weight: 700;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.slot.busy.reportDone span { color: #3d6b51; }

	.time-label.majorBoundary,
	.slot.majorBoundary {
		border-top: 3px solid #87968b !important;
		box-shadow: inset 0 1px 0 #ffffff;
	}

	@media (max-width: 720px) {
		header {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
