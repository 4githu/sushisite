<!-- BrandSection.svelte -->

<script lang="ts">
	let {} = $props();
</script>

<section class="section">

	<h1 class="text-title-main title">
		BRAND COLOR
	</h1>

	<div class="grid">

		<div class="hero">

			<div class="text-caption hex lime">
				#CFFF5E
			</div>

			<div class="logo lime">
				Re:hear
			</div>

			<div class="text-caption-main lime">
				Ink black
			</div>

		</div>

		<div class="card navy">

			<div class="text-caption">
				#050632
			</div>

			<div class="logo">
				Re:hear
			</div>

			<div class="text-caption-main">
				Deep navy
			</div>

		</div>

		<div class="card blue">

			<div class="text-caption">
				#0033FF
			</div>

			<div class="logo">
				Re:hear
			</div>

			<div class="text-caption-main">
				Bright indigo
			</div>

		</div>

		<div class="card white">

			<div class="text-caption">
				#FAFAF8
			</div>

			<div class="logo dark">
				Re:hear
			</div>

			<div class="text-caption-main dark">
				Off white
			</div>

		</div>

		<div class="row purple">

			<div>

				<div class="logo">
					Re:hear
				</div>

				<div class="text-caption-main">
					Soft periwinkle
				</div>

			</div>

			<div class="text-caption">
				#807DFE
			</div>

		</div>

		<div class="row lime-row">

			<div>

				<div class="logo dark">
					Re:hear
				</div>

				<div class="text-caption-main dark">
					Neon lime
				</div>

			</div>

			<div class="text-caption dark">
				#CFFF5E
			</div>

		</div>

		<div class="bar grey-light">
			<div>
				<div class="logo">Re:hear</div>
				<div class="text-caption-main">Bright indigo</div>
			</div>
			<div>#DEE0E5</div>
		</div>

		<div class="bar grey">
			<div>
				<div class="logo">Re:hear</div>
				<div class="text-caption-main">Bright indigo</div>
			</div>
			<div>#969CAC</div>
		</div>

		<div class="bar grey-dark">
			<div>
				<div class="logo">Re:hear</div>
				<div class="text-caption-main">Bright indigo</div>
			</div>
			<div>#5A5E67</div>
		</div>

		<div class="bar grey-darker">
			<div>
				<div class="logo">Re:hear</div>
				<div class="text-caption-main">Bright indigo</div>
			</div>
			<div>#35373C</div>
		</div>

	</div>

</section>

<style>

.section{

	display:flex;

	flex-direction:column;

	gap:32px;

}

.title{

	color:var(--text-primary);

}

.grid{

	width:760px;

	display:grid;

	grid-template-columns:1fr 1fr 1fr;

	gap:12px;

}

.hero{

	grid-column:1/4;

	height:155px;

	border-radius:10px;

	background:var(--brand-black);

	padding:20px;

	display:flex;

	flex-direction:column;

	justify-content:flex-end;

}

.hero .logo{

	font-size:32px;

}

.card{

	height:240px;

	padding:18px;

	border-radius:10px;

	display:flex;

	flex-direction:column;

	justify-content:flex-start;

	gap:8px;

}

.navy{

	background:var(--brand-dark);

	color:white;

}

.blue{

	background:var(--brand-primary);

	color:white;

}

.white{

	background:var(--brand-off-white);

	border:1px solid var(--border);

}

.dark{

	color:var(--brand-black);

}

.lime{

	color:var(--brand-lime);

}

.row{

	height:74px;

	border-radius:10px;

	padding:18px;

	display:flex;

	align-items:center;

	justify-content:space-between;

}

.purple{

	grid-column:1/3;

	background:var(--purple);

	color:white;

}

.lime-row{

	background:var(--brand-lime);

	color:var(--brand-black);

}

.bar{

	grid-column:1/4;

	height:74px;

	border-radius:10px;

	padding:18px;

	display:flex;

	align-items:center;

	justify-content:space-between;

	color:white;

}

.grey-light{

	background:var(--cool-grey-light-active);

}

.grey{

	background:var(--cool-grey);

}

.grey-dark{

	background:var(--cool-grey-dark-hover);

}

.grey-darker{

	background:var(--cool-grey-darker);

}

.logo{

	font-size:32px;

	font-weight:600;

}

</style>