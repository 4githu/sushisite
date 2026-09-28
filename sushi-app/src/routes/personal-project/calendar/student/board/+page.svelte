<script lang="ts">
	import StudentCommunity from '$lib/personal-project/shared/StudentCommunity.svelte';
	import '$lib/personal-project/student/student.css';
</script>

<svelte:head><title>학과 게시판 · NETAQ</title></svelte:head>
<div class="student-page">
	<header class="page-heading">
		<div>
			<span class="eyebrow">CAMPUS / COMMUNITY</span>
			<h1>학과 게시판</h1>
			<p class="muted">학교·학과 설정에 맞는 소식과 사용자 편집 이수규정을 나눠보세요.</p>
		</div>
		<a class="button" href="/personal-project/calendar/student">내 학교·학과 설정</a>
	</header>
	<StudentCommunity />
</div>
