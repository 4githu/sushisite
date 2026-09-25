<script lang="ts">
	let {
		name,
		size = 20
	}: {
		name:
			| 'panel'
			| 'day'
			| 'week'
			| 'month'
			| 'tasks'
			| 'search'
			| 'plus'
			| 'link'
			| 'chevron-left'
			| 'chevron-right';
		size?: number;
	} = $props();
	const paths = {
		panel: 'M4 4h16v16H4z M9 4v16 M14 9l3 3-3 3',
		day: 'M5 4h14v16H5z M9 4v16 M12 8h4 M12 12h4 M12 16h4',
		week: 'M4 5h16v15H4z M4 9h16 M9 9v11 M15 9v11 M8 3v4 M16 3v4',
		month: 'M4 5h16v15H4z M4 9h16 M8 3v4 M16 3v4 M8 13h1 M12 13h1 M16 13h1 M8 17h1 M12 17h1',
		tasks: 'M4 6l2 2 3-4 M12 6h8 M4 13l2 2 3-4 M12 13h8 M5 20h3 M12 20h8',
		search: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13 M16 16l4 4',
		plus: 'M12 5v14 M5 12h14',
		link: 'M10 13a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-2 2 M14 11a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l2-2',
		'chevron-left': 'M14 6l-6 6 6 6',
		'chevron-right': 'M10 6l6 6-6 6'
	};
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.6"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"><path d={paths[name]} /></svg
>
