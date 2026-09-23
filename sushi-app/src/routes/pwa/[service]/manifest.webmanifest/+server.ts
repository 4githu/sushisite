import { json, error } from '@sveltejs/kit';
export function GET({ params }) {
	if (!['aura', 'calendar'].includes(params.service)) error(404);
	const aura = params.service === 'aura';
	const path = `/personal-project/${params.service}`;
	return json(
		{
			id: path,
			name: aura ? '아우라 클리닉' : 'NETAQ',
			short_name: aura ? '아우라' : 'NETAQ',
			lang: 'ko',
			start_url: path,
			scope: '/personal-project/',
			display: 'standalone',
			background_color: '#ffffff',
			theme_color: aura ? '#484d43' : '#232428',
			description: '일정과 할 일을 한곳에서 관리하세요.',
			icons: [
				{ src: '/ondo-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
				{ src: '/ondo-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
			],
			shortcuts: [
				{ name: '캘린더', url: '/personal-project/calendar' },
				{ name: '해야 할 일', url: '/personal-project/calendar/tasks' }
			]
		},
		{
			headers: {
				'Content-Type': 'application/manifest+json',
				'Cache-Control': 'public, max-age=3600'
			}
		}
	);
}
