import type {
	AiReportModel,
	AiReportResult,
	AuraReport,
	AuraSession,
	CalendarEvent,
	ClinicRound,
	School,
	SchoolSettlement,
	Student,
	TargetReport
} from './types';

// 개발·터널 환경에서도 로그인과 API가 같은 브라우저 출처를 사용해야
// HttpOnly 쿠키가 빠지지 않는다. VITE_SUSHIFASTURL을 비워 두면 Vite proxy를 사용한다.
const configuredApi = import.meta.env.VITE_SUSHIFASTURL || '';
export const API_BASE = /^(https?:\/\/)?(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configuredApi.replace(/\/$/, ''))
	? ''
	: configuredApi;

type RequestOptions = Omit<RequestInit, 'body'> & { body?: unknown };
export type ReportAttachment = { id: number; kind: 'blank_test' | 'problem_solving'; name: string; mimeType: string; byteSize: number; createdAt: string };

export class PersonalApiError extends Error {
	status: number;
	code?: string;
	detail?: unknown;

	constructor(status: number, message: string, code?: string, detail?: unknown) {
		super(message);
		this.name = 'PersonalApiError';
		this.status = status;
		this.code = code;
		this.detail = detail;
	}
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	let response: Response;
	try {
		response = await fetch(`${API_BASE}/api/personal${path}`, {
			...options,
			credentials: 'include',
			headers: options.body
				? { 'Content-Type': 'application/json', ...options.headers }
				: options.headers,
			body: options.body ? JSON.stringify(options.body) : undefined
		});
	} catch (cause) {
		throw new PersonalApiError(
			0,
			'백엔드 서버에 연결할 수 없습니다. / Cannot connect to the backend server.',
			'backend_unreachable',
			cause
		);
	}
	if (response.status === 401) {
		throw new PersonalApiError(
			401,
			'로그인이 만료되었습니다. 다시 로그인해주세요. / Your session expired. Please sign in again.',
			'authentication_required'
		);
	}
	if (!response.ok) {
		const error = await response.json().catch(() => null);
		const detail = error?.detail;
		const message =
			typeof detail === 'string'
				? detail
				: typeof detail?.message === 'string'
					? detail.message
					: `요청을 처리하지 못했습니다. / Request failed. (${response.status})`;
		throw new PersonalApiError(response.status, message, detail?.code, detail);
	}
	return response.status === 204 ? (undefined as T) : response.json();
}

