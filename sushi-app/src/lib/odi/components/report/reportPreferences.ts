export type ReportViewVersion = 'v1' | 'v2' | 'v3';
export type AvailableReportViewVersion = ReportViewVersion;
export type STTProviderPreference = 'deepgram' | 'azure';

export const DEFAULT_REPORT_VIEW_VERSION: AvailableReportViewVersion = 'v3';

export function resolveReportViewVersion(value: unknown): AvailableReportViewVersion {
	return value === 'v1' || value === 'v2' || value === 'v3'
		? value
		: DEFAULT_REPORT_VIEW_VERSION;
}

export function resolveTimelineVideoPreference(value: unknown): boolean {
	return value !== false;
}

export function resolveSTTProviderPreference(value: unknown): STTProviderPreference {
	return value === 'azure' ? 'azure' : 'deepgram';
}
