<script lang="ts">
	import { days, minutes, type Lesson } from './catalog';
	let { lessons }: { lessons: Lesson[] } = $props();
	const first = $derived(Math.min(9, ...lessons.map((l) => Math.floor(minutes(l.start) / 60))));
	const last = $derived(Math.max(18, ...lessons.map((l) => Math.ceil(minutes(l.end) / 60))));
	const count = $derived(lessons.some((l) => l.weekday > 4) ? 7 : 5);
	const colors = ['#f5d8d1', '#dce7ee', '#e3def2', '#dcebdc', '#f2e4c9', '#d6e9e7', '#eddae7'];
	const titles = $derived([...new Set(lessons.map((l) => l.title))]);
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex (keyboard scrolling of the timetable) -->
<div class="grid-scroll" tabindex="0" role="region" aria-label="주간 수업 시간표">
	<div class="timetable" style={`--days:${count}`}>
		<div class="corner">시간</div>
		{#each days.slice(0, count) as day}<div class="day">{day}</div>{/each}
		<div class="hours" style={`height:${(last - first) * 64}px`}>
			{#each Array(last - first) as _, i}<span style={`top:${i * 64}px`}
					>{String(first + i).padStart(2, '0')}</span
				>{/each}
		</div>
		{#each days.slice(0, count) as _, d}<div
				class="column"
				style={`height:${(last - first) * 64}px`}
			>
				{#each lessons.filter((l) => l.weekday === d) as lesson}<div
						class="class-block"
						style={`top:${((minutes(lesson.start) - first * 60) / 60) * 64}px;height:${((minutes(lesson.end) - minutes(lesson.start)) / 60) * 64}px;background:${colors[titles.indexOf(lesson.title) % colors.length]}`}
						title={`${lesson.title} ${lesson.start}–${lesson.end} ${lesson.location}`}
					>
						<strong>{lesson.title}</strong><span>{lesson.start}–{lesson.end}</span><small
							>{lesson.location}</small
						>
					</div>{/each}
			</div>{/each}
	</div>
</div>

<style>
	.grid-scroll {
		overflow: auto;
		border: 1px solid var(--ondo-line);
		border-radius: 12px;
		background: white;
	}
	.timetable {
		display: grid;
		grid-template-columns: 36px repeat(var(--days), minmax(90px, 1fr));
		min-width: 500px;
	}
	.corner,
	.day {
		position: sticky;
		top: 0;
		z-index: 2;
		text-align: center;
		padding: 12px 0;
		background: #fff;
		border-bottom: 1px solid #e2e3e7;
		font-size: 12px;
		color: #686a72;
	}
	.hours {
		position: relative;
		border-right: 1px solid #e2e3e7;
	}
	.hours span {
		position: absolute;
		width: 100%;
		text-align: center;
		font-size: 11px;
		color: #777;
		transform: translateY(3px);
	}
	.column {
		position: relative;
		border-right: 1px solid #ececf0;
		background: repeating-linear-gradient(
			to bottom,
			transparent 0,
			transparent 63px,
			#e9eaee 63px,
			#e9eaee 64px
		);
	}
	.class-block {
		position: absolute;
		left: 2px;
		right: 2px;
		border-radius: 5px;
		padding: 5px;
		box-sizing: border-box;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 3px;
		font-size: 11px;
		color: #333;
	}
	.class-block strong {
		font-size: 12px;
		line-height: 1.35;
	}
	.class-block span,
	.class-block small {
		font-size: 10px;
	}
	@media (max-width: 760px) {
		.timetable {
			min-width: 0;
			grid-template-columns: 28px repeat(var(--days), minmax(52px, 1fr));
		}
		.class-block {
			padding: 4px 3px;
		}
		.class-block strong {
			font-size: 10px;
		}
		.class-block span,
		.class-block small {
			font-size: 9px;
		}
	}
</style>
