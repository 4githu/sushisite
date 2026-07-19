// src/lib/odi/components/report/reportTypes.ts

export type ReportScore = {
	overall_score?: number;
	percentile?: number;
	grade?: string;
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
};

export type ReportTimelineItem = {
	time_sec: number;
	title: string;
	description: string;
	type: "positive" | "warning" | "negative" | string;
	slide?: number;
};

export type AudienceGraphPoint = {
	time_sec: number;
	E: number;
	V: number;
	C: number;
};

export type ReportFeedback = {
	version?: string;
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
	};
	timeline?: ReportTimelineItem[];
	audience_analysis?: {
		graph?: AudienceGraphPoint[];
		events?: {
			time_sec: number;
			label: string;
			type?: string;
		}[];
	};
	ai_insight?: {
		title?: string;
		description?: string;
	};
};

export type ReportTemplateFileRef = {
	storage_path?: string | null;
	original_name?: string | null;
	mime_type?: string | null;
	size_bytes?: number | null;
	status?: "temp" | "committed";
	page_count?: number | null;
	image_manifest_path?: string | null;
};

export type ReportTemplate = {
	type?: "presentation" | "interview";
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
};