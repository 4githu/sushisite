import { redirect } from '@sveltejs/kit';

/** 아우라 전용 hostname은 앱의 실제 진입 경로로 바로 보낸다. */
export function load({ url }) {
    if (['calender.chobab.app', 'calendar.chobab.app'].includes(url.hostname)) {
        redirect(307, '/personal-project/calendar');
    }
	if (url.hostname === 'rehear.chobab.app' && url.pathname === '/') {
		redirect(307, '/odi');
	}

	if (url.hostname === 'aura.chobab.app' && url.pathname === '/') {
		redirect(307, '/personal-project/aura');
	}
}
