import { read } from '$app/server';
import apk from '$lib/server/assets/ondo-widget.apk?url';
import type { RequestHandler } from './$types';
export const GET: RequestHandler = () => {
    const asset = read(apk);
    return new Response(asset.body, { headers: {
        'Content-Type': 'application/vnd.android.package-archive',
        'Content-Disposition': 'attachment; filename="ondo-widget.apk"',
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'no-cache'
    } });
};
