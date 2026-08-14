const configuredApi = (import.meta.env.VITE_SUSHIFASTURL || '').replace(/\/$/, '');

/**
 * 브라우저에서 localhost는 접속한 사용자의 기기를 뜻합니다.
 * 개발/터널 배포에서는 같은 origin의 Vite 프록시를 사용합니다.
 */
export const API_BASE = /^(https?:\/\/)?(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configuredApi)
	? ''
	: configuredApi;
