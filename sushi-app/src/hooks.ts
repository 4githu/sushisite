import type { Reroute } from '@sveltejs/kit';

/** Render the Odi route at the Rehear product hostname without redirecting. */
export const reroute: Reroute = ({ url }) => {
	if (url.hostname === 'rehear.chobab.app' && url.pathname === '/') {
		return '/odi';
	}
};
