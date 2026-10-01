import { API_BASE } from '../shared/api';
export type Resource = {
	id: string;
	name: string;
	mimeType: string;
	byteSize: number;
	url: string;
};
export function uploadResource(
	file: File,
	boardId?: number,
	onprogress?: (percent: number) => void
): Promise<Resource> {
	return new Promise((resolve, reject) => {
		const xhr = new XMLHttpRequest();
		const query = new URLSearchParams({ name: file.name });
		if (boardId) query.set('board_id', String(boardId));
		xhr.open('POST', `${API_BASE}/api/personal/resources?${query}`);
		xhr.withCredentials = true;
		xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
		xhr.upload.onprogress = (e) => {
			if (e.lengthComputable) onprogress?.(Math.round((e.loaded / e.total) * 100));
		};
		xhr.onerror = () => reject(Error('파일 업로드 중 연결이 끊겼습니다.'));
		xhr.onload = () => {
			let result;
			try {
				result = JSON.parse(xhr.responseText);
			} catch {
				reject(Error('파일 업로드 실패'));
				return;
			}
			if (xhr.status >= 200 && xhr.status < 300) resolve(result);
			else reject(Error(typeof result.detail === 'string' ? result.detail : '파일 업로드 실패'));
		};
		xhr.send(file);
	});
}
