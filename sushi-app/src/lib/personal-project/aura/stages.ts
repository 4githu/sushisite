export const progressStages = [
	'accepted',
	'grade1_winter',
	'grade1_semester1_midterm',
	'grade1_semester1_final',
	'grade1_summer',
	'grade1_semester2_midterm',
	'grade1_semester2_final',
	'grade2_winter',
	'grade2_semester1_midterm',
	'grade2_semester1_final',
	'grade2_summer',
	'grade2_semester2_midterm',
	'grade2_semester2_final',
	'grade3_winter',
	'grade3_semester1_midterm',
	'grade3_semester1_final',
	'deep'
] as const;

export type LegacyProgressStage =
	| 'grade1_semester1'
	| 'grade1_semester2'
	| 'grade2_semester1'
	| 'grade2_semester2'
	| 'grade3_semester1';
export type CurrentProgressStage = (typeof progressStages)[number];
export type ProgressStage = CurrentProgressStage | LegacyProgressStage;

export const progressStageLabels: Record<string, string> = {
	accepted: '합격자반',
	grade1_winter: '1학년 · 겨울방학',
	grade1_semester1_midterm: '1학년 · 1학기 중간고사',
	grade1_semester1_final: '1학년 · 1학기 기말고사',
	grade1_summer: '1학년 · 여름방학',
	grade1_semester2_midterm: '1학년 · 2학기 중간고사',
	grade1_semester2_final: '1학년 · 2학기 기말고사',
	grade2_winter: '2학년 · 겨울방학',
	grade2_semester1_midterm: '2학년 · 1학기 중간고사',
	grade2_semester1_final: '2학년 · 1학기 기말고사',
	grade2_summer: '2학년 · 여름방학',
	grade2_semester2_midterm: '2학년 · 2학기 중간고사',
	grade2_semester2_final: '2학년 · 2학기 기말고사',
	grade3_winter: '3학년 · 겨울방학',
	grade3_semester1_midterm: '3학년 · 1학기 중간고사',
	grade3_semester1_final: '3학년 · 1학기 기말고사',
	deep: '심층',
	// Existing school and clinic records may still carry the previous unsplit values.
	grade1_semester1: '1학년 · 1학기',
	grade1_semester2: '1학년 · 2학기',
	grade2_semester1: '2학년 · 1학기',
	grade2_semester2: '2학년 · 2학기',
	grade3_semester1: '3학년 · 1학기'
};

export function normalizeProgressStage(stage: string): CurrentProgressStage {
	const aliases: Record<string, CurrentProgressStage> = {
		grade1_semester1: 'grade1_semester1_midterm',
		grade1_semester2: 'grade1_semester2_midterm',
		grade2_semester1: 'grade2_semester1_midterm',
		grade2_semester2: 'grade2_semester2_midterm',
		grade3_semester1: 'grade3_semester1_midterm'
	};
	return aliases[stage] ?? (stage as CurrentProgressStage);
}

export function availableProgressStages(current: ProgressStage) {
	return progressStages.slice(0, progressStages.indexOf(normalizeProgressStage(current)) + 1);
}
