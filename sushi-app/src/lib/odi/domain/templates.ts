import type { OdiTemplate } from '../stores/template';
export type StoredTemplate = {
	template_id: string;
	template: OdiTemplate;
	version: number;
	created_at: string;
	updated_at: string;
	last_used_at: string | null;
	use_count: number;
};
export function templateTitle(value: OdiTemplate) {
	return value.type === 'presentation'
		? value.environment.title || '제목 없는 발표'
		: value.environment.position || value.environment.company_name || '제목 없는 면접';
}
