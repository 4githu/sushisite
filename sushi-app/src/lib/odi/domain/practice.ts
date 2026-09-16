export type PracticeExercise = {
	id: string;
	title: string;
	group: string;
	task: string;
	available: boolean;
};
export type PracticeAttempt = {
	attempt_id: string;
	metric_id: string;
	state: 'queued' | 'analyzing' | 'completed' | 'failed';
	duration_seconds: number;
	transcript: string | null;
	score: number | null;
	feedback: { score: number; feedback: string; evidence: string } | null;
	error: string | null;
	created_at: string;
	completed_at: string | null;
};
export type PracticeData = {
	catalog: PracticeExercise[];
	attempts: PracticeAttempt[];
	progress: {
		metrics: Record<string, { level: number; successes: number; next_progress: number }>;
		weekly_successes: number;
		weekly_target: number;
		completed_count: number;
		total_seconds: number;
	};
};
