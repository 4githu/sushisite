// src/lib/odi/stores/template.ts

import { derived, get, writable } from "svelte/store";
import { odiuser, type JsonObject } from "./odiuser";

export type TemplateType = "presentation" | "interview";

export type OdiFileStatus = "temp" | "committed";

export type OdiFileRef = {
	storage_path: string | null;
	original_name: string | null;
	mime_type: string | null;
	size_bytes: number | null;
	status: OdiFileStatus;
	uploaded_at?: string | null;
	expires_at?: string | null;
	page_count?: number | null;
	image_manifest_path?: string | null;
};

export type OdiTemplateFiles = {
	slide: OdiFileRef | null;
	paper: OdiFileRef | null;
	script: OdiFileRef | null;
	script_content: string | null;
};

export type PresentationTemplate = {
	id?: string;
	owner_id?: string;
	type: "presentation";
	description?: string;
	created_at?: string;
	updated_at?: string;
	file_bundle_id?: string;
	file_bundle_path?: string;
	file_bundle_expires_at?: string;

	environment: {
		title: string;
		purpose: string;
		language: string;
		place: string;
		duration_minutes: number;
		question_count: number;
	};

	files: OdiTemplateFiles;

	audience: {
		audience_type: string;
		audience_count: number;
		expertise_level: string;
		interest_level: string;
	};
};

export type InterviewTemplate = {
	id?: string;
	owner_id?: string;
	type: "interview";
	description?: string;
	created_at?: string;
	updated_at?: string;
	file_bundle_id?: string;
	file_bundle_path?: string;
	file_bundle_expires_at?: string;

	environment: {
		company_name: string;
		department: string;
		position: string;
		job_detail: string;
		language: string;
		duration_minutes: number;
		interview_context: string;
		interviewer_count: number;
		answer_order: string;
	};

	files: OdiTemplateFiles;

	audience: {
		interviewer_persona: string;
		interview_style: string;
	};
};

export type OdiTemplate = PresentationTemplate | InterviewTemplate;

const draftStore = writable<OdiTemplate | null>(null);
const savedSnapshotStore = writable<string | null>(null);

function clone<T>(value: T): T {
	return value === null ? value : JSON.parse(JSON.stringify(value));
}

function stableStringify(value: unknown) {
	return JSON.stringify(value ?? null);
}

function createEmptyFiles(): OdiTemplateFiles {
	return {
		slide: null,
		paper: null,
		script: null,
		script_content: null
	};
}

function migrateFiles(files: any): OdiTemplateFiles {
	if (!files) return createEmptyFiles();

	return {
		slide: files.slide ?? (files.slide_path ? {
			storage_path: files.slide_path,
			original_name: files.slide_path.split("/").at(-1) ?? "slide.pdf",
			mime_type: "application/pdf",
			size_bytes: null,
			status: "committed",
			uploaded_at: null,
			expires_at: null,
			page_count: null,
			image_manifest_path: null
		} : null),

		paper: files.paper ?? (files.paper_path ? {
			storage_path: files.paper_path,
			original_name: files.paper_path.split("/").at(-1) ?? "paper.pdf",
			mime_type: "application/pdf",
			size_bytes: null,
			status: "committed",
			uploaded_at: null,
			expires_at: null,
			page_count: null,
			image_manifest_path: null
		} : null),

		script: files.script ?? (files.script_path ? {
			storage_path: files.script_path,
			original_name: files.script_path.split("/").at(-1) ?? "script.txt",
			mime_type: "text/plain",
			size_bytes: null,
			status: "committed",
			uploaded_at: null,
			expires_at: null,
			page_count: null,
			image_manifest_path: null
		} : null),

		script_content: files.script_content ?? null
	};
}

function migrateTemplate(value: OdiTemplate): OdiTemplate {
	const copied = clone(value) as any;

	copied.files = migrateFiles(copied.files);

	return copied as OdiTemplate;
}

export function createDefaultPresentationTemplate(): PresentationTemplate {
	return {
		type: "presentation",
		description: "",

		environment: {
			title: "",
			purpose: "",
			language: "한국어",
			place: "",
			duration_minutes: 10,
			question_count: 3
		},

		files: createEmptyFiles(),

		audience: {
			audience_type: "",
			audience_count: 6,
			expertise_level: "중간",
			interest_level: "중간"
		}
	};
}

