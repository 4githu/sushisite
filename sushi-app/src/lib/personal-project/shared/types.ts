import type { AnalysisDocument, EditorDocument } from '$lib/textediter/types';

export type EventStatus = 'passive' | 'todo' | 'done';
export type AttendanceStatus = 'scheduled' | 'completed' | 'cancelled' | 'absent';
export type ReportStatus = 'draft' | 'ready' | 'submitted';

export type CalendarEvent = {
	id: number;
	title: string;
	description: string;
	startTime: string;
	endTime: string | null;
	isAllDay: boolean;
	status: EventStatus;
	type: string;
	groupName: string | null;
	categoryName: string | null;
	serviceLink?: string | null;
	recurrenceGroupId: string | null;
	recurrenceIndex: number | null;
};

export type Student = {
	id: number;
	name: string;
	schoolName: string;
	affiliation: string;
	memo: string;
	isActive: boolean;
};

export type AuraReport = {
	id: number;
	status: ReportStatus;
	contentJson: EditorDocument;
	analysisJson: AnalysisDocument;
	sourceNotes: string;
	submittedAt: string | null;
};

export type AuraSession = {
	id: number;
	eventId: number;
	studentId: number;
	studentName: string;
	schoolName: string;
	title: string;
	description: string;
	startTime: string;
	endTime: string | null;
	attendanceStatus: AttendanceStatus;
	reportRequired: boolean;
	hourlyRate: number;
	amount: number;
	paymentStatus: 'pending' | 'paid';
	report: AuraReport | null;
};

export type Settlement = {
	year: number;
	month: number;
	totalAmount: number;
	completedCount: number;
	items: AuraSession[];
};

export type School = {
	id: number;
	name: string;
	defaultHourlyRate: number;
	memo: string;
	isActive: boolean;
	roundCount: number;
	priority: number;
	termStatus: 'active' | 'ended';
	rounds?: ClinicRound[];
};

export type RoundTarget = {
	id: number;
	studentName: string;
	report: {
		id: number;
		status: ReportStatus;
		templateVersion: number | null;
		submittedAt: string | null;
	} | null;
};

export type ClinicRound = {
	id: number;
	schoolId: number;
	schoolName: string;
	eventId: number;
	roundNumber: number;
	roundNumbers: number[];
	roundLabel: string;
	startTime: string;
	endTime: string;
	description: string;
	attendanceStatus: 'scheduled' | 'completed' | 'cancelled';
	reportRequired: boolean;
	hourlyRate: number;
	amount: number;
	paymentStatus: 'pending' | 'paid';
	seriesGroupId: string | null;
	seriesIndex: number | null;
	targets: RoundTarget[];
};

export type SchoolSettlement = {
	year: number;
	month: number;
	totalAmount: number;
	completedCount: number;
	items: ClinicRound[];
};

export type TargetReport = {
	id: number;
	targetId: number;
	studentName: string;
	schoolId: number;
	schoolName: string;
	roundNumber: number;
	roundNumbers: number[];
	roundLabel: string;
	startTime: string;
	endTime: string;
	templateVersion: number | null;
	contentJson: EditorDocument;
	analysisJson: AnalysisDocument;
	sourceNotes: string;
	questionChecks: Record<string, boolean>;
	lectureProgress: number;
	lectureComprehension: number;
	memoryBefore: number;
	memoryAfter: number;
	assessmentJson: null | {
		formatName?: string;
		items?: Array<{ name: string; score: number }>;
	};
	generatedReportJson: AiReportOutput | null;
	aiModel: string | null;
	clinicTargets: Array<{
		id: number;
		studentName: string;
		status: ReportStatus | 'unwritten';
	}>;
	status: ReportStatus;
	submittedAt: string | null;
};

export type AiReportOutput = {
	schemaVersion: 'aura.clinic-report-output.v2';
	target: Record<string, unknown>;
	assessment: null | {
		formatName: string;
		items: Array<{ name: string; score: number }>;
	};
	learningContent: { paragraphs: string[] };
	problemSolvingNote?: string;
};

export type AiReportResult = {
	runId: number;
	provider: string;
	model: string;
	cacheMode: 'implicit' | 'explicit';
	reused: boolean;
	inputHash?: string;
	completedAt?: string;
	cacheNotice?: string | null;
	output: AiReportOutput;
};

export type AiReportModel = {
	id: string;
	provider: string;
	label: string;
	description: string;
	is_default: boolean;
	explicit_cache: boolean;
	available?: boolean;
	unavailable_reason?: string | null;
};
