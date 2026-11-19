import { API_BASE, PersonalApiError } from '$lib/personal-project/shared/api';

export type PlayerTrack = {
	id: number;
	source_id: number | null;
	video_id: string;
	title: string;
	channel_title: string;
	thumbnail_url: string;
	position: number;
	weight: number;
	enabled: number;
};
export type PlayerSource = {
	id: number;
	playlist_id: string;
	title: string;
	source_url: string;
	account_id: number | null;
};
export type PlayerCollection = {
	id: number;
	name: string;
	mode: 'ordered' | 'weighted';
	repeat_mode: 'all' | 'one' | 'off';
	avoid_repeat: number;
	playback_rate: number;
	track_count?: number;
	sources: PlayerSource[];
	tracks: PlayerTrack[];
};
export type PlayerSummary = Pick<PlayerCollection, 'id' | 'name' | 'mode' | 'repeat_mode'> & {
	track_count: number;
};
export type GooglePlayerAccount = { id: number; email: string; created_at: string };
export type GooglePlaylist = { id: string; title: string; count: number };

async function playerRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
	let response: Response;
	try {
		response = await fetch(`${API_BASE}/api/personal/player${path}`, {
			method,
			credentials: 'include',
			headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
			body: body === undefined ? undefined : JSON.stringify(body)
		});
	} catch (cause) {
		throw new PersonalApiError(0, '서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.', 'backend_unreachable', cause);
	}
	if (response.status === 401) {
		window.dispatchEvent(new Event('personal-auth-invalid'));
		throw new PersonalApiError(401, '로그인이 만료되었습니다. 다시 로그인해주세요.');
	}
	if (!response.ok) {
		const result = await response.json().catch(() => null);
		const detail = result?.detail;
		throw new PersonalApiError(response.status, typeof detail === 'string' ? detail : detail?.message || '요청을 처리하지 못했습니다.');
	}
	return response.status === 204 ? (undefined as T) : response.json();
}

export const playerApi = {
	collections: () => playerRequest<PlayerSummary[]>('/collections'),
	create: (name: string) => playerRequest<PlayerCollection>('/collections', 'POST', { name }),
	collection: (id: number) => playerRequest<PlayerCollection>(`/collections/${id}`),
	update: (id: number, data: Partial<Pick<PlayerCollection, 'name' | 'mode' | 'repeat_mode' | 'avoid_repeat' | 'playback_rate'>>) =>
		playerRequest<PlayerCollection>(`/collections/${id}`, 'PATCH', data),
	remove: (id: number) => playerRequest<void>(`/collections/${id}`, 'DELETE'),
	importSource: (id: number, url: string, account_id?: number) =>
		playerRequest<PlayerCollection>(`/collections/${id}/sources`, 'POST', { url, account_id }),
	removeSource: (id: number, sourceId: number) =>
		playerRequest<void>(`/collections/${id}/sources/${sourceId}`, 'DELETE'),
	addTrack: (id: number, url: string, account_id?: number) => playerRequest<PlayerCollection>(`/collections/${id}/tracks`, 'POST', { url, account_id }),
	updateTrack: (id: number, trackId: number, data: { weight?: number; enabled?: boolean }) =>
		playerRequest<PlayerCollection>(`/collections/${id}/tracks/${trackId}`, 'PATCH', data),
	removeTrack: (id: number, trackId: number) => playerRequest<void>(`/collections/${id}/tracks/${trackId}`, 'DELETE'),
	reorder: (id: number, ids: number[]) => playerRequest<PlayerCollection>(`/collections/${id}/tracks/order`, 'PUT', { ids }),
	accounts: () => playerRequest<GooglePlayerAccount[]>('/google/accounts'),
	googlePlaylists: (accountId: number) => playerRequest<GooglePlaylist[]>(`/google/accounts/${accountId}/playlists`),
	disconnect: (accountId: number) => playerRequest<void>(`/google/accounts/${accountId}`, 'DELETE')
};

export function googleConnectUrl(forceConsent = false) {
	return `${API_BASE}/auth/google/start?purpose=player&return_to=${encodeURIComponent('/personal-project/player')}${forceConsent ? '&force_consent=true' : ''}`;
}
