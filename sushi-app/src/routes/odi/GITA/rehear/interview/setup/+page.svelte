<script lang="ts">
	import Icon from '../../_components/Icon.svelte';
	import PageHeader from '../../_components/PageHeader.svelte';
</script>

<div class="rehear-page">
	<PageHeader
		title="면접 연습 설정"
		description="면접 유형, 지원 직무, 질문 난이도를 설정하는 화면으로 확장할 예정이에요."
	/>

	<section class="rehear-card rehear-interview-card">
		<span class="rehear-title-icon"><Icon name="briefcase" size={24} /></span>
		<div>
			<h2>면접 플로우 준비 중</h2>
			<p>
				발표 연습은 <strong>/rehear/presentation/setup</strong> 아래로 분리했고, 면접 연습은 이 주소를
				기준으로 별도 설정 단계를 붙이면 됩니다.
			</p>
			<div class="rehear-actions inline">
				<a class="rehear-secondary-button" href="/rehear">홈으로</a>
				<a class="rehear-primary-button" href="/rehear/presentation/setup">
					<span>발표 연습으로 이동</span>
					<Icon name="arrow-right" size={22} />
				</a>
			</div>
		</div>
	</section>
</div>
