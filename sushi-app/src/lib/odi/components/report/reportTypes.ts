// src/lib/odi/components/report/reportTypes.ts

export type ReportScore = {
	overall_score?: number;
	percentile?: number | null;
	grade?: string;
	previous_session_delta?: number | null;
};

export type ReportComparison = {
	account_average?: {
		overall_score: number;
		engagement: number;
		clarity: number;
		credibility: number;
		session_count: number;
	} | null;
	previous_session?: {
		session_id: string;
		overall_score: number;
		score_delta: number;
	} | null;
};

export type ReportDuration = {
	planned_seconds?: number;
	actual_seconds?: number;
	qa_seconds?: number;
};

export type ReportScoreCard = {
	scores?: {
		engagement?: number;
		clarity?: number;
		credibility?: number;
	};
	descriptions?: {
		engagement?: string;
		clarity?: string;
		credibility?: string;
	};
	/** Compatibility-only field from early V2 fixtures. New responses use session.comparison. */
	average_scores?: {
		engagement?: number;
		clarity?: number;
		credibility?: number;
	};
};

export type ReportTimelineItem = {
	time_sec: number;
	title: string;
	description: string;
	type: 'positive' | 'warning' | 'negative' | string;
	slide?: number;
	end_sec?: number;
	source_step?: number;
	evidence_ids?: string[];
	reaction_ids?: string[];
	metric_impacts?: Partial<Record<'engagement' | 'clarity' | 'credibility', number>>;
};

export type ReportEvidence = {
	evidence_id: string;
	source_step: number;
	start_sec: number;
	end_sec: number;
	slide: number;
	transcript_excerpt: string;
	evaluation_summary: string;
	metric_impacts: Partial<Record<'engagement' | 'clarity' | 'credibility', number>>;
	confidence: number;
	missing_inputs?: string[];
};

export type ReportReactionTrace = {
	reaction_id: string;
	sequence: number;
	time_sec: number;
	source_steps: number[];
	evidence_ids: string[];
	audiences?: unknown[];
	commands?: unknown[];
};

export type ReportInsightItem = {
	title: string;
	description: string;
	action: string;
	metric?: 'engagement' | 'clarity' | 'credibility' | null;
	evidence_ids?: string[];
};

export type AudienceGraphPoint = {
	time_sec: number;
	E: number;
	V: number;
	C: number;
};

export type ReportMedia = {
	/** Added by the server for session-scoped media. Absent on legacy reports. */
	version?: string;
	session_id?: string;
	video_url?: string;
	title?: string;
	source?: 'demo' | 'recording' | 'upload' | 'external' | string;
	storage_path?: string;
	mime_type?: string | null;
	size_bytes?: number;
};

export type ReportQaQuestion = {
	question_index?: number;
	question?: string;
	intent?: string;
	time_sec?: number;
	answer?: string;
	answer_end_sec?: number;
	answer_duration_sec?: number;
	scores?: {
		understanding?: number;
		clarity?: number;
		evidence?: number;
	};
	strength?: string;
	improvement?: string;
	suggested_answer?: string;
};

export type ReportQaFeedback = {
	score?: number;
	summary?: string;
	average_answer_seconds?: number;
	questions?: ReportQaQuestion[];
};

export type ReportTraining = {
	id?: string;
	title?: string;
	description?: string;
	duration_minutes?: number;
	type?: string;
	priority?: boolean;
	evidence_ids?: string[];
};

export type ReportDetailMetric = {
	id: string;
	label?: string;
	score?: number | null;
	reason?: string | null;
	/** Compatibility aliases used only while reading early V2 fixtures. */
	rank_label?: string | null;
	status?: 'available' | 'unavailable';
	summary?: string | null;
	evidence_ids?: string[];
	coaching?: string | null;
};

export type ReportFeedback = {
	version?: string;
	generation?: {
		generated_at?: string;
		generator?: string;
		source_segment_count?: number;
		source_reaction_count?: number;
		transcript_word_count?: number;
		warnings?: string[];
		stt_provider?: 'deepgram' | 'azure' | null;
	};
	score?: ReportScore;
	duration?: ReportDuration;
	score_card?: ReportScoreCard;
	detail_analysis?: {
		highlight_metrics?: {
			name: string;
			score: number;
		}[];
		content_analysis?: Record<string, number>;
		delivery_analysis?: Record<string, number>;
		content_metrics?: ReportDetailMetric[];
		delivery_metrics?: ReportDetailMetric[];
	};
	timeline?: ReportTimelineItem[];
	audience_analysis?: {
		graph?: AudienceGraphPoint[];
		events?: {
			time_sec: number;
			label: string;
			type?: string;
			source_step?: number;
		}[];
	};
	ai_insight?: {
		title?: string;
		description?: string;
		strengths?: ReportInsightItem[];
		improvements?: ReportInsightItem[];
	};
	/** Optional v3 fields. Legacy reports render useful fallbacks when they are absent. */
	qa_feedback?: ReportQaFeedback;
	recommended_trainings?: ReportTraining[];
	media?: ReportMedia;
	qa_history?: { question_index: number; question: string; intent?: string; answer: string }[];
	evidence?: ReportEvidence[];
	reaction_trace?: ReportReactionTrace[];
};

export type ReportTemplateFileRef = {
	storage_path?: string | null;
	original_name?: string | null;
	mime_type?: string | null;
	size_bytes?: number | null;
	status?: 'temp' | 'committed';
	page_count?: number | null;
	image_manifest_path?: string | null;
};

export type ReportTemplate = {
	type?: 'presentation' | 'interview';
	environment?: Record<string, any>;
	files?: {
		slide?: ReportTemplateFileRef | null;
		paper?: ReportTemplateFileRef | null;
		script?: ReportTemplateFileRef | null;
		script_content?: string | null;
	};
	audience?: Record<string, any>;
};

export type ReportSession = {
	session_id: string;
	user_id: string;
	template_id: string | null;
	template: ReportTemplate;
	feedback: ReportFeedback | null;
	state: string;
	started_at: string | null;
	ended_at: string | null;
	created_at: string;
	updated_at: string;
	comparison?: ReportComparison;
};
