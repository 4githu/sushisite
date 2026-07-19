<script lang="ts">
	type IconName =
		| 'arrow-right'
		| 'bell'
		| 'briefcase'
		| 'calendar'
		| 'chart'
		| 'check'
		| 'chevron-right'
		| 'chevron-down'
		| 'clock'
		| 'document'
		| 'flag'
		| 'flame'
		| 'goggles'
		| 'home'
		| 'leaf'
		| 'list'
		| 'mic'
		| 'plus'
		| 'settings'
		| 'sliders'
		| 'star'
		| 'target'
		| 'upload'
		| 'user'
		| 'users'
		| 'wand';

	let {
		name,
		size = 24,
		strokeWidth = 2
	}: {
		name: IconName;
		size?: number;
		strokeWidth?: number;
	} = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width={strokeWidth}
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#if name === 'arrow-right'}
		<path d="M5 12h14" />
		<path d="m13 6 6 6-6 6" />
	{:else if name === 'bell'}
		<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
		<path d="M10 21h4" />
	{:else if name === 'briefcase'}
		<rect x="3" y="7" width="18" height="13" rx="2" />
		<path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
		<path d="M3 12h18" />
	{:else if name === 'calendar'}
		<rect x="3" y="4" width="18" height="17" rx="2" />
		<path d="M8 2v4" />
		<path d="M16 2v4" />
		<path d="M3 10h18" />
	{:else if name === 'chart'}
		<path d="M4 19V5" />
		<path d="M4 19h16" />
		<path d="m7 15 4-5 4 3 5-7" />
	{:else if name === 'check'}
		<path d="m5 12 4 4L19 6" />
	{:else if name === 'chevron-right'}
		<path d="m9 18 6-6-6-6" />
	{:else if name === 'chevron-down'}
		<path d="m6 9 6 6 6-6" />
	{:else if name === 'clock'}
		<circle cx="12" cy="12" r="9" />
		<path d="M12 7v5l3 2" />
	{:else if name === 'document'}
		<path d="M7 3h7l4 4v14H7z" />
		<path d="M14 3v5h5" />
		<path d="M10 13h5" />
		<path d="M10 17h4" />
	{:else if name === 'flag'}
		<path d="M5 21V4" />
		<path d="M5 4h12l-2 5 2 5H5" />
	{:else if name === 'flame'}
		<path
			d="M8.5 14.5A4.5 4.5 0 0 0 13 21a6 6 0 0 0 6-6c0-4-3-6-4-10-2 2-2 4-1 6-3-1-4-4-4-7-3 3-5 6-5 10a8 8 0 0 0 .4 2.5"
		/>
	{:else if name === 'goggles'}
		<path d="M4 14.5c.7-2.6 2.2-4 4.5-4H10c1 0 1.7.4 2 1 .3-.6 1-1 2-1h1.5c2.3 0 3.8 1.4 4.5 4" />
		<path d="M7 16h4" />
		<path d="M13 16h4" />
		<path d="M11 16c0-1 .4-1.5 1-1.5s1 .5 1 1.5" />
	{:else if name === 'home'}
		<path d="m3 11 9-8 9 8" />
		<path d="M5 10v10h14V10" />
		<path d="M10 20v-6h4v6" />
	{:else if name === 'leaf'}
		<path d="M5 20c8 0 14-6 14-14V4h-2C9 4 5 8 5 16v4Z" />
		<path d="M5 20 15 10" />
	{:else if name === 'list'}
		<rect x="4" y="4" width="16" height="16" rx="2" />
		<path d="M8 8h.01" />
		<path d="M11 8h5" />
		<path d="M8 12h.01" />
		<path d="M11 12h5" />
		<path d="M8 16h.01" />
		<path d="M11 16h5" />
	{:else if name === 'mic'}
		<rect x="9" y="2" width="6" height="12" rx="3" />
		<path d="M5 10a7 7 0 0 0 14 0" />
		<path d="M12 17v5" />
		<path d="M8 22h8" />
	{:else if name === 'plus'}
		<path d="M12 5v14" />
		<path d="M5 12h14" />
	{:else if name === 'settings'}
		<path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
		<path
			d="M19.4 15a1.8 1.8 0 0 0 .4 2l.1.1-2.1 2.1-.1-.1a1.8 1.8 0 0 0-2-.4 1.8 1.8 0 0 0-1.1 1.6V20h-3v-.1a1.8 1.8 0 0 0-1.1-1.6 1.8 1.8 0 0 0-2 .4l-.1.1-2.1-2.1.1-.1a1.8 1.8 0 0 0 .4-2A1.8 1.8 0 0 0 5.1 13H5v-3h.1a1.8 1.8 0 0 0 1.6-1.1 1.8 1.8 0 0 0-.4-2l-.1-.1 2.1-2.1.1.1a1.8 1.8 0 0 0 2 .4A1.8 1.8 0 0 0 11.5 3h3a1.8 1.8 0 0 0 1.1 2.1 1.8 1.8 0 0 0 2-.4l.1-.1 2.1 2.1-.1.1a1.8 1.8 0 0 0-.4 2A1.8 1.8 0 0 0 20.9 10h.1v3h-.1a1.8 1.8 0 0 0-1.5 2Z"
		/>
	{:else if name === 'sliders'}
		<path d="M4 7h5" />
		<path d="M15 7h5" />
		<path d="M11 7a2 2 0 1 0 4 0 2 2 0 0 0-4 0Z" />
		<path d="M4 17h9" />
		<path d="M19 17h1" />
		<path d="M15 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0Z" />
	{:else if name === 'star'}
		<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z" />
	{:else if name === 'target'}
		<circle cx="12" cy="12" r="8" />
		<circle cx="12" cy="12" r="4" />
		<path d="M12 2v4" />
		<path d="M22 12h-4" />
		<path d="M12 22v-4" />
		<path d="M2 12h4" />
	{:else if name === 'upload'}
		<path d="M16 16h2a4 4 0 0 0 0-8 5.5 5.5 0 0 0-10.8-1.5A4.8 4.8 0 0 0 6 16h2" />
		<path d="M12 12v8" />
		<path d="m9 15 3-3 3 3" />
	{:else if name === 'user'}
		<circle cx="12" cy="8" r="4" />
		<path d="M4 21a8 8 0 0 1 16 0" />
	{:else if name === 'users'}
		<path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
		<circle cx="9.5" cy="7" r="4" />
		<path d="M22 21v-2a4 4 0 0 0-3-3.9" />
		<path d="M16 3.1a4 4 0 0 1 0 7.8" />
	{:else if name === 'wand'}
		<path d="M15 4v4" />
		<path d="M13 6h4" />
		<path d="M20 11v3" />
		<path d="M18.5 12.5h3" />
		<path d="m4 20 10-10 3 3L7 23z" />
	{/if}
</svg>
