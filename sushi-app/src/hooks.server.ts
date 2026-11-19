import { sequence } from '@sveltejs/kit/hooks';
import { building } from '$app/environment';
import { auth } from '$lib/server/auth';
import { svelteKitHandler } from 'better-auth/svelte-kit';
import type { Handle } from '@sveltejs/kit';
import { getTextDirection } from '$lib/paraglide/runtime';
import { paraglideMiddleware } from '$lib/paraglide/server';

const handleParaglide: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ request, locale }) => {
		event.request = request;

		return resolve(event, {
			transformPageChunk: ({ html }) =>
				html
					.replace('%paraglide.lang%', locale)
					.replace('%paraglide.dir%', getTextDirection(locale))
					.replace('</head>', event.url.pathname.startsWith('/personal-project/') ? '<script src="/netaq-cache-recovery-v2.js"></script></head>' : '</head>')
		});
	});

const handleBetterAuth: Handle = async ({ event, resolve }) => {
	const hasSessionCookie = /(?:^|;\s*)(?:__Secure-)?better-auth\.session_token=/.test(event.request.headers.get('cookie') || '');
	const session = hasSessionCookie ? await auth.api.getSession({ headers: event.request.headers }) : null;

	if (session) {
		event.locals.session = session.session;
		event.locals.user = session.user;
	}

	return svelteKitHandler({ event, resolve, auth, building });
};

export const handle: Handle = sequence(handleParaglide, handleBetterAuth);
