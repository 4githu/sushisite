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

export async function checkPersonalAuth(): Promise<PersonalUser | null> {
	const response = await fetchAuth('/auth/isjwt?key=mainauth');
	if (response.status === 401 || response.status === 403) return null;
	if (!response.ok) {
		throw new PersonalApiError(
			response.status,
			`로그인 상태를 확인하지 못했습니다. / Could not verify login. (${response.status})`,
			'auth_check_failed'
		);
	}
	return response.json();
}

export async function loginPersonal(email: string, password: string): Promise<PersonalUser> {
	const response = await fetchAuth('/auth/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ email, password })
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
}
