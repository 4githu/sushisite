import { API_BASE, PersonalApiError } from './api';

export type PersonalUser = {
	sub: string;
	data: {
		id: string;
		name?: string;
		email?: string;
	};
	exp: number;
};

async function fetchAuth(path: string, options: RequestInit = {}) {
	try {
		return await fetch(`${API_BASE}${path}`, {
			...options,
			signal: options.signal ?? AbortSignal.timeout(10000),
			credentials: 'include'
		});
	} catch (cause) {
		throw new PersonalApiError(
			0,
			'백엔드 서버에 연결할 수 없습니다. / Cannot connect to the backend server.',
			'backend_unreachable',
			cause
		);
	}
}

let cachedUser: PersonalUser | null = null;
let verifiedAt = 0;
let pending: Promise<PersonalUser | null> | null = null;
let generation = 0;
export function invalidatePersonalAuth() {
	cachedUser = null;
	verifiedAt = 0;
	pending = null;
	generation++;
}
if (typeof window !== 'undefined') {
	window.addEventListener('personal-auth-invalid', invalidatePersonalAuth);
	window.addEventListener('storage', (event) => {
		if (event.key === 'personal-auth-reset') invalidatePersonalAuth();
	});
}
export async function checkPersonalAuth(): Promise<PersonalUser | null> {
	if (typeof window === 'undefined') return null;
	if (cachedUser && Date.now() - verifiedAt < 30000 && cachedUser.exp * 1000 > Date.now())
		return cachedUser;
	if (pending) return pending;
	const version = generation;
	const operation = (async () => {
		const response = await fetchAuth('/auth/isjwt?key=mainauth', { cache: 'no-store' });
		if (version !== generation) return null;
		if (response.status === 401 || response.status === 403) {
			invalidatePersonalAuth();
			return null;
		}
		if (!response.ok)
			throw new PersonalApiError(
				response.status,
				'로그인 상태를 확인하지 못했습니다. 잠시 후 다시 시도해주세요.',
				'auth_check_failed'
			);
		const user: PersonalUser = await response.json();
		if (version !== generation) return null;
		cachedUser = user;
		verifiedAt = Date.now();
		return user;
	})();
	pending = operation;
	try {
		return await operation;
	} finally {
		if (pending === operation) pending = null;
	}
}

export async function loginPersonal(email: string, password: string): Promise<PersonalUser> {
	const normalizedEmail = email.trim().toLowerCase();
	const response = await fetchAuth('/auth/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ email: normalizedEmail, password })
	});
	const result = await response.json().catch(() => null);
	if (!response.ok) {
		throw new PersonalApiError(
			response.status,
			`로그인 요청에 실패했습니다. / Login request failed. (${response.status})`,
			'login_failed',
			result
		);
	}
	if (!result?.success) {
		throw new PersonalApiError(
			401,
			'이메일 또는 비밀번호가 올바르지 않습니다. / Invalid email or password.',
			'invalid_credentials'
		);
	}
	invalidatePersonalAuth();
	const user = await checkPersonalAuth();
	if (!user) {
		throw new PersonalApiError(
			401,
			'로그인 쿠키를 확인할 수 없습니다. / Login cookie was not found.',
			'cookie_missing'
		);
	}
	return user;
}

export async function logoutPersonal() {
	const response = await fetchAuth('/auth/logout', { method: 'POST' });
	if (!response.ok) {
		throw new PersonalApiError(
			response.status,
			'로그아웃하지 못했습니다. / Could not sign out.',
			'logout_failed'
		);
	}
	invalidatePersonalAuth();
	try {
		localStorage.setItem('personal-auth-reset', String(Date.now()));
	} catch {
		/* Storage may be unavailable. */
	}
}
