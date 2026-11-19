<script lang="ts">
	import { onMount } from 'svelte';
	let { onclose }: { onclose: () => void } = $props();
	let events = $state<string[]>([]),
		signal = $state('버튼을 누르기 전·후의 신호를 확인하세요'),
		previousButtons = 0;
	onMount(() => {
		let last = 0;
		const record = (e: Event) => {
			const p = e as PointerEvent;
			if (!['pen', 'mouse', 'touch'].includes(p.pointerType)) return;
			if (p.buttons !== previousButtons && p.buttons)
				signal = `버튼 값 ${previousButtons} → ${p.buttons} · ${p.pointerType}`;
			previousButtons = p.buttons;
			if (e.type === 'pointermove' && performance.now() - last < 90) return;
			last = performance.now();
			events = [
				`${e.type} · ${p.pointerType} · button ${p.button} / buttons ${p.buttons} · 압력 ${p.pressure?.toFixed(2)}`,
				...events
			].slice(0, 8);
		};
		const types = ['pointerdown', 'pointermove', 'pointerup', 'pointercancel', 'contextmenu'];
		for (const type of types) window.addEventListener(type, record, true);
		return () => {
			for (const type of types) window.removeEventListener(type, record, true);
		};
	});
</script>

<aside class="pen-diagnostics" aria-label="펜 입력 진단">
	<div>
		<strong>펜 입력 확인</strong><button onclick={onclose} aria-label="펜 입력 확인 닫기">×</button>
	</div>
	<p>{signal}</p>
	<small
		>노트 위에서 펜을 띄운 채 버튼을 짧게 누르고 떼 보세요. 누를 때 신호가 전혀 없으면 브라우저가
		버튼을 전달하지 않는 상태입니다.</small
	>{#each events as event, i (i)}<code>{event}</code>{/each}
</aside>

<style>
	.pen-diagnostics {
		position: fixed;
		right: 12px;
		bottom: 35px;
		width: 390px;
		max-width: calc(100vw - 24px);
		box-sizing: border-box;
		z-index: 1000;
		border: 1px solid #d9dbe0;
		border-radius: 8px;
		padding: 14px;
		background: #fff;
		box-shadow: 0 5px 25px #24252914;
		color: #242529;
		font: 12px sans-serif;
	}
	.pen-diagnostics div {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.pen-diagnostics button {
		border: 0;
		background: none;
		font-size: 20px;
		cursor: pointer;
	}
	.pen-diagnostics p {
		margin: 8px 0;
	}
	.pen-diagnostics small {
		display: block;
		color: #73757c;
		line-height: 1.6;
		margin-bottom: 10px;
	}
	.pen-diagnostics code {
		display: block;
		font-size: 10px;
		margin: 4px 0;
		overflow: hidden;
		white-space: nowrap;
	}
</style>
