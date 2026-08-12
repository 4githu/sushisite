// src/lib/odi/stores/session.ts

const API = import.meta.env.VITE_SUSHIFASTURL;

import { get, writable } from "svelte/store";
import { goto } from "$app/navigation";
import { odiuser, type JsonObject } from "./odiuser";
import { template } from "./template";
import { publishPresentationData } from "$lib/odi/firebase/session-materials";

export type PreSessionState = "waiting" | "running" | "finished" | "expired" | "cancelled";

export type OdiPreSession = {
	pin_code: string;
	template_id: string;
	session_id: string | null;
	state: PreSessionState;
	expires_at: string;
	created_at: string;
};

export type OdiSessionState = "running" | "completed" | "failed" | "cancelled";

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
};

export type OdiFileBundle = {
	file_bundle_id: string;
	file_bundle_path: string;
	expires_at: string;
	files: JsonObject;
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

async function fetchJson(res: Response) {
	const data = await res.json().catch(() => null);

	if (!res.ok) {
		const message = data?.detail ?? data?.message ?? "요청 실패";
		throw new Error(message);
	}

	return data;
}

function sleep(ms: number) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

export const session = {
	subscribe: store.subscribe,

	get() {
		return get(store);
	},

	clear() {
		store.set(initialState);
	},

	async startFromCurrentTemplate(expires_minutes = 30) {
		const user = odiuser.get();

		if (user === null) {
			throw new Error("ODI 유저가 없습니다.");
		}

		await template.saveToRecent();

		const res = await fetch(`${API}/odi/db/pre-sessions/start-from-recent`, {
			method: "POST",
			credentials: "include",
			headers: {
				"Content-Type": "application/json"
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
		if (preparedTemplate?.type === "presentation") {
			try {
				await publishPresentationData(String(data.pin_code), preparedTemplate);
			} catch (error) {
				await this.updatePreSessionState(String(data.pin_code), "cancelled").catch(() => undefined);
				throw error;
			}
		}

		store.update((state) => ({
			...state,
			pin_code: data.pin_code,
			pre_session: preSession,
			current_session: null,
			file_bundle: data.file_bundle ?? null
		}));

		return preSession;
	},

	async refreshPreSession(pinCode?: string) {
		const current = get(store);
		const targetPin = pinCode ?? current.pin_code;

		if (!targetPin) {
			throw new Error("조회할 pin_code가 없습니다.");
		}

		const res = await fetch(`${API}/odi/db/pre-sessions/${targetPin}`, {
			credentials: "include"
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
			method: "PUT",
			credentials: "include",
			headers: {
				"Content-Type": "application/json"
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

	async pollUntilFinished(pinCode?: string, intervalMs = 1500) {
		store.update((state) => ({
			...state,
			polling: true
		}));

		try {
			while (get(store).polling) {
				const preSession = await this.refreshPreSession(pinCode);

				if (preSession.state === "finished" && preSession.session_id) {
					const report = await this.getReport(preSession.session_id);
					return report;
				}

				if (preSession.state === "expired" || preSession.state === "cancelled") {
					throw new Error(`pre_session 상태가 ${preSession.state}입니다.`);
				}

				await sleep(intervalMs);
			}

			return null;
		} finally {
			store.update((state) => ({
				...state,
				polling: false
			}));
		}
	},

	stopPolling() {
		store.update((state) => ({
			...state,
			polling: false
		}));
	},

	async finishPreSession(pinCode: string, feedback: JsonObject) {
		const user = odiuser.get();

		if (user === null) {
			throw new Error("ODI 유저가 없습니다.");
		}

		const res = await fetch(`${API}/odi/db/pre-sessions/${pinCode}/finish`, {
			method: "POST",
			credentials: "include",
			headers: {
				"Content-Type": "application/json"
			},
			body: JSON.stringify({
				user_id: user.user_id,
				feedback
			})
		});

		const data = await fetchJson(res);

		store.update((state) => ({
			...state,
			pin_code: data.pre_session?.pin_code ?? state.pin_code,
			pre_session: data.pre_session,
			current_session: data.session
		}));

		return data.session as OdiSession;
	},

	async getReport(sessionId: string) {
		const res = await fetch(`${API}/odi/db/sessions/${sessionId}`, {
			credentials: "include"
		});

		const data = await fetchJson(res);
		const currentSession = data.session as OdiSession;

		store.update((state) => ({
			...state,
			current_session: currentSession
		}));

		return currentSession;
	},

	async listMySessions(limit = 20) {
		const user = odiuser.get();

		if (user === null) {
			throw new Error("ODI 유저가 없습니다.");
		}

		const res = await fetch(`${API}/odi/db/users/${user.user_id}/sessions?limit=${limit}`, {
			credentials: "include"
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
	}
};