export const personalApi = {
	events(from: string, to: string) {
		const query = new URLSearchParams({ from, to });
		return request<CalendarEvent[]>(`/calendar/events?${query}`);
	},
	event(id: number) {
		return request<CalendarEvent>(`/calendar/events/${id}`);
	},
	createEvent(body: {
		title: string;
		description: string;
		start_time: string;
		end_time: string | null;
		is_all_day: boolean;
		status: string;
		type: string;
		category_name?: string;
	}) {
		return request<CalendarEvent>('/calendar/events', { method: 'POST', body });
	},
	createEventSeries(body: Record<string, unknown>) {
		return request<CalendarEvent[]>('/calendar/events/series', { method: 'POST', body });
	},
	updateEvent(id: number, body: Record<string, unknown>) {
		return request<CalendarEvent>(`/calendar/events/${id}`, { method: 'PATCH', body });
	},
	deleteEvent(id: number) {
		return request<void>(`/calendar/events/${id}`, { method: 'DELETE' });
	},
	updateEventScope(id: number, body: Record<string, unknown>) {
		return request<CalendarEvent>(`/calendar/events/${id}/scope`, { method: 'PATCH', body });
	},
	deleteEventScope(id: number, scope: 'this' | 'following') {
		return request<void>(`/calendar/events/${id}/scope?scope=${scope}`, { method: 'DELETE' });
	},
	students(active?: boolean) {
		const query = active === undefined ? '' : `?active=${active}`;
		return request<Student[]>(`/aura/students${query}`);
	},
	createStudent(body: Record<string, unknown>) {
		return request<Student>('/aura/students', { method: 'POST', body });
	},
	updateStudent(id: number, body: Record<string, unknown>) {
		return request<Student>(`/aura/students/${id}`, { method: 'PATCH', body });
	},
	sessions(from?: string, to?: string) {
		const query = new URLSearchParams();
		if (from) query.set('from', from);
		if (to) query.set('to', to);
		return request<AuraSession[]>(`/aura/sessions?${query}`);
	},
	session(id: number) {
		return request<AuraSession>(`/aura/sessions/${id}`);
	},
	createSession(body: Record<string, unknown>) {
		return request<AuraSession>('/aura/sessions', { method: 'POST', body });
	},
	createSessionSeries(body: Record<string, unknown>) {
		return request<AuraSession[]>('/aura/sessions/series', { method: 'POST', body });
	},
	updateSession(id: number, body: Record<string, unknown>) {
		return request<AuraSession>(`/aura/sessions/${id}`, { method: 'PATCH', body });
	},
	deleteSession(id: number) {
		return request<void>(`/aura/sessions/${id}`, { method: 'DELETE' });
	},
	createReport(sessionId: number, contentJson: unknown, sourceNotes = '') {
		return request<{ id: number }>(`/aura/sessions/${sessionId}/report`, {
			method: 'POST',
			body: { source_notes: sourceNotes, content_json: contentJson }
		});
	},
	updateReport(id: number, body: Record<string, unknown>) {
		return request<AuraReport>(`/aura/reports/${id}`, { method: 'PATCH', body });
	},
	submitReport(id: number) {
		return request<AuraReport>(`/aura/reports/${id}/submit`, { method: 'POST' });
	},
	settlements(year: number, month: number) {
		return request<SchoolSettlement>(`/aura/settlements?year=${year}&month=${month}`);
	},
	settlementExportUrl(year: number, month: number) {
		return `${API_BASE}/api/personal/aura/settlements/export.xlsx?year=${year}&month=${month}`;
	},
	schools() {
		return request<School[]>('/aura/schools');
	},
	school(id: number) {
		return request<School>(`/aura/schools/${id}`);
	},
	createSchool(body: Record<string, unknown>) {
		return request<School>('/aura/schools', { method: 'POST', body });
	},
	updateSchool(id: number, body: Record<string, unknown>) {
		return request<School>(`/aura/schools/${id}`, { method: 'PATCH', body });
	},
	moveSchool(id: number, direction: 'up' | 'down') {
		return request<School>(`/aura/schools/${id}/move?direction=${direction}`, {
			method: 'POST'
		});
	},
	deleteSchool(id: number) {
		return request<void>(`/aura/schools/${id}`, { method: 'DELETE' });
	},
	schoolExportUrl(id: number) {
		return `${API_BASE}/api/personal/aura/schools/${id}/export.json`;
	},
	rounds(from?: string, to?: string, schoolId?: number) {
		const query = new URLSearchParams();
		if (from) query.set('from', from);
		if (to) query.set('to', to);
		if (schoolId) query.set('school_id', String(schoolId));
		return request<ClinicRound[]>(`/aura/rounds?${query}`);
	},
	round(id: number) {
		return request<ClinicRound>(`/aura/rounds/${id}`);
	},
	createRound(body: Record<string, unknown>) {
		return request<ClinicRound>('/aura/rounds', { method: 'POST', body });
	},
	createRoundSeries(body: Record<string, unknown>) {
		return request<ClinicRound[]>('/aura/rounds/series', { method: 'POST', body });
	},
	updateRound(id: number, body: Record<string, unknown>) {
		return request<ClinicRound>(`/aura/rounds/${id}`, { method: 'PATCH', body });
	},
	deleteRound(id: number) {
		return request<void>(`/aura/rounds/${id}`, { method: 'DELETE' });
	},
	addRoundTarget(roundId: number, studentName: string) {
		return request(`/aura/rounds/${roundId}/targets`, {
			method: 'POST',
			body: { student_name: studentName }
		});
	},
	deleteRoundTarget(targetId: number) {
		return request<void>(`/aura/targets/${targetId}`, { method: 'DELETE' });
	},
	targetReport(targetId: number) {
		return request<TargetReport>(`/aura/targets/${targetId}/report`);
	},
	targetReportAttachments(targetId: number) {
		return request<ReportAttachment[]>(`/aura/targets/${targetId}/attachments`);
	},
	async uploadTargetReportAttachment(targetId: number, kind: 'blank_test' | 'problem_solving', file: File) {
		const query = new URLSearchParams({ kind, filename: file.name || 'image.jpg' });
		const response = await fetch(`${API_BASE}/api/personal/aura/targets/${targetId}/attachments?${query}`, {
			method: 'POST', credentials: 'include', headers: { 'Content-Type': file.type || 'image/jpeg' }, body: file
		});
		if (!response.ok) {
			const body = await response.json().catch(() => null);
			throw new PersonalApiError(response.status, typeof body?.detail === 'string' ? body.detail : '이미지 저장에 실패했습니다.');
		}
		return response.json() as Promise<{ id: number; kind: string; name: string; mimeType: string }>;
	},
	deleteTargetReportAttachment(id: number) {
		return request<void>(`/aura/report-attachments/${id}`, { method: 'DELETE' });
	},
	targetReportAttachmentUrl(id: number) { return `${API_BASE}/api/personal/aura/report-attachments/${id}`; },
	aiReportModels() {
		return request<{ defaultModel: string; models: AiReportModel[] }>('/aura/ai/models');
	},
	aiReportResults(targetId: number) {
		return request<{ targetId: number; results: AiReportResult[] }>(
			`/aura/targets/${targetId}/ai-reports`
		);
	},
	generateAiReports(
		targetId: number,
		body: {
			model: string;
			score_mode: 'auto' | 'none';
			assessment_items?: Array<{ name: string; score: number }>;
			force?: boolean;
			highlight_semantics?: { yellow: 'fixed' | 'unfixed' | 'not_reasked'; orange: 'fixed' | 'unfixed' | 'not_reasked'; peach: 'fixed' | 'unfixed' | 'not_reasked' };
			include_question_checks?: boolean;
		}
	) {
		return request<{
			targetId: number;
			defaultModel: string;
			results: AiReportResult[];
			errors: Array<{ model: string; message: string }>;
		}>(`/aura/targets/${targetId}/ai-reports/generate`, { method: 'POST', body });
	},
	updateTargetReport(reportId: number, body: Record<string, unknown>) {
		return request<TargetReport>(`/aura/target-reports/${reportId}`, {
			method: 'PATCH',
			body
		});
	},
	kakaoStatus() {
		return request<{ connected: boolean; kakaoUserId: string | null }>('/kakao/status');
	},
	kakaoConnectUrl(returnTo: string) {
		return request<{ url: string; redirectUri: string }>(
			`/kakao/connect-url?return_to=${encodeURIComponent(returnTo)}`
		);
	},
	kakaoSendMe(body: { title: string; description: string; link_url: string; image_urls?: string[] }) {
		return request<{ sent: boolean; sentCount: number; totalCount: number }>('/kakao/send-me', { method: 'POST', body });
	},
	submitTargetReport(reportId: number) {
		return request<TargetReport>(`/aura/target-reports/${reportId}/submit`, {
			method: 'POST'
		});
	},
	saveRoundTemplate(schoolId: number, roundNumber: number, contentJson: unknown) {
		return request<{ version: number }>(
			`/aura/schools/${schoolId}/rounds/${roundNumber}/template`,
			{ method: 'POST', body: { content_json: contentJson } }
		);
	}
};
