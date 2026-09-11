export const progressStages = [
	'accepted',
	'grade1_winter',
	'grade1_semester1',
	'grade1_summer',
	'grade1_semester2',
	'grade2_winter',
	'grade2_semester1',
	'grade2_summer',
	'grade2_semester2',
	'grade3_winter',
	'grade3_semester1',
	'deep'
] as const;

export type ProgressStage = (typeof progressStages)[number];

export const progressStageLabels: Record<ProgressStage, string> = {
	accepted: '합격자반',
	grade1_winter: '1학년 · 겨울방학',
	grade1_semester1: '1학년 · 1학기',
	grade1_summer: '1학년 · 여름방학',
	grade1_semester2: '1학년 · 2학기',
	grade2_winter: '2학년 · 겨울방학',
	grade2_semester1: '2학년 · 1학기',
	grade2_summer: '2학년 · 여름방학',
	grade2_semester2: '2학년 · 2학기',
	grade3_winter: '3학년 · 겨울방학',
	grade3_semester1: '3학년 · 1학기',
	deep: '심층'
};

export function availableProgressStages(current: ProgressStage) {
	return progressStages.slice(0, progressStages.indexOf(current) + 1);
}
