import { API_BASE_URL } from '$lib/config/env';

/** @param {string} sessionId @param {Record<string, unknown>} config */
export async function saveSessionConfig(sessionId, config) {
	const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/config`, {
		method: 'PUT',
		headers: {
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(config)
	});

	if (!res.ok) {
		throw new Error('설정 저장 실패');
	}

	return await res.json();
}

/** @param {string} sessionId @returns {Promise<Record<string, unknown>>} */
export async function getSessionResult(sessionId) {
	const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/result`);

	if (!res.ok) {
		throw new Error('결과 불러오기 실패');
	}

	return await res.json();
}
