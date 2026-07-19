<!-- SystemColorSection.svelte -->

<script lang="ts">
	let {} = $props();
</script>

<section class="section">

	<h1 class="text-title-main title">
		SYSTEM COLOR
	</h1>

	<div class="grid">

		<!-- Cool Grey -->
		<div class="palette">

			<h2 class="text-title-small">Cool Grey</h2>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-light)"><span>50</span></div><div class="info"><div class="text-body-medium">Light</div><div class="text-caption">#F4F5F7</div><div class="text-caption">rgb(245,245,247)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-light-hover)"><span>100</span></div><div class="info"><div class="text-body-medium">Light :hover</div><div class="text-caption">#EFF0F3</div><div class="text-caption">rgb(239,240,243)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-light-active)"></div><div class="info"><div class="text-body-medium">Light :active</div><div class="text-caption">#DEE0E5</div><div class="text-caption">rgb(222,224,229)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey)"></div><div class="info"><div class="text-body-medium">Normal</div><div class="text-caption">#969CAC</div><div class="text-caption">rgb(150,156,172)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-hover)"></div><div class="info"><div class="text-body-medium">Normal :hover</div><div class="text-caption">#878C9B</div><div class="text-caption">rgb(135,140,155)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-active)"></div><div class="info"><div class="text-body-medium">Normal :active</div><div class="text-caption">#787D8A</div><div class="text-caption">rgb(120,125,138)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-dark)"></div><div class="info"><div class="text-body-medium">Dark</div><div class="text-caption">#717581</div><div class="text-caption">rgb(113,117,129)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-dark-hover)"></div><div class="info"><div class="text-body-medium">Dark :hover</div><div class="text-caption">#5A5E67</div><div class="text-caption">rgb(90,94,103)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-dark-active)"></div><div class="info"><div class="text-body-medium">Dark :active</div><div class="text-caption">#44464D</div><div class="text-caption">rgb(68,70,77)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--cool-grey-darker)"></div><div class="info"><div class="text-body-medium">Darker</div><div class="text-caption">#35373C</div><div class="text-caption">rgb(53,55,60)</div></div></div>

		</div>

		<!-- Blue -->
		<div class="palette">

			<h2 class="text-title-small">Blue</h2>

			<div class="swatch"><div class="preview" style="background:var(--blue-light)"></div><div class="info"><div class="text-body-medium">Light</div><div class="text-caption">#E6EBFF</div><div class="text-caption">rgb(230,235,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-light-hover)"></div><div class="info"><div class="text-body-medium">Light :hover</div><div class="text-caption">#D9E0FF</div><div class="text-caption">rgb(217,224,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-light-active)"></div><div class="info"><div class="text-body-medium">Light :active</div><div class="text-caption">#B0C0FF</div><div class="text-caption">rgb(176,192,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue)"></div><div class="info"><div class="text-body-medium">Normal</div><div class="text-caption">#0033FF</div><div class="text-caption">rgb(0,51,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-hover)"></div><div class="info"><div class="text-body-medium">Normal :hover</div><div class="text-caption">#002EE6</div><div class="text-caption">rgb(0,46,230)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-active)"></div><div class="info"><div class="text-body-medium">Normal :active</div><div class="text-caption">#0029CC</div><div class="text-caption">rgb(0,41,204)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-dark)"></div><div class="info"><div class="text-body-medium">Dark</div><div class="text-caption">#0026BF</div><div class="text-caption">rgb(0,38,191)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-dark-hover)"></div><div class="info"><div class="text-body-medium">Dark :hover</div><div class="text-caption">#001F99</div><div class="text-caption">rgb(0,31,153)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-dark-active)"></div><div class="info"><div class="text-body-medium">Dark :active</div><div class="text-caption">#001773</div><div class="text-caption">rgb(0,23,115)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--blue-darker)"></div><div class="info"><div class="text-body-medium">Darker</div><div class="text-caption">#001259</div><div class="text-caption">rgb(0,18,89)</div></div></div>

		</div>
        
        		<!-- Purple -->
		<div class="palette">

			<h2 class="text-title-small">
				Purple
			</h2>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-light);"></div>
				<div class="info">
					<div class="text-body-medium">Light</div>
					<div class="text-caption">#F2F2FF</div>
					<div class="text-caption">rgb(242,242,255)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-light-hover);"></div>
				<div class="info">
					<div class="text-body-medium">Light :hover</div>
					<div class="text-caption">#ECECFF</div>
					<div class="text-caption">rgb(236,236,255)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-light-active);"></div>
				<div class="info">
					<div class="text-body-medium">Light :active</div>
					<div class="text-caption">#D8D7FF</div>
					<div class="text-caption">rgb(216,215,255)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple);"></div>
				<div class="info">
					<div class="text-body-medium">Normal</div>
					<div class="text-caption">#807DFE</div>
					<div class="text-caption">rgb(128,125,254)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-hover);"></div>
				<div class="info">
					<div class="text-body-medium">Normal :hover</div>
					<div class="text-caption">#7371E5</div>
					<div class="text-caption">rgb(115,113,229)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-active);"></div>
				<div class="info">
					<div class="text-body-medium">Normal :active</div>
					<div class="text-caption">#6664CB</div>
					<div class="text-caption">rgb(102,100,203)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-dark);"></div>
				<div class="info">
					<div class="text-body-medium">Dark</div>
					<div class="text-caption">#605EBF</div>
					<div class="text-caption">rgb(96,94,191)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-dark-hover);"></div>
				<div class="info">
					<div class="text-body-medium">Dark :hover</div>
					<div class="text-caption">#4D4B98</div>
					<div class="text-caption">rgb(77,75,152)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-dark-active);"></div>
				<div class="info">
					<div class="text-body-medium">Dark :active</div>
					<div class="text-caption">#3A3872</div>
					<div class="text-caption">rgb(58,56,114)</div>
				</div>
			</div>

			<div class="swatch">
				<div class="preview" style="background:var(--purple-darker);"></div>
				<div class="info">
					<div class="text-body-medium">Darker</div>
					<div class="text-caption">#2D2C59</div>
					<div class="text-caption">rgb(45,44,89)</div>
				</div>
			</div>

		</div>

		<!-- Accent Purple -->
		<div class="palette">

			<h2 class="text-title-small">
				Accent Purple
			</h2>

			<div class="swatch"><div class="preview" style="background:var(--accent-light);"></div><div class="info"><div class="text-body-medium">Light</div><div class="text-caption">#F3E9FF</div><div class="text-caption">rgb(243,233,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-light-hover);"></div><div class="info"><div class="text-body-medium">Light :hover</div><div class="text-caption">#EDDEFF</div><div class="text-caption">rgb(237,222,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-light-active);"></div><div class="info"><div class="text-body-medium">Light :active</div><div class="text-caption">#D9BBFF</div><div class="text-caption">rgb(217,187,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent);"></div><div class="info"><div class="text-body-medium">Normal</div><div class="text-caption">#8624FF</div><div class="text-caption">rgb(134,36,255)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-hover);"></div><div class="info"><div class="text-body-medium">Normal :hover</div><div class="text-caption">#7920E6</div><div class="text-caption">rgb(121,32,230)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-active);"></div><div class="info"><div class="text-body-medium">Normal :active</div><div class="text-caption">#6B1DCC</div><div class="text-caption">rgb(107,29,204)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-dark);"></div><div class="info"><div class="text-body-medium">Dark</div><div class="text-caption">#651BBF</div><div class="text-caption">rgb(101,27,191)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-dark-hover);"></div><div class="info"><div class="text-body-medium">Dark :hover</div><div class="text-caption">#501699</div><div class="text-caption">rgb(80,22,153)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-dark-active);"></div><div class="info"><div class="text-body-medium">Dark :active</div><div class="text-caption">#3C1073</div><div class="text-caption">rgb(60,16,115)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--accent-darker);"></div><div class="info"><div class="text-body-medium">Darker</div><div class="text-caption">#2F0D59</div><div class="text-caption">rgb(47,13,89)</div></div></div>

		</div>

		<!-- Yellow -->
		<div class="palette">

			<h2 class="text-title-small">
				Yellow
			</h2>

			<div class="swatch"><div class="preview" style="background:var(--lime-light);"></div><div class="info"><div class="text-body-medium">Light</div><div class="text-caption">#FAFFEF</div><div class="text-caption">rgb(250,255,239)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-light-hover);"></div><div class="info"><div class="text-body-medium">Light :hover</div><div class="text-caption">#F8FFE7</div><div class="text-caption">rgb(248,255,231)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-light-active);"></div><div class="info"><div class="text-body-medium">Light :active</div><div class="text-caption">#F0FFCD</div><div class="text-caption">rgb(240,255,205)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime);"></div><div class="info"><div class="text-body-medium">Normal</div><div class="text-caption">#CFFF5E</div><div class="text-caption">rgb(207,255,94)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-hover);"></div><div class="info"><div class="text-body-medium">Normal :hover</div><div class="text-caption">#BAE655</div><div class="text-caption">rgb(186,230,85)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-active);"></div><div class="info"><div class="text-body-medium">Normal :active</div><div class="text-caption">#A6CC4B</div><div class="text-caption">rgb(166,204,75)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-dark);"></div><div class="info"><div class="text-body-medium">Dark</div><div class="text-caption">#9BBF47</div><div class="text-caption">rgb(155,191,71)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-dark-hover);"></div><div class="info"><div class="text-body-medium">Dark :hover</div><div class="text-caption">#7C9938</div><div class="text-caption">rgb(124,153,56)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-dark-active);"></div><div class="info"><div class="text-body-medium">Dark :active</div><div class="text-caption">#5D732A</div><div class="text-caption">rgb(93,115,42)</div></div></div>

			<div class="swatch"><div class="preview" style="background:var(--lime-darker);"></div><div class="info"><div class="text-body-medium">Darker</div><div class="text-caption">#485921</div><div class="text-caption">rgb(72,89,33)</div></div></div>

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
	display:grid;
	grid-template-columns:1fr 1fr;
	gap:48px;
}

.palette{
	display:flex;
	flex-direction:column;
	gap:16px;
}

.swatch{
	display:grid;
	grid-template-columns:160px 1fr;
	gap:16px;
	align-items:center;
}

.preview{
	width:160px;
	height:56px;
	border-radius:var(--radius-md);
	border:1px solid var(--border);
	display:flex;
	align-items:center;
	justify-content:center;
}

.preview span{
	font-size:10px;
	font-weight:600;
}

.info{
	display:flex;
	flex-direction:column;
	gap:2px;
}

</style>