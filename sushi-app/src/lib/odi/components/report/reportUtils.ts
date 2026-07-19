// src/lib/odi/components/report/reportUtils.ts

export function formatSeconds(totalSeconds: number | undefined | null) {
	const seconds = Math.max(0, Math.floor(totalSeconds ?? 0));
	const min = Math.floor(seconds / 60);
	const sec = seconds % 60;

	return `${min}:${String(sec).padStart(2, "0")}`;
}

export function formatKoreanDuration(totalSeconds: number | undefined | null) {
	const seconds = Math.max(0, Math.floor(totalSeconds ?? 0));
	const min = Math.floor(seconds / 60);
	const sec = seconds % 60;

	if (min <= 0) return `${sec}초`;
	if (sec <= 0) return `${min}분`;

	return `${min}분 ${sec}초`;
}

export function formatDateTime(value: string | null | undefined) {
	if (!value) return "날짜 정보 없음";

	const date = new Date(value);

	if (Number.isNaN(date.getTime())) return value;

	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, "0");
	const day = String(date.getDate()).padStart(2, "0");
	const hour = String(date.getHours()).padStart(2, "0");
	const minute = String(date.getMinutes()).padStart(2, "0");

	return `${year}.${month}.${day} ${hour}:${minute}`;
}

export function scoreGrade(score: number | undefined | null) {
	const value = score ?? 0;

	if (value >= 80) return "우수";
	if (value >= 65) return "보통";

	return "개선";
}

export function scoreGradeType(score: number | undefined | null) {
	const value = score ?? 0;

	if (value >= 80) return "good";
	if (value >= 65) return "normal";

	return "bad";
}

export function clampScore(score: number | undefined | null) {
	return Math.max(0, Math.min(100, score ?? 0));
}

export function safePercentValue(value: number | undefined | null) {
	return Math.max(0, Math.min(1, value ?? 0));
}

export function contentMetricLabel(key: string) {
	const map: Record<string, string> = {
		organization: "발표 구조와 흐름",
		supporting_material: "근거와 자료 활용",
		central_message: "메시지 명확성",
		cer_validity: "주장 - 근거 연결성"
	};

	return map[key] ?? key;
}

export function deliveryMetricLabel(key: string) {
	const map: Record<string, string> = {
		language_clarity: "언어 명확성",
		vocal_delivery: "발화 속도",
		gaze_delivery: "시선 처리",
		slide_speech_alignment: "슬라이드 정렬도"
	};

	return map[key] ?? key;
}

export function scoreCardLabel(key: "engagement" | "clarity" | "credibility") {
	const map = {
		engagement: "몰입도",
		clarity: "명확도",
		credibility: "신뢰도"
	};

	return map[key];
}