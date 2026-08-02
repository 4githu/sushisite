export type ProductMode = 'education' | 'presentation';

export type WordTiming = {
	transcriptIndex: number;
	text: string;
	startSec: number;
	endSec: number;
	sttConfidence: number;
};

export type WordResult = {
	expected?: string | null;
	recognized?: string | null;
	status: string;
	location?: {
		displayCharPosition?: number | null;
		displayLabel?: string | null;
		targetStartCharIndex?: number | null;
		targetEndCharIndexExclusive?: number | null;
	};
	observation?: {
		message: string;
	};
	practice?: {
		tip?: string | null;
		articulationTipId?: string | null;
		practiceResourceId?: string | null;
	};
};

export type VoiceEvaluationResponse = {
	analysisStatus: string;
	requiresRetry: boolean;
	retryReason?: string | null;
	needsRepractice: boolean;
	targetText?: string | null;
	transcript: string;
	confidenceNote: string;
	score: {
		overallScore?: number | null;
		textMatchScore?: number | null;
		timingScore?: number | null;
		pauseScore?: number | null;
		fluencyScore?: number | null;
		deliveryScore?: number | null;
		scoreBasis: string;
		matchedSyllableCount: number;
		totalTargetSyllableCount: number;
	};
	words: WordTiming[];
	wordResults: WordResult[];
	metrics?: {
		durationSec: number;
		speechDurationSec: number;
		silenceRatio: number;
		longPauseCount: number;
		speakingRateCpm?: number | null;
		fillerCount: number;
	} | null;
	feedback: {
		status: string;
		summary?: string | null;
		nextAction?: string | null;
	};
};

export type GraphPoint = {
	frequency_hz?: number;
	magnitude_db?: number;
	frequencyHz?: number;
	magnitudeDb?: number;
};

export type WordEvaluationResponse = {
	score: number;
	distance: number;
	feedback: string;
	user_formants?: Record<string, number>;
	target_formants?: Record<string, number>;
	userFormants?: Record<string, number>;
	targetFormants?: Record<string, number>;
	delta: Record<string, number>;
	graph: {
		user: GraphPoint[];
		target: GraphPoint[];
	};
};