export function createDefaultInterviewTemplate(): InterviewTemplate {
	return {
		type: "interview",
		description: "",

		environment: {
			company_name: "",
			department: "",
			position: "",
			job_detail: "",
			language: "한국어",
			duration_minutes: 30,
			interview_context: "",
			interviewer_count: 2,
			answer_order: ""
		},

		files: createEmptyFiles(),

		audience: {
			interviewer_persona: "",
			interview_style: ""
		}
	};
}

export const template = {
	subscribe: draftStore.subscribe,

	get() {
		return get(draftStore);
	},

	set(value: OdiTemplate | null) {
		const copied = value === null ? null : migrateTemplate(value);
		draftStore.set(copied);
	},

	clear() {
		draftStore.set(null);
		savedSnapshotStore.set(null);
	},

	resetToSaved() {
		const snapshot = get(savedSnapshotStore);

		if (snapshot === null) {
			draftStore.set(null);
			return;
		}

		draftStore.set(JSON.parse(snapshot));
	},

	setDefault(type: TemplateType) {
		const next = type === "presentation"
			? createDefaultPresentationTemplate()
			: createDefaultInterviewTemplate();

		draftStore.set(next);
		savedSnapshotStore.set(stableStringify(next));
	},

	loadFromRecent() {
		const user = odiuser.get();
		const recent = user?.recent_template ?? null;

		if (recent === null) {
			draftStore.set(null);
			savedSnapshotStore.set(null);
			return null;
		}

		const copied = migrateTemplate(recent as OdiTemplate);
		draftStore.set(copied);
		savedSnapshotStore.set(stableStringify(copied));

		return copied;
	},

	loadOrCreate(type: TemplateType = "presentation") {
		const loaded = this.loadFromRecent();

		if (loaded !== null) {
			return loaded;
		}

		const next = type === "presentation"
			? createDefaultPresentationTemplate()
			: createDefaultInterviewTemplate();

		draftStore.set(next);
		savedSnapshotStore.set(stableStringify(next));

		return next;
	},

	patch(partial: Partial<OdiTemplate>) {
		const current = get(draftStore);

		if (current === null) {
			throw new Error("수정할 템플릿 draft가 없습니다.");
		}

		const next = {
			...current,
			...partial
		} as OdiTemplate;

		draftStore.set(next);

		return next;
	},

	patchEnvironment(partial: JsonObject) {
		const current = get(draftStore);

		if (current === null) {
			throw new Error("수정할 템플릿 draft가 없습니다.");
		}

		const next = {
			...current,
			environment: {
				...current.environment,
				...partial
			}
		} as OdiTemplate;

		draftStore.set(next);

		return next;
	},

	patchFiles(partial: Partial<OdiTemplateFiles>) {
		const current = get(draftStore);

		if (current === null) {
			throw new Error("수정할 템플릿 draft가 없습니다.");
		}

		const next = {
			...current,
			files: {
				...current.files,
				...partial
			}
		} as OdiTemplate;

		draftStore.set(next);

		return next;
	},

	patchAudience(partial: JsonObject) {
		const current = get(draftStore);

		if (current === null) {
			throw new Error("수정할 템플릿 draft가 없습니다.");
		}

		const next = {
			...current,
			audience: {
				...current.audience,
				...partial
			}
		} as OdiTemplate;

		draftStore.set(next);

		return next;
	},

	async saveToRecent() {
		const current = get(draftStore);

		if (current === null) {
			throw new Error("저장할 템플릿 draft가 없습니다.");
		}

		const savedUser = await odiuser.updateRecentTemplate(clone(current));
		savedSnapshotStore.set(stableStringify(current));

		return savedUser;
	}
};

export const isTemplateDirty = derived(
	[draftStore, savedSnapshotStore],
	([$draft, $snapshot]) => stableStringify($draft) !== $snapshot
);

export const templateType = derived(
	draftStore,
	($draft) => $draft?.type ?? null
);