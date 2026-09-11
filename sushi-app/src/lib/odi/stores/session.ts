// src/lib/odi/stores/session.ts

import { API_BASE as API } from '$lib/config/api';

import { get, writable } from 'svelte/store';
import { goto } from '$app/navigation';
import { odiuser, type JsonObject } from './odiuser';
import { template } from './template';
import {
	deletePresentationData,
	publishPresentationData
} from '$lib/odi/firebase/session-materials';
import {
	createFixedDemoPresentationTemplate,
	fixedDemoFeedback
} from '$lib/odi/demo/fixedPresentationScenario';

export type PreSessionState = 'waiting' | 'running' | 'finished' | 'expired' | 'cancelled';

export type OdiPreSession = {
	pin_code: string;
	template_id: string;
	session_id: string | null;
	state: PreSessionState;
	expires_at: string;
	created_at: string;
	report_status?: 'not_started' | 'queued' | 'generating' | 'ready' | 'failed';
	report_error?: string | null;
};

export type OdiSessionState = 'running' | 'completed' | 'failed' | 'cancelled';

export type OdiSession = {
	session_id: string;
	user_id: string;
	template_id: string | null;
	template: JsonObject;
	feedback: JsonObject | null;
	state: OdiSessionState;
	started_at: string | null;
	ended_at: string | null;
	created_at: string;
	updated_at: string;
	comparison?: JsonObject;
};

export type OdiFileBundle = {
	file_bundle_id: string;
	file_bundle_path: string;
	expires_at: string;
	files: JsonObject;
};

export type EvcReportFinishPayload = {
	request_id: string;
	planned_seconds?: number;
	qa_seconds?: number;
};

export type SessionMediaInput = {
	video_url: string;
	title?: string;
	source?: 'demo' | 'recording' | 'upload' | 'external';
};

type SessionStoreState = {
	pin_code: string | null;
	pre_session: OdiPreSession | null;
	current_session: OdiSession | null;
	sessions: OdiSession[];
	file_bundle: OdiFileBundle | null;
	polling: boolean;
};

const initialState: SessionStoreState = {
	pin_code: null,
	pre_session: null,
	current_session: null,
	sessions: [],
	file_bundle: null,
	polling: false
};

const store = writable<SessionStoreState>(initialState);
let pollingGeneration = 0;

async function fetchJson(res: Response) {
	const data = await res.json().catch(() => null);

	if (!res.ok) {
		const rawMessage = data?.detail?.message ?? data?.detail ?? data?.message ?? '요청 실패';
		const message = typeof rawMessage === 'string' ? rawMessage : JSON.stringify(rawMessage);
		throw new Error(message);
	}

	return data;
}

function sleep(ms: number) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureSessionContext() {
	let user = odiuser.get();

	if (user === null) {
		const access = await odiuser.checkAccess();
		user = access.user;
	}

	if (user === null) {
		throw new Error('로그인 정보를 확인하지 못했습니다. 다시 로그인해 주세요.');
	}

	let currentTemplate = template.get();

	if (currentTemplate === null) {
		currentTemplate = template.loadFromRecent();
	}

	if (currentTemplate === null) {
		throw new Error('저장된 발표 설정을 찾지 못했습니다. 발표 설정 화면에서 다시 확인해 주세요.');
	}

	return { user, currentTemplate };
}

export const session = {
	subscribe: store.subscribe,

	get() {
		return get(store);
	},

	clear() {
		pollingGeneration += 1;
		store.set(initialState);
	},

	async saveCurrentTemplateForHandoff() {
		await ensureSessionContext();
		return template.saveToRecent();
	},

	async startFromCurrentTemplate(
		expires_minutes = 30,
		options: { skipPresentationPublish?: boolean } = {}
	) {
		const { user } = await ensureSessionContext();

		await template.saveToRecent();

		const res = await fetch(`${API}/odi/db/pre-sessions/start-from-recent`, {
			method: 'POST',
			credentials: 'include',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				user_id: user.user_id,
				expires_minutes
			})
		});

		const data = await fetchJson(res);
		const preSession = data.pre_session as OdiPreSession;

		if (data.template?.template) {
			template.set(data.template.template);
		}

		const preparedTemplate = data.template?.template;
		if (preparedTemplate?.type === 'presentation' && !options.skipPresentationPublish) {
			try {
				await publishPresentationData(String(data.pin_code), preparedTemplate);
			} catch (error) {
				await this.updatePreSessionState(String(data.pin_code), 'cancelled').catch(() => undefined);
				throw error;
			}
		}

		// Firebase 행까지 준비된 뒤에만 PIN을 노출합니다. XR이 PIN으로 조회할 때
		// 아직 데이터가 없는 경쟁 상태를 만들지 않습니다.
		store.update((state) => ({
			...state,
			pin_code: data.pin_code,
			pre_session: preSession,
			current_session: null,
			file_bundle: data.file_bundle ?? null
		}));

		return preSession;
	},

	async startFixedDemoPresentation(expires_minutes = 30) {
		const { currentTemplate: originalTemplate } = await ensureSessionContext();

		try {
			template.set(createFixedDemoPresentationTemplate());
			return await this.startFromCurrentTemplate(expires_minutes, {
				skipPresentationPublish: true
			});
		} finally {
			// 체험 세션 때문에 사용자가 설정한 발표 자료와 옵션이 recent_template에서
			// 사라지지 않도록 반드시 원래 템플릿을 복원합니다.
			template.set(originalTemplate);
			await template.saveToRecent();
		}
	},

	async finishFixedDemoPresentation(pinCode?: string) {
		const current = get(store);
		const targetPin = pinCode ?? current.pin_code;
		if (!targetPin) throw new Error('시연 PIN 번호가 없습니다.');
		if (current.pre_session?.state === 'finished') return current.current_session;

		return this.finishPreSession(targetPin, fixedDemoFeedback);
	},

	async refreshPreSession(pinCode?: string) {
		const current = get(store);
		const targetPin = pinCode ?? current.pin_code;

		if (!targetPin) {
			throw new Error('조회할 pin_code가 없습니다.');
		}

		const res = await fetch(`${API}/odi/db/pre-sessions/${targetPin}`, {
			credentials: 'include'
		});

		const data = await fetchJson(res);
		const preSession = data.pre_session as OdiPreSession;

		store.update((state) => ({
			...state,
			pin_code: preSession.pin_code,
			pre_session: preSession
		}));

		return preSession;
	},

	async updatePreSessionState(pinCode: string, nextState: PreSessionState) {
		const res = await fetch(`${API}/odi/db/pre-sessions/${pinCode}/state`, {
			method: 'PUT',
			credentials: 'include',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				state: nextState
			})
		});

		const data = await fetchJson(res);
		const preSession = data.pre_session as OdiPreSession;

		store.update((state) => ({
			...state,
			pin_code: preSession.pin_code,
			pre_session: preSession
		}));

		return preSession;
	},

	async pollUntilFinished(pinCode?: string, intervalMs = 1500, timeoutMs = 30 * 60 * 1000) {
		const generation = ++pollingGeneration;
		const startedAt = Date.now();

		store.update((state) => ({
			...state,
			polling: true
		}));

		try {
			while (generation === pollingGeneration && get(store).polling) {
				if (Date.now() - startedAt >= timeoutMs) {
					throw new Error(
						'분석 완료를 기다리는 시간이 길어지고 있습니다. 잠시 후 다시 시도해 주세요.'
					);
				}

				const preSession = await this.refreshPreSession(pinCode);

				if (preSession.state === 'finished' && preSession.session_id) {
					await deletePresentationData(preSession.pin_code).catch((error) => {
						console.warn('완료된 Firebase 발표 데이터를 삭제하지 못했습니다.', error);
					});
					// 리포트 본문은 상세 라우트가 자신의 session_id로 한 번만 조회합니다.
					// 대기 화면에서는 완료 여부만 갱신해 같은 데이터를 연속 호출하지 않습니다.
					return preSession;
				}

				if (preSession.state === 'expired' || preSession.state === 'cancelled') {
					throw new Error(`pre_session 상태가 ${preSession.state}입니다.`);
				}

				await sleep(intervalMs);
			}

			return null;
		} finally {
			if (generation === pollingGeneration) {
				store.update((state) => ({
					...state,
					polling: false
				}));
			}
		}
	},

	stopPolling() {
		pollingGeneration += 1;
		store.update((state) => ({
			...state,
			polling: false
		}));
	},

	async finishPreSession(pinCode: string, feedback: JsonObject) {
		const user = odiuser.get();

		if (user === null) {
			throw new Error('ODI 유저가 없습니다.');
		}

		const res = await fetch(`${API}/odi/db/pre-sessions/${pinCode}/finish`, {
			method: 'POST',
			credentials: 'include',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				user_id: user.user_id,
				feedback
			})
		});

		const data = await fetchJson(res);
		await deletePresentationData(pinCode).catch((error) => {
			console.warn('완료된 Firebase 발표 데이터를 삭제하지 못했습니다.', error);
		});

		store.update((state) => ({
			...state,
			pin_code: data.pre_session?.pin_code ?? state.pin_code,
			pre_session: data.pre_session,
			current_session: data.session
		}));

		return data.session as OdiSession;
	},

	async finishEvcPresentation(
		evcSessionId: string,
		evcToken: string,
		payload: EvcReportFinishPayload
	) {
		const res = await fetch(`${API}/odi/xreal_rehear/evc/sessions/${evcSessionId}/finish`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-EVC-Session-Token': evcToken
			},
			body: JSON.stringify(payload)
		});
		return fetchJson(res);
	},

	async getEvcReportStatus(evcSessionId: string, evcToken: string) {
		const res = await fetch(`${API}/odi/xreal_rehear/evc/sessions/${evcSessionId}/report`, {
			headers: { 'X-EVC-Session-Token': evcToken }
		});
		return fetchJson(res);
	},

	async retryReport(pinCode: string, plannedSeconds = 0, qaSeconds = 0) {
		const res = await fetch(`${API}/odi/db/pre-sessions/${pinCode}/report/retry`, {
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				request_id: crypto.randomUUID(),
				planned_seconds: plannedSeconds,
				qa_seconds: qaSeconds
			})
		});
		return fetchJson(res);
	},

	async getReport(sessionId: string) {
		await odiuser.requireUser();

		const res = await fetch(`${API}/odi/db/sessions/${sessionId}`, {
			credentials: 'include'
		});

		const data = await fetchJson(res);
		const currentSession = {
			...(data.session as OdiSession),
			comparison: data.comparison ?? undefined
		} as OdiSession;

		store.update((state) => ({
			...state,
			current_session: currentSession
		}));

		return currentSession;
	},

	async updateSessionMedia(sessionId: string, media: SessionMediaInput) {
		const res = await fetch(`${API}/odi/db/sessions/${sessionId}/media`, {
			method: 'PUT',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(media)
		});

		const data = await fetchJson(res);
		const updatedSession = data.session as OdiSession;
		store.update((state) => ({
			...state,
			current_session:
				state.current_session?.session_id === sessionId ? updatedSession : state.current_session,
			sessions: state.sessions.map((item) =>
				item.session_id === sessionId ? updatedSession : item
			)
		}));

		return updatedSession;
	},

	async uploadSessionVideo(sessionId: string, file: File) {
		const formData = new FormData();
		formData.append('file', file);

		const res = await fetch(`${API}/odi/db/sessions/${sessionId}/media/upload`, {
			method: 'POST',
			credentials: 'include',
			body: formData
		});

		const data = await fetchJson(res);
		const updatedSession = data.session as OdiSession;
		store.update((state) => ({
			...state,
			current_session:
				state.current_session?.session_id === sessionId ? updatedSession : state.current_session,
			sessions: state.sessions.map((item) =>
				item.session_id === sessionId ? updatedSession : item
			)
		}));

		return updatedSession;
	},

	async getTranscript(sessionId: string) {
		const res = await fetch(`${API}/odi/db/sessions/${sessionId}/transcript`, {
			credentials: 'include'
		});
		return fetchJson(res);
	},

	async deleteSourceData(sessionId: string) {
		const res = await fetch(`${API}/odi/db/sessions/${sessionId}/source-data`, {
			method: 'DELETE',
			credentials: 'include'
		});
		return fetchJson(res);
	},

	async listMySessions(limit = 20) {
		const user = await odiuser.requireUser();

		const res = await fetch(`${API}/odi/db/users/${user.user_id}/sessions?limit=${limit}`, {
			credentials: 'include'
		});

		const data = await fetchJson(res);
		const sessions = data.sessions as OdiSession[];

		store.update((state) => ({
			...state,
			sessions
		}));

		return sessions;
	},

	async openReport(sessionId: string, path = `/odi/report/${sessionId}`) {
		await this.getReport(sessionId);
		goto(path);
	},

	async deleteSession(sessionId: string) {
		await odiuser.requireUser();

		const res = await fetch(`${API}/odi/db/sessions/${sessionId}`, {
			method: 'DELETE',
			credentials: 'include'
		});
		await fetchJson(res);
		store.update((state) => ({
			...state,
			sessions: state.sessions.filter((item) => item.session_id !== sessionId),
			current_session:
				state.current_session?.session_id === sessionId ? null : state.current_session
		}));
	}
};
