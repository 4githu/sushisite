<script lang="ts">
	import Icon from './Icon.svelte';

	const navItems = [
		{ label: 'Home', icon: 'home', href: '/rehear' },
		{ label: 'Favorites', icon: 'star', href: '/rehear' },
		{ label: 'Report', icon: 'list', href: '/rehear' },
		{ label: 'My Practice', icon: 'mic', href: '/rehear' }
	] as const;
</script>

<aside class="rehear-sidebar" aria-label="Re:hear navigation">
	<div>
		<a class="rehear-brand" href="/rehear" aria-label="Re:hear">
			<span class="rehear-brand-mark"></span>
			<span>Re:hear</span>
		</a>
		<p class="rehear-tagline">Practice. Feedback. Real Growth.</p>

		<a class="rehear-new-session" href="/rehear/presentation/setup">
			<Icon name="plus" size={22} />
			<span>New Session</span>
		</a>

		<nav class="rehear-nav" aria-label="Main navigation">
			{#each navItems as item}
				<a href={item.href}>
					<Icon name={item.icon} size={20} strokeWidth={1.8} />
					<span>{item.label}</span>
				</a>
			{/each}
		</nav>
	</div>

	<a class="rehear-profile" href="/rehear">
		<span class="rehear-profile-icon">
			<Icon name="user" size={22} />
		</span>
		<span>My page</span>
		<Icon name="chevron-right" size={24} />
	</a>
</aside>
