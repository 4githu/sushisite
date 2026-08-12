import { redirect } from '@sveltejs/kit';

/** 아우라 전용 hostname은 앱의 실제 진입 경로로 바로 보낸다. */
export function load({ url }) {
	if (url.hostname === 'aura.chobab.app' && url.pathname === '/') {
		redirect(307, '/personal-project/aura');
	}
}
