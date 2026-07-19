<script lang="ts">
	let {} = $props();
</script>

<section class="shadow-section">

	<h1 class="text-title-main title">
		SHADOW
	</h1>

	<div class="shadow-grid">

		<div class="shadow-card">

			<div class="card-title text-title-small">
				Card Shadow
			</div>

			<div class="text-body">
				box-shadow
			</div>

			<div class="text-caption">
				var(--shadow-card)
			</div>

		</div>

		<div class="shadow-card">

			<div class="card-title text-title-small">
				Preview
			</div>

			<div class="dummy">

				<div class="dummy-card">

					<div class="text-body-medium">
						Shadow Preview
					</div>

				</div>

			</div>

		</div>

	</div>

</section>

<style>

.shadow-section{

	display:flex;

	flex-direction:column;

	gap:32px;

}

.title{

	color:var(--text-primary);

}

.shadow-grid{

	display:grid;

	grid-template-columns:1fr 1fr;

	gap:32px;

}

.shadow-card{

	background:var(--surface);

	border-radius:var(--radius-md);

	padding:32px;

	box-shadow:var(--shadow-card);

	min-height:260px;

	display:flex;

	flex-direction:column;

	gap:20px;

}

.card-title{

	margin-bottom:8px;

}

.dummy{

	flex:1;

	display:flex;

	justify-content:center;

	align-items:center;

}

.dummy-card{

	width:220px;

	height:120px;

	background:var(--surface);

	border-radius:var(--radius-md);

	box-shadow:var(--shadow-card);

	display:flex;

	align-items:center;

	justify-content:center;

}

</style>