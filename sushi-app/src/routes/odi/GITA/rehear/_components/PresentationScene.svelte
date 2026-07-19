<div class="rehear-presentation-scene" aria-label="Presentation practice scene" role="img">
	<div class="rehear-scene-window"></div>
	<div class="rehear-presenter">
		<span class="head"></span>
		<span class="body"></span>
		<span class="arm"></span>
		<span class="podium"></span>
	</div>
	<div class="rehear-screen">
		<div class="screen-title">Presentation</div>
		<div class="screen-list">
			<span></span>
			<span></span>
			<span></span>
		</div>
		<div class="pie">
			<span></span>
		</div>
		<div class="bars">
			<span></span>
			<span></span>
			<span></span>
			<span></span>
			<span></span>
		</div>
		<div class="info-card one"></div>
		<div class="info-card two"></div>
	</div>
	<div class="rehear-audience">
		{#each Array(7) as _, index}
			<span class={`person person-${index + 1}`}></span>
		{/each}
	</div>
</div>
