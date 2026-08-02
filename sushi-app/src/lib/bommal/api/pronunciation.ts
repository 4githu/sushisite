import type { ProductMode, VoiceEvaluationResponse, WordEvaluationResponse } from '$lib/bommal/types';

const API_BASE = import.meta.env.VITE_SUSHIFASTURL || 'http://localhost:8000';

async function parseApiResponse<T>(response: Response): Promise<T> {
	const body = await response.text();
	const payload = body ? JSON.parse(body) : {};

	if (!response.ok) {
		const detail = payload?.detail ?? response.statusText;
		throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
	}

	return payload as T;
}

export async function checkPronunciationHealth() {
	const response = await fetch(`${API_BASE}/pronunciation/health`);
	return parseApiResponse<{ status: string; apiVersion: string }>(response);
}

export async function analyzeSentence(params: {
	audio: File;
	mode: ProductMode;
	sessionId: string;
	attemptId: string;
	targetText?: string;
}) {
	const formData = new FormData();
	formData.append('audio', params.audio);
	formData.append('mode', params.mode);
	formData.append('session_id', params.sessionId);
	formData.append('attempt_id', params.attemptId);
	if (params.targetText) formData.append('target_text', params.targetText);

	const response = await fetch(`${API_BASE}/pronunciation/analyze`, {
		method: 'POST',
		body: formData
	});

	return parseApiResponse<VoiceEvaluationResponse>(response);
}

export async function analyzeWord(params: { audio: File; vowel: string }) {
	const formData = new FormData();
	formData.append('audio', params.audio);
	formData.append('vowel', params.vowel);

	const response = await fetch(`${API_BASE}/pronunciation/word`, {
		method: 'POST',
		body: formData
	});

	return parseApiResponse<WordEvaluationResponse>(response);
}
