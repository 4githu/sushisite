import type { ReportMedia } from './reportTypes';
import { API_BASE } from '$lib/config/api';

export type ResolvedReportMedia = {
	videoUrl: string;
	title: string;
	hasSessionMismatch: boolean;
};

/**
 * Resolve session-scoped playback media while continuing to accept the old
 * `{ video_url, title }` shape. A URL explicitly bound to another session is
 * never rendered, which prevents stale report data from playing the wrong clip.
 */
export function resolveReportMedia(
	media: ReportMedia | undefined,
	sessionId: string
): ResolvedReportMedia {
	const boundSessionId = media?.session_id?.trim();
	const hasSessionMismatch = Boolean(boundSessionId && boundSessionId !== sessionId);
	const rawVideoUrl = media?.video_url?.trim() ?? '';
	const videoUrl = rawVideoUrl.startsWith('/odi/') ? `${API_BASE}${rawVideoUrl}` : rawVideoUrl;

	return {
		videoUrl: hasSessionMismatch ? '' : videoUrl,
		title: media?.title?.trim() || '발표 시연 영상',
		hasSessionMismatch
	};
}
