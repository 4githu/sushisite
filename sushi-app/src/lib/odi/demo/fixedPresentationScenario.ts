import type { JsonObject } from "$lib/odi/stores/odiuser";
import type { PresentationTemplate } from "$lib/odi/stores/template";

export const FIXED_DEMO_SCENARIO_ID = "ai-audience-v2";

/** Unity 통신 없이도 같은 장면과 결과를 재현하기 위한 발표 시연 시나리오입니다. */
export function createFixedDemoPresentationTemplate(): PresentationTemplate {
	return {
		type: "presentation",
		description: "[시연 고정] AI 청중 반응 파이프라인 v2 소개",
		environment: {
			title: "AI 청중 반응 파이프라인 v2",
			purpose: "프로젝트 목적",
			language: "한국어",
			place: "세미나실",
			duration_minutes: 2,
			question_count: 2
		},
		files: {
			slide: null,
			paper: null,
			script: null,
			script_content: "AI 청중 반응 파이프라인 v2는 발표 음성, 슬라이드, 시선 신호를 결합해 여섯 명의 AI 청중 반응을 보여주고 사후 리포트로 개선점을 정리합니다."
		},
		audience: {
			audience_type: "일반 청중",
			audience_count: 6,
			expertise_level: "중간",
			interest_level: "중간"
		}
	};
}

export const fixedDemoFeedback: JsonObject = {
	version: "fixed-demo-v1",
	score: { overall_score: 86, percentile: 12, grade: "우수" },
	duration: { planned_seconds: 120, actual_seconds: 116, qa_seconds: 28 },
	score_card: {
		scores: { engagement: 88, clarity: 84, credibility: 86 },
		descriptions: {
			engagement: "문제 정의와 핵심 메시지가 청중의 관심을 안정적으로 이끌었습니다.",
			clarity: "입력 신호와 결과를 순서대로 설명해 흐름을 이해하기 쉬웠습니다.",
			credibility: "음성·슬라이드·시선 신호를 함께 활용한 근거가 설득력을 높였습니다."
		}
	},
	detail_analysis: {
		highlight_metrics: [
			{ name: "시선 처리", score: 91 },
			{ name: "핵심 메시지", score: 88 },
			{ name: "발화 속도", score: 84 },
			{ name: "Q&A 대응", score: 82 }
		],
		content_analysis: { organization: 86, supporting_material: 84, central_message: 88, cer_validity: 83 },
		delivery_analysis: { language_clarity: 85, vocal_delivery: 84, gaze_delivery: 91, slide_speech_alignment: 82 }
	},
	timeline: [
		{ time_sec: 12, title: "도입이 명확해요", description: "발표의 문제와 목표를 짧게 제시해 청중이 바로 맥락을 잡았습니다.", type: "positive" },
		{ time_sec: 34, title: "입력 신호를 구분해 보세요", description: "음성·슬라이드·시선 데이터의 역할을 한 문장씩 나누면 더 선명해집니다.", type: "warning" },
		{ time_sec: 57, title: "핵심 구조 설명이 좋아요", description: "실시간 반응과 사후 리포트의 연결을 자연스럽게 설명했습니다.", type: "positive" },
		{ time_sec: 78, title: "전환 구간은 천천히", description: "다음 단계로 넘어가기 전 짧게 호흡을 두면 전달력이 높아집니다.", type: "warning" },
		{ time_sec: 101, title: "시선 유지가 좋습니다", description: "핵심 메시지에서 안정적으로 정면 시선을 유지했습니다.", type: "positive" }
	],
	audience_analysis: {
		graph: [
			{ time_sec: 0, E: 0.66, V: 0.57, C: 0.61 }, { time_sec: 15, E: 0.78, V: 0.70, C: 0.72 },
			{ time_sec: 30, E: 0.74, V: 0.68, C: 0.75 }, { time_sec: 45, E: 0.85, V: 0.81, C: 0.83 },
			{ time_sec: 60, E: 0.82, V: 0.78, C: 0.84 }, { time_sec: 75, E: 0.71, V: 0.67, C: 0.76 },
			{ time_sec: 90, E: 0.87, V: 0.84, C: 0.88 }, { time_sec: 105, E: 0.83, V: 0.80, C: 0.86 },
			{ time_sec: 116, E: 0.80, V: 0.78, C: 0.85 }
		],
		events: [
			{ time_sec: 12, label: "문제 정의", type: "positive" }, { time_sec: 48, label: "파이프라인 설명", type: "positive" },
			{ time_sec: 73, label: "전환 속도", type: "warning" }, { time_sec: 95, label: "핵심 메시지", type: "positive" }
		]
	},
	ai_insight: {
		title: "핵심 메시지를 먼저 제시한 뒤 근거를 덧붙이는 흐름이 좋았어요.",
		description: "중반의 파이프라인 설명과 후반의 사용자 가치 연결이 안정적입니다. 다음에는 단계 전환마다 짧은 호흡을 두고 결론의 기대 효과를 한 문장 더 강조해 보세요."
	}
};
