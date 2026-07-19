<script lang="ts">
	let {} = $props();
</script>

<section class="button-section">

	<h1 class="text-title-main title">
		BUTTON AND STATES
	</h1>

	<div class="panel">

		<div></div>

		<div class="text-title-small center">
			CTA
		</div>

		<div class="text-title-small center">
			Basic
		</div>

		<div class="text-body-medium row-title">
			Default
		</div>

		<button class="cta default text-button-start">
			Button
		</button>

		<button class="basic default text-button-start">
			Button
		</button>

		<div class="text-body-medium row-title">
			Hover (Focused)
		</div>

		<button class="cta hover text-button-start">
			Button
		</button>

		<button class="basic hover text-button-start">
			Button
		</button>

		<div class="text-body-medium row-title">
			Selected (Pressed)
		</div>

		<button class="cta active text-button-start">
			Button
		</button>

		<button class="basic disabled text-button-start">
			Button
		</button>

	</div>

</section>

<style>

.button-section{
	display:flex;
	flex-direction:column;
	gap:32px;
}

.title{
	color:var(--text-primary);
}

.panel{

	background:var(--cool-grey);

	border-radius:var(--radius-xl);

	padding:40px;

	display:grid;

	grid-template-columns:180px 340px 340px;

	row-gap:48px;

	column-gap:28px;

	align-items:center;

}

.center{

	text-align:center;

	color:white;

}

.row-title{

	color:white;

}

button{

	height:56px;

	border-radius:var(--radius-xl);

	transition:.15s;

}

.cta{

	background:var(--primary);

	color:var(--text-on-primary);

}

.cta.hover{

	background:var(--primary-hover);

}

.cta.active{

	background:var(--primary-active);

}

.basic{

	background:transparent;

	color:white;

	border:2px solid white;

}

.basic.hover{

	border-width:4px;

}

.basic.disabled{

	background:rgba(255,255,255,.3);

}

</style>