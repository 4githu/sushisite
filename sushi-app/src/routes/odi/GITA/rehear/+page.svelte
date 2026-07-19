<script lang="ts">
	import Icon from './_components/Icon.svelte';

	const summaryStats = [
		{
			icon: 'chart',
			label: '나의 평균 점수',
			value: '81점',
			detail: '지난 2주간 평균',
			tone: 'green'
		},
		{
			icon: 'wand',
			label: '나의 강점 스킬',
			value: '시선 분배',
			detail: '우수(상위 11%)',
			tone: 'violet'
		},
		{
			icon: 'flame',
			label: '연속 연습',
			value: '5일',
			detail: '연속 기록 갱신 중!',
			tone: 'amber'
		}
	] as const;

	const recentSessions = [
		{
			title: '제품 로드맵 발표 및 Q&A',
			people: '6인',
			time: '37:53',
			score: 86,
			rating: '우수'
		},
		{
			title: '분기 실적 리뷰 발표',
			people: '10인',
			time: '18:38',
			score: 78,
			rating: '보통'
		},
		{
			title: '신제품 아이디어 피칭',
			people: '6인',
			time: '21:17',
			score: 75,
			rating: '보통'
		}
	] as const;

	const trainings = [
		{
			title: '습관어 줄이기',
			description:
				'자주 사용하는 추임새와 불필요한 반복 표현을 줄여 메시지를 더 명확하게 전달해요.',
			category: '명확도 훈련',
			level: '난이도 : 쉬움',
			tone: 'green'
		},
		{
			title: '적정 말하기 속도 유지',
			description: '말하기 속도를 안정적으로 유지하여 전달력을 높이도록 연습해요.',
			category: '몰입도 훈련',
			level: '난이도 : 보통',
			tone: 'blue'
		},
		{
			title: 'Q&A 답변 구조 강화',
			description: '두괄식으로 핵심을 먼저 말하고, 근거를 덧붙이는 답변 구조를 학습해요.',
			category: '신뢰도 훈련',
			level: '난이도 : 보통',
			tone: 'violet'
		}
	] as const;

	const dates = ['6/8', '6/12', '6/16', '6/20', '6/24'];
</script>

