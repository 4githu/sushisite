<script lang="ts">
	let {} = $props();
</script>

<section class="radius-section">

	<h1 class="text-title-main title">
		RADIUS
	</h1>

	<div class="radius-grid">

		<div class="radius-card radius-xl">

			<div class="text-body-bold">40</div>

			<div class="text-caption">
				--radius-xl
			</div>

		</div>

		<div class="radius-card radius-md">

			<div class="text-body-bold">16</div>

			<div class="text-caption">
				--radius-md
			</div>

		</div>

		<div class="radius-card radius-sm">

			<div class="text-body-bold">8</div>

			<div class="text-caption">
				--radius-sm
			</div>

		</div>

	</div>

</section>

<style>

.radius-section{

	display:flex;

	flex-direction:column;

	gap:32px;

}

.title{

	color:var(--text-primary);

}

.radius-grid{

	display:grid;

	grid-template-columns:repeat(3,1fr);

	gap:32px;

}

.radius-card{

	height:280px;

	background:var(--surface);

	box-shadow:var(--shadow-card);

	border:2px solid var(--blue);

	display:flex;

	flex-direction:column;

	align-items:flex-start;

	justify-content:flex-start;

	padding:24px;

}

.radius-xl{

	border-radius:var(--radius-xl);

}

.radius-md{

	border-radius:var(--radius-md);

}

.radius-sm{

	border-radius:var(--radius-sm);

}

</style>