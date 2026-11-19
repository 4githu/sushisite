<script lang="ts">
	import { type PaperTemplate, paperColors } from './paper';
	let {
		initial,
		onapply,
		label = '페이지 추가'
	}: {
		initial: PaperTemplate;
		onapply: (p: PaperTemplate, remember: boolean) => void;
		label?: string;
	} = $props();
	let pattern = $derived(initial.pattern),
		color = $derived(initial.color),
		remember = $state(false);
	const colorNames = { white: '흰 종이', yellow: '노란 종이', black: '검은 종이' };
</script>

<form
	class="paper-options"
	onsubmit={(e) => {
		e.preventDefault();
		onapply({ pattern, color }, remember);
	}}
>
	<header><strong>{label}</strong><span>용지 설정</span></header>
	<div class="paper-preview" aria-label="용지 미리보기">
		<div
			class="preview-sheet"
			class:ruled={pattern === 'ruled'}
			style:background-color={paperColors[color]}
			style:--rule-color={color === 'black' ? '#ffffff28' : '#c9c7b877'}
			aria-hidden="true"
		>
			<span></span>
		</div>
		<div class="preview-caption">
			<strong>{pattern === 'ruled' ? '줄 노트' : '백지'}</strong><span>{colorNames[color]}</span
			><small>A4 · 세로</small>
		</div>
	</div>
	<fieldset class="pattern-options">
		<legend>양식</legend
		>{#each [['ruled', '줄 노트'], ['blank', '백지']] as [value, name] (value)}<button
				type="button"
				class:chosen={pattern === value}
				aria-pressed={pattern === value}
				onclick={() => (pattern = value as PaperTemplate['pattern'])}
				><svg viewBox="0 0 20 24" aria-hidden="true"
					><rect x="3" y="2" width="14" height="20" rx="1" />{#if value === 'ruled'}<path
							d="M6 8h8M6 12h8M6 16h8"
						/>{/if}</svg
				>{name}<span class="choice-check" aria-hidden="true">{pattern === value ? '✓' : ''}</span
				></button
			>{/each}
	</fieldset>
	<fieldset class="color-options">
		<legend>종이 색</legend
		>{#each [['white', '흰 종이'], ['yellow', '노란 종이'], ['black', '검은 종이']] as [value, name] (value)}<button
				type="button"
				class:chosen={color === value}
				aria-pressed={color === value}
				onclick={() => (color = value as PaperTemplate['color'])}
				><span
					class="color-swatch"
					style:background={paperColors[value as keyof typeof paperColors]}
				></span>{name}</button
			>{/each}
	</fieldset>
	<footer>
		{#if label !== '기본값 저장'}<label
				><input type="checkbox" bind:checked={remember} />새 페이지 기본값으로 저장</label
			>{:else}<span class="default-hint">새 페이지에 적용</span>{/if}<button
			class="apply-paper"
			type="submit">{label}</button
		>
	</footer>
</form>

<style>
	.paper-options {
		width: 100%;
		max-width: calc(100vw - 20px);
		box-sizing: border-box;
		padding: 20px;
		background: white;
		border: 1px solid #e1e3e8;
		border-radius: 10px;
		color: #303238;
		font:
			12px 'Noto Sans KR',
			sans-serif;
		display: grid;
		gap: 18px;
	}
	.paper-options header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}
	.paper-options header strong {
		font-size: 15px;
		font-weight: 600;
	}
	.paper-options header > span {
		font-size: 10px;
		color: #8a8d96;
	}
	.paper-preview {
		display: flex;
		align-items: center;
		gap: 22px;
		padding: 14px 24px;
		background: #f3f4f6;
		border-radius: 6px;
	}
	.preview-sheet {
		width: 72px;
		height: 102px;
		position: relative;
		flex: none;
		box-shadow: 0 2px 6px #24252914;
		border: 1px solid #2425290a;
		overflow: hidden;
	}
	.preview-sheet.ruled span {
		position: absolute;
		inset: 26px 9px 9px;
		background: repeating-linear-gradient(
			transparent,
			transparent 8px,
			var(--rule-color) 8px,
			var(--rule-color) 9px
		);
	}
	.preview-caption {
		display: grid;
		gap: 7px;
	}
	.preview-caption strong {
		font-size: 12px;
		font-weight: 500;
	}
	.preview-caption span {
		font-size: 11px;
		color: #717681;
	}
	.preview-caption small {
		font-size: 10px;
		color: #969aa3;
	}
	.paper-options fieldset {
		padding: 0;
		margin: 0;
		border: 0;
		display: flex;
		gap: 8px;
		min-width: 0;
	}
	.paper-options legend {
		font-size: 11px;
		font-weight: 500;
		margin-bottom: 9px;
		color: #626772;
	}
	.paper-options button {
		cursor: pointer;
		font: inherit;
		color: inherit;
	}
	.pattern-options button {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 1;
		border: 1px solid #e1e3e8;
		border-radius: 5px;
		background: #fff;
		padding: 10px;
		font-size: 12px;
		min-width: 0;
	}
	.pattern-options button.chosen {
		border-color: #bd4e36;
		background: #fcf7f5;
	}
	.pattern-options svg {
		width: 18px;
		height: 23px;
		fill: none;
		stroke: #7c8089;
		stroke-width: 1.2;
		flex: none;
	}
	.choice-check {
		color: #bd4e36;
		margin-left: auto;
		font-size: 12px;
		width: 10px;
	}
	.color-options button {
		flex: 1;
		display: grid;
		justify-items: center;
		gap: 8px;
		padding: 5px 0;
		border: 0;
		background: none;
		font-size: 10px;
		color: #737884;
	}
	.color-swatch {
		display: block;
		width: 29px;
		height: 29px;
		border-radius: 50%;
		box-shadow: 0 0 0 1px #d9dce3;
		outline: 2px solid transparent;
		outline-offset: 3px;
	}
	.color-options button.chosen {
		color: #303238;
	}
	.color-options button.chosen .color-swatch {
		outline-color: #bd4e36;
	}
	.paper-options footer {
		border-top: 1px solid #eceef1;
		padding-top: 14px;
		display: grid;
		gap: 14px;
	}
	.paper-options footer label {
		display: flex;
		align-items: center;
		gap: 7px;
		font-size: 10px;
		color: #737884;
	}
	.paper-options input {
		accent-color: #bd4e36;
		width: 13px;
		height: 13px;
		margin: 0;
	}
	.apply-paper {
		width: 100%;
		border: 0;
		border-radius: 5px;
		background: #303238;
		color: white !important;
		min-height: 36px;
		font-size: 12px !important;
	}
	.default-hint {
		font-size: 10px;
		color: #8a8d96;
	}
	.paper-options button:focus-visible {
		outline: 2px solid #bd4e36;
		outline-offset: 3px;
	}
</style>
