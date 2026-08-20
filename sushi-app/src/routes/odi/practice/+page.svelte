<script lang="ts">
	import { voice_selection } from "$lib/odi/icons";
</script>

<svelte:head><title>My Practice | Re:hear</title></svelte:head>

<main class="coming-soon-page">
	<section class="coming-soon-card">
		<div class="icon-wrap"><img src={voice_selection} alt="" /></div>
		<p class="eyebrow">My Practice</p>
		<h1>준비 중입니다</h1>
		<p>나에게 필요한 연습을 추천하고 진행 상황을 모아보는 공간을 만들고 있어요.</p>
		<a href="/odi">홈으로 돌아가기</a>
	</section>
</main>

<style>
	.coming-soon-page { min-height:100vh; display:grid; place-items:center; padding:40px 24px; background:linear-gradient(145deg,#f7f5ff,#fff 55%,#f0f7ff); }
	.coming-soon-card { width:min(620px,100%); padding:64px 48px; text-align:center; border:1px solid var(--cool-grey-light-active); border-radius:24px; background:rgb(from var(--surface) r g b / 92%); box-shadow:var(--shadow-sm); }
	.icon-wrap { width:88px; height:88px; margin:0 auto 24px; display:grid; place-items:center; border-radius:24px; background:var(--purple-light); }
	.icon-wrap img { width:48px; height:48px; }
	.eyebrow { margin:0 0 12px; color:var(--primary); font-size:13px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
	h1 { margin:0; color:var(--text-primary); font-size:32px; }
	p:not(.eyebrow) { margin:16px auto 30px; max-width:420px; color:var(--text-secondary); line-height:1.7; }
	a { display:inline-flex; height:48px; padding:0 24px; align-items:center; border-radius:10px; background:var(--primary); color:var(--text-on-primary); font-weight:700; text-decoration:none; }
	@media(max-width:640px){.coming-soon-card{padding:48px 24px}}
</style>
