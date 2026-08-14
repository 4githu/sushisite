// src/lib/odi/api/files.ts

import type { OdiFileRef } from "$lib/odi/stores/template";
import { API_BASE as API } from '$lib/config/api';


export type UploadRole = "slide" | "paper" | "script";

async function fetchJson(res: Response) {
	const data = await res.json().catch(() => null);

	if (!res.ok) {
		throw new Error(data?.detail ?? data?.message ?? "요청 실패");
	}

	return data;
}

export async function uploadTempFile(file: File, role: UploadRole): Promise<OdiFileRef> {
	const formData = new FormData();

	formData.append("role", role);
	formData.append("file", file);

	const res = await fetch(`${API}/odi/files/upload-temp`, {
		method: "POST",
		credentials: "include",
		body: formData
	});

	const data = await fetchJson(res);

	if (!data?.success || !data?.file) {
		throw new Error("파일 업로드 응답이 올바르지 않습니다.");
	}

	return data.file as OdiFileRef;
}
