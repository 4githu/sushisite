<!-- src/lib/odi/components/session/PresentationAudienceSettingCard.svelte -->
<script lang="ts">
	import SurfaceCard from "$lib/odi/components/common/SurfaceCard.svelte";
	import SessionSlider from "$lib/odi/components/session/SessionSlider.svelte";
	import SegmentedControl from "$lib/odi/components/session/SegmentedControl.svelte";

	type AudienceType = "general" | "student" | "judge" | "mixed";
	type Level = "low" | "medium" | "high";

	let {
		audienceType = $bindable<AudienceType>("general"),
		audienceSize = $bindable(20),
		expertiseLevel = $bindable<Level>("medium"),
		interestLevel = $bindable<Level>("medium")
	}: {
		audienceType?: AudienceType;
		audienceSize?: number;
		expertiseLevel?: Level;
		interestLevel?: Level;
	} = $props();

	const audienceTypes = [
		{ value: "general", title: "일반 청중", subtitle: "비전공자", icon: "person" },
		{ value: "student", title: "학생 중심", subtitle: "관련 전공생", icon: "school" },
		{ value: "judge", title: "심사위원 중심", subtitle: "교수 및 평가위원", icon: "crown" },
		{ value: "mixed", title: "혼합", subtitle: "다양한 청중", icon: "group" }
	] as const;

	const audienceSizeTicks = [
		{ value: 1, label: "1명" },
		{ value: 10, label: "10명" },
		{ value: 20, label: "20명" },
		{ value: 30, label: "30명" },
		{ value: 40, label: "40명" },
		{ value: 50, label: "50명+" }
	];

	const levelItems = [
		{ label: "낮음", value: "low" },
		{ label: "중간", value: "medium" },
		{ label: "높음", value: "high" }
	];

	function applyRecommendedPreset(type: AudienceType) {
		audienceType = type;

		if (type === "general") {
			expertiseLevel = "low";
			interestLevel = "medium";
			audienceSize = 20;
		}

		if (type === "student") {
			expertiseLevel = "medium";
			interestLevel = "high";
			audienceSize = 20;
		}

		if (type === "judge") {
			expertiseLevel = "high";
			interestLevel = "medium";
			audienceSize = 10;
		}

		if (type === "mixed") {
			expertiseLevel = "medium";
			interestLevel = "medium";
			audienceSize = 30;
		}
	}
</script>

<SurfaceCard padding="36px" minHeight="609px">
	<div class="audience-card">
		<section class="section">
			<div class="section-header">
				<div class="title-icon" aria-hidden="true">
					<span>▣</span>
				</div>

				<h2 class="text-title-middle">청중 유형</h2>
				<p class="section-help text-body">청중 유형을 선택하면 추천 설정이 자동 적용됩니다.</p>
			</div>

			<div class="audience-type-grid">
				{#each audienceTypes as item}
					<button
						type="button"
						class="audience-type clickable"
						class:selected={audienceType === item.value}
						onclick={() => applyRecommendedPreset(item.value)}
					>
						<div class="audience-icon" aria-hidden="true">
							{#if item.icon === "person"}
								<span>♙</span>
							{:else if item.icon === "school"}
								<span>▱</span>
							{:else if item.icon === "crown"}
								<span>♛</span>
							{:else}
								<span>♙♙</span>
							{/if}
						</div>

						<div class="audience-text">
							<strong class="text-body-active">{item.title}</strong>
							<span class="text-caption-medium">{item.subtitle}</span>
						</div>
					</button>
				{/each}
			</div>
		</section>

		<section class="section persona-section">
			<div class="section-header compact">
				<div class="title-icon" aria-hidden="true">
					<span>◉</span>
				</div>

				<h2 class="text-title-middle">청중 페르소나</h2>
			</div>

			<div class="persona-control">
				<label class="control-label text-title-small">청중 규모</label>

				<SessionSlider
					mode="node"
					min={1}
					max={50}
					step={1}
					majorTicks={audienceSizeTicks}
					showCurrentTick
					bind:value={audienceSize}
				/>
			</div>

			<div class="level-grid">
				<div class="persona-control">
					<label class="control-label text-title-small">전문성 수준</label>

					<SegmentedControl
						items={levelItems}
						itemWidth="158px"
						bind:selected={expertiseLevel}
					/>
				</div>

				<div class="persona-control">
					<label class="control-label text-title-small">관심도 수준</label>

					<SegmentedControl
						items={levelItems}
						itemWidth="158px"
						bind:selected={interestLevel}
					/>
				</div>
			</div>
		</section>
	</div>
</SurfaceCard>

<style>
	.audience-card {
		display: flex;
		flex-direction: column;
		gap: 28px;
	}

	.section {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.section-header {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.section-header.compact {
		gap: var(--space-2);
	}

	.title-icon {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: rgba(0, 80, 255, 0.15);
		color: var(--primary);
		font-weight: var(--font-bold);
	}

	.section-help {
		margin-left: var(--space-5);
		color: var(--text-disabled);
	}

	.audience-type-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--space-5);
	}

	.audience-type {
		height: 100px;
		padding: var(--space-5) var(--space-2);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-secondary);
	}

	.audience-type.selected {
		border-color: var(--primary);
		color: var(--primary);
		box-shadow: 0 0 0 1px var(--primary) inset;
	}

	.audience-icon {
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 24px;
		line-height: 1;
	}

	.audience-text {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}

	.audience-text span {
		color: var(--text-secondary);
	}

	.persona-section {
		gap: 22px;
	}

	.persona-control {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.control-label {
		color: var(--text-primary);
	}

	.level-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-5);
	}

	@media (max-width: 1280px) {
		.audience-type-grid,
		.level-grid {
			grid-template-columns: 1fr;
		}
	}
</style>