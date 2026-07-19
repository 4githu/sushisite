<script lang="ts">
	let {} = $props();
</script>

<section class="typography-section">

	<h1 class="text-title-main title">
		TYPOGRAPHY
	</h1>

	<div class="typography-grid">

		<!-- Title -->
		<div class="group">

			<h2 class="text-title-small group-title">
				Title
			</h2>

			<div class="sample">
				<div class="text-title-main">Main</div>
				<div class="meta text-caption">42 / Bold</div>
			</div>

			<div class="sample">
				<div class="text-title-middle">Middle</div>
				<div class="meta text-caption">26 / Bold</div>
			</div>

			<div class="sample">
				<div class="text-title-small">Small</div>
				<div class="meta text-caption">20 / Bold</div>
			</div>

			<div class="sample">
				<div class="text-title-xs">Extra Small</div>
				<div class="meta text-caption">18 / Bold</div>
			</div>

		</div>

		<!-- Body -->
		<div class="group">

			<h2 class="text-title-small group-title">
				Body
			</h2>

			<div class="sample">
				<div class="text-body">
					Basic rg
				</div>

				<div class="meta text-caption">
					18 / Regular
				</div>
			</div>

			<div class="sample">
				<div class="text-body-medium">
					Basic md
				</div>

				<div class="meta text-caption">
					18 / Medium
				</div>
			</div>

			<div class="sample">
				<div class="text-body-active">
					Basic active
				</div>

				<div class="meta text-caption">
					18 / SemiBold
				</div>
			</div>

			<div class="sample">
				<div class="text-body-bold">
					Basic bd
				</div>

				<div class="meta text-caption">
					22 / Bold
				</div>
			</div>

			<div class="sample">
				<div class="text-body-bold-xl">
					Main
				</div>

				<div class="meta text-caption">
					32 / Bold
				</div>
			</div>

		</div>

		<!-- Button -->
		<div class="group">

			<h2 class="text-title-small group-title">
				Button
			</h2>

			<div class="sample">
				<div class="text-button">
					Button
				</div>

				<div class="meta text-caption">
					18 / Medium
				</div>
			</div>

			<div class="sample">
				<div class="text-button-start">
					Start
				</div>

				<div class="meta text-caption">
					22 / Medium
				</div>
			</div>

		</div>

		<!-- Caption -->
		<div class="group">

			<h2 class="text-title-small group-title">
				Caption
			</h2>

			<div class="sample">
				<div class="text-caption-nav">
					Navigation
				</div>

				<div class="meta text-caption">
					14 / Medium
				</div>
			</div>

			<div class="sample">
				<div class="text-caption">
					Caption
				</div>

				<div class="meta text-caption">
					16 / Regular
				</div>
			</div>

			<div class="sample">
				<div class="text-caption-medium">
					Caption Medium
				</div>

				<div class="meta text-caption">
					16 / Medium
				</div>
			</div>

			<div class="sample">
				<div class="text-caption-main">
					Main Caption
				</div>

				<div class="meta text-caption">
					20 / Medium
				</div>
			</div>

		</div>

	</div>

</section>

<style>

.typography-section{
	display:flex;
	flex-direction:column;
	gap:32px;
}

.title{
	color:var(--text-primary);
}

.typography-grid{
	display:grid;
	grid-template-columns:repeat(2,1fr);
	gap:48px;
}

.group{
	display:flex;
	flex-direction:column;
	gap:18px;
}

.group-title{
	padding-bottom:8px;
	border-bottom:1px solid var(--border);
}

.sample{
	padding:16px 0;
	border-bottom:1px solid var(--border);
	display:flex;
	flex-direction:column;
	gap:8px;
}

.meta{
	color:var(--text-secondary);
}

</style>