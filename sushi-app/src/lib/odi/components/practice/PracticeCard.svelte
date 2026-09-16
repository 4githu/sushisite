<script lang="ts">
	import type { PracticeExercise } from '$lib/odi/domain/practice';
	import { practiceIcon } from '$lib/odi/icons/practice';
	import arrowLeft from '$lib/odi/icons/figma-ui/practice-arrow-left.svg';
	let {
		exercise,
		level = 0,
		progress = 0,
		onselect
	}: {
		exercise: PracticeExercise;
		level?: number;
		progress?: number;
		onselect: () => void;
	} = $props();
</script>

<button class="practice-card" disabled={!exercise.available} onclick={onselect}
	><div class="card-top">
		<img class="practice-icon" src={practiceIcon(exercise.id)} alt="" />
		<div>
			<h3>{exercise.title}</h3>
			<p>{exercise.task}</p>
		</div>
		<span class="card-arrow" aria-hidden="true"><img src={arrowLeft} alt="" /></span>
	</div>
	{#if exercise.available}<footer>
			<span>Lv. {level}</span><progress
				max="3"
				value={progress}
				aria-label={`${exercise.title} 다음 레벨 진도`}
			></progress><small>{progress}/3</small>
		</footer>{:else}<p class="soon">준비 중</p>{/if}</button
>

<style>
	.practice-card {
		display: block;
		text-align: left;
		padding: 20px;
		border: 1px solid #dce0ea;
		border-radius: 10px;
		background: white;
		min-height: 180px;
		color: #151b28;
	}
	.card-top {
		display: flex;
		gap: 12px;
	}
	.practice-icon {
		width: 40px;
		height: 40px;
		flex-shrink: 0;
	}
	.card-top > div {
		flex: 1;
	}
	.card-arrow {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		flex-shrink: 0;
		border: 1px solid var(--cool-grey-light-active, #caced9);
		border-radius: 50%;
	}
	.card-arrow img {
		width: 14px;
		height: 14px;
		transform: rotate(180deg);
	}
	.card-top h3 {
		font-size: 16px !important;
	}
	.card-top p {
		font-size: 13px;
		color: #767e90;
	}
	footer {
		display: flex;
		align-items: center;
		gap: 12px;
		font-size: 12px;
		color: #667088;
		margin-top: 20px;
	}
	progress {
		flex: 1;
		min-width: 0;
		width: auto;
		height: 5px;
		accent-color: #03f;
	}
	small,
	footer > span {
		white-space: nowrap;
	}
	.soon {
		font-size: 12px;
		color: #858c9c;
	}
</style>
