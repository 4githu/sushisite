<script lang="ts">
	let {
		name,
		size = 20
	}: {
		name:
			| 'boards'
			| 'files'
			| 'school'
			| 'meals'
			| 'plan'
			| 'settings'
			| 'projects'
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
		settings:
			'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',
		boards: 'M3 4h18v12H9l-5 4v-4H3z M7 8h10 M7 12h6',
		files: 'M5 3h9l5 5v13H5z M14 3v6h5 M8 13h8 M8 17h6',
		school: 'M3 9l9-6 9 6-9 6z M6 11v7q6 5 12 0v-7',
		meals: 'M5 3v7 M8 3v7 M3 3v7h7 M6 10v11 M18 3v18 M18 3q-6 6 0 10',
		plan: 'M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h4',
		projects: 'M4 5h6l2 3h8v12H4z M8 13h8 M12 10v6',
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