<div class="rehear-home">
	<header class="rehear-home-header">
		<div>
			<h1>좋은 아침이에요, 리히어님 ✋</h1>
			<p>꾸준한 연습이 자신감을 만듭니다. 오늘도 한 걸음 더 성장해요!</p>
		</div>

		<div class="rehear-home-tabs" aria-label="개인 메뉴">
			<a href="/rehear">
				<Icon name="calendar" size={22} />
				<span>나의 일정</span>
			</a>
			<a href="/rehear">
				<Icon name="bell" size={22} />
				<span>알림</span>
			</a>
		</div>
	</header>

	<section class="rehear-summary-grid" aria-label="나의 요약 지표">
		<article class="rehear-dashboard-card rehear-summary-card level">
			<span class="rehear-dashboard-icon blue-soft"><Icon name="leaf" size={30} /></span>
			<div>
				<p>나의 단계 : 새싹 보이스</p>
				<div class="rehear-level-progress"><span></span></div>
				<span>다음 레벨업까지 52 Point</span>
			</div>
		</article>

		{#each summaryStats as card}
			<article class="rehear-dashboard-card rehear-summary-card">
				<span class={`rehear-dashboard-icon ${card.tone}`}><Icon name={card.icon} size={30} /></span
				>
				<div>
					<p>{card.label}</p>
					<strong>{card.value}</strong>
					<span>{card.detail}</span>
				</div>
			</article>
		{/each}
	</section>

	<div class="rehear-dashboard-main">
		<section class="rehear-dashboard-card rehear-session-card">
			<div class="rehear-card-head">
				<h2>최근 세션</h2>
				<a href="/rehear">
					<span>전체 보기</span>
					<Icon name="arrow-right" size={18} />
				</a>
			</div>

			<div class="rehear-session-list">
				{#each recentSessions as session, index}
					<article class="rehear-session-item" class:featured={index === 0}>
						<span class="rehear-session-rank">{index + 1}</span>
						<div>
							<h3>{session.title}</h3>
							<p>
								<span><Icon name="calendar" size={16} />2026.06.26 (금) 14:00</span>
								<span><Icon name="users" size={16} />{session.people}</span>
								<span><Icon name="clock" size={16} />{session.time}</span>
							</p>
						</div>
						<strong>
							{session.score}
							<span>{session.rating}</span>
						</strong>
					</article>
				{/each}
			</div>
		</section>

		<section class="rehear-dashboard-card rehear-chart-card">
			<div class="rehear-card-head">
				<div>
					<h2>E/V/C 요소 분석</h2>
					<div class="rehear-chart-legend">
						<span><i class="engagement"></i>몰입도</span>
						<span><i class="trust"></i>신뢰도</span>
						<span><i class="clarity"></i>명확도</span>
					</div>
				</div>
				<button type="button" class="rehear-period-button">
					최근 2주
					<Icon name="chevron-down" size={18} />
				</button>
			</div>

			<div class="rehear-line-chart" aria-label="최근 2주 EVC 요소 분석">
				<div class="rehear-chart-yaxis" aria-hidden="true">
					<span>100</span>
					<span>50</span>
					<span>0</span>
				</div>
				<div class="rehear-chart-canvas">
					<svg viewBox="0 0 600 180" role="img" aria-label="몰입도, 신뢰도, 명확도 추이">
						<defs>
							<linearGradient id="engagement-fill" x1="0" x2="0" y1="0" y2="1">
								<stop offset="0%" stop-color="#0048ff" stop-opacity="0.18" />
								<stop offset="100%" stop-color="#0048ff" stop-opacity="0.02" />
							</linearGradient>
							<linearGradient id="trust-fill" x1="0" x2="0" y1="0" y2="1">
								<stop offset="0%" stop-color="#b6eb2f" stop-opacity="0.3" />
								<stop offset="100%" stop-color="#b6eb2f" stop-opacity="0.04" />
							</linearGradient>
						</defs>
						<g class="grid-lines">
							<path d="M0 20H600" />
							<path d="M0 60H600" />
							<path d="M0 100H600" />
							<path d="M0 140H600" />
							<path d="M0 180H600" />
							<path d="M40 0V180" />
							<path d="M170 0V180" />
							<path d="M300 0V180" />
							<path d="M430 0V180" />
							<path d="M560 0V180" />
						</g>
						<path
							class="area trust"
							d="M0 96 C55 94 78 112 120 98 S210 116 260 102 S350 88 390 92 S470 76 520 86 S575 76 600 82 L600 180 L0 180Z"
						/>
						<path
							class="area engagement"
							d="M0 88 C70 88 85 80 130 76 S215 98 250 76 S335 82 380 70 S460 50 500 66 S560 86 600 72 L600 180 L0 180Z"
						/>
						<path
							class="line trust"
							d="M0 96 C55 94 78 112 120 98 S210 116 260 102 S350 88 390 92 S470 76 520 86 S575 76 600 82"
						/>
						<path
							class="line clarity"
							d="M0 88 C66 88 98 70 140 84 S206 108 250 86 S310 62 360 68 S430 34 500 52 S555 44 600 40"
						/>
						<path
							class="line engagement"
							d="M0 88 C70 88 85 80 130 76 S215 98 250 76 S335 82 380 70 S460 50 500 66 S560 86 600 72"
						/>
					</svg>
					<div class="rehear-chart-dates">
						{#each dates as date}
							<span>{date}</span>
						{/each}
					</div>
				</div>
			</div>

			<div class="rehear-insight-note">
				<Icon name="chart" size={44} />
				<p>
					<strong>전반적인 전달력이 꾸준히 향상하고 있어요!</strong>
					<span
						>몰입도와 신뢰도가 최근 눈에 띄게 개선되었어요. 시선 처리와 메시지 구조가 더 명확해진
						영향이에요. 다음 단계로는 표현의 생동감을 올려 명확도를 성장한다면 설득력이 한층 강화될
						거예요.</span
					>
				</p>
			</div>
		</section>

		<aside class="rehear-dashboard-card rehear-insight-card">
			<h2>오늘의 인사이트</h2>
			<blockquote>
				<p>설득은 말하는 사람의<br />신뢰에서 시작된다.</p>
				<cite>— Aristotle</cite>
			</blockquote>
			<span>좋은 발표는 청중이 믿고 따라올 수 있는 흐름을 만드는 것입니다.</span>

			<div class="rehear-goal-card">
				<h3>이번 주 목표</h3>
				<div class="rehear-goal-box">
					<div class="rehear-goal-title">
						<Icon name="target" size={22} />
						<strong>연속 5회 평균 점수 85점 달성</strong>
					</div>
					<div class="rehear-goal-progress"><span></span></div>
					<p>현재 86점 · 남은 세션 4회</p>
				</div>
			</div>
		</aside>
	</div>

	<section class="rehear-dashboard-card rehear-training-card">
		<div class="rehear-card-head">
			<div>
				<h2>추천 훈련</h2>
				<p>최근 세션 분석을 바탕으로 맞춤 추천해드려요.</p>
			</div>
			<a href="/rehear/presentation/setup">
				<span>훈련하러 가기</span>
				<Icon name="arrow-right" size={18} />
			</a>
		</div>

		<div class="rehear-training-list">
			{#each trainings as training}
				<article class="rehear-training-item">
					<span class="rehear-training-flag"><Icon name="flag" size={22} /></span>
					<div>
						<h3>{training.title}</h3>
						<p>{training.description}</p>
						<div class="rehear-chip-row">
							<span class={training.tone}>{training.category}</span>
							<span class="level">{training.level}</span>
						</div>
					</div>
					<a href="/rehear/presentation/setup">훈련 시작</a>
				</article>
			{/each}
		</div>
	</section>
</div>
