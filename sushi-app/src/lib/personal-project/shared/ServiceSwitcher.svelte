<script lang="ts">
	let { active }: { active: 'calendar' | 'aura' | 'player' | 'notes' } = $props();
</script>

<nav class="service-switcher" aria-label="서비스">
	<a
		href="/personal-project/calendar"
		class:active={active === 'calendar'}
		aria-current={active === 'calendar' ? 'page' : undefined}
		><span class="service-icon" aria-hidden="true">▦</span><span class="service-name"
			>NETAQ 캘린더</span
		></a
	>
	<a
		href="/personal-project/aura"
		class:active={active === 'aura'}
		aria-current={active === 'aura' ? 'page' : undefined}
		><span class="service-icon" aria-hidden="true">A</span><span class="service-name"
			>아우라 클리닉</span
		></a
	>
	<a
		href="/personal-project/player"
		class:active={active === 'player'}
		aria-current={active === 'player' ? 'page' : undefined}
		><span class="service-icon" aria-hidden="true">♫</span><span class="service-name"
			>온전히 음악</span
		></a
	>
	<a href="/personal-project/notes" class:active={active === 'notes'}
		><span class="service-icon" aria-hidden="true">▤</span><span class="service-name"
			>NETAQ Notes</span
		></a
	>
</nav>

<style>
	.service-switcher {
		display: grid;
		gap: 2px;
		margin: 14px 0;
	}
	.service-switcher a {
		display: flex;
		align-items: center;
		gap: 9px;
		padding: 9px 11px;
		border-radius: 7px;
		color: inherit;
		font-size: 12px;
		text-decoration: none;
		opacity: 0.76;
	}
	.service-icon {
		display: grid;
		place-items: center;
		width: 19px;
		height: 19px;
		flex: 0 0 19px;
		border: 1px solid currentColor;
		border-radius: 5px;
		font-size: 10px;
		font-weight: 700;
	}
	.service-switcher a:hover {
		background: #0000000a;
		opacity: 1;
	}
	.service-switcher a.active {
		background: #0000000d;
		font-weight: 700;
		opacity: 1;
	}
</style>
