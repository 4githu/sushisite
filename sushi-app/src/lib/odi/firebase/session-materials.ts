import { getDownloadURL, ref as storageRef, uploadBytes } from 'firebase/storage';
import { onValue, ref as databaseRef, set, update } from 'firebase/database';
import { firebaseDatabase, firebaseStorage } from '$lib/firebase/client';
import type { PresentationTemplate, OdiFileRef } from '$lib/odi/stores/template';
import { API_BASE as API } from '$lib/config/api';


export type PresentationFirebaseData = {
	created_at: string;
	page_1: {
		duration_minutes: number;
		environment_type: string;
		presentation_purpose: string;
		presentation_title: string;
		qa_count: number;
		used_language: string;
	};
	page_2: {
		paper_pdf_path: string | null;
		presentation_script_content: string;
		slide_image: { image_len: number; image_urls: string[] };
		slide_pdf_path: string;
	};
	page_3: {
		audience_expertise: string;
		audience_interest: string;
		audience_scale: number;
		audience_type: string;
	};
	status: string;
};

type SlideManifest = {
	images?: Array<{ index: number; storage_path: string }>;
};

const presentationPath = (pinCode: string) => `presentation_data/${pinCode}`;

async function readBackendFile(path: string): Promise<Blob> {
	if (!path.startsWith('storage/odi/users/')) {
		throw new Error(
			'이전 데모 자료의 원본 파일을 찾을 수 없습니다. 자료 업로드 화면에서 슬라이드와 논문을 다시 업로드한 뒤 세션을 시작해주세요.'
		);
	}

	const response = await fetch(`${API}/odi/files/read?path=${encodeURIComponent(path)}`, {
		credentials: 'include'
	});
	if (!response.ok) {
		const body = await response.json().catch(() => null);
		throw new Error(body?.detail ?? `세션 파일을 읽지 못했습니다: ${path}`);
	}
	return response.blob();
}

async function uploadBackendFile(path: string, firebasePath: string, contentType?: string) {
	const blob = await readBackendFile(path);
	return uploadBlob(blob, firebasePath, contentType);
}

async function uploadBlob(blob: Blob, firebasePath: string, contentType?: string) {
	const target = storageRef(firebaseStorage(), firebasePath);
	await uploadBytes(target, blob, { contentType: contentType ?? blob.type });
	return getDownloadURL(target);
}

async function convertToJpeg(blob: Blob): Promise<Blob> {
	const bitmap = await createImageBitmap(blob);
	const canvas = document.createElement('canvas');
	canvas.width = bitmap.width;
	canvas.height = bitmap.height;
	canvas.getContext('2d')?.drawImage(bitmap, 0, 0);
	bitmap.close();

	return new Promise((resolve, reject) => {
		canvas.toBlob(
			(result) => result ? resolve(result) : reject(new Error('슬라이드 이미지를 JPEG로 변환하지 못했습니다.')),
			'image/jpeg',
			0.92
		);
	});
}

async function uploadSlideImages(pinCode: string, slide: OdiFileRef): Promise<string[]> {
	if (!slide.image_manifest_path) return [];

	const manifestBlob = await readBackendFile(slide.image_manifest_path);
	const manifest = JSON.parse(await manifestBlob.text()) as SlideManifest;
	const images = [...(manifest.images ?? [])].sort((a, b) => a.index - b.index);

	return Promise.all(images.map(async (image, index) => {
		const source = await readBackendFile(image.storage_path);
		const jpeg = await convertToJpeg(source);
		return uploadBlob(jpeg, `slides/${pinCode}/page_${index + 1}.jpg`, 'image/jpeg');
	}));
}

function languageCode(language: string) {
	if (language === '한국어' || language.toLowerCase().startsWith('ko')) return 'ko';
	if (language === '영어' || language.toLowerCase().startsWith('en')) return 'en';
	return language;
}

export async function publishPresentationData(pinCode: string, template: PresentationTemplate) {
	const slide = template.files.slide;
	if (!slide?.storage_path) throw new Error('Firebase로 전송할 발표 PDF가 없습니다.');

	const [slidePdfPath, imageUrls, paperPdfPath] = await Promise.all([
		uploadBackendFile(slide.storage_path, `slides/${pinCode}/presentation.pdf`, 'application/pdf'),
		uploadSlideImages(pinCode, slide),
		template.files.paper?.storage_path
			? uploadBackendFile(template.files.paper.storage_path, `papers/${pinCode}/research_paper.pdf`, 'application/pdf')
			: Promise.resolve(null)
	]);

	const payload: PresentationFirebaseData = {
		created_at: new Date().toISOString(),
		page_1: {
			duration_minutes: template.environment.duration_minutes,
			environment_type: template.environment.place,
			presentation_purpose: template.environment.purpose,
			presentation_title: template.environment.title,
			qa_count: template.environment.question_count,
			used_language: languageCode(template.environment.language)
		},
		page_2: {
			paper_pdf_path: paperPdfPath,
			presentation_script_content: template.files.script_content ?? '',
			slide_image: { image_len: imageUrls.length, image_urls: imageUrls },
			slide_pdf_path: slidePdfPath
		},
		page_3: {
			audience_expertise: template.audience.expertise_level,
			audience_interest: template.audience.interest_level,
			audience_scale: template.audience.audience_count,
			audience_type: template.audience.audience_type
		},
		status: 'ready'
	};

	await set(databaseRef(firebaseDatabase(), presentationPath(pinCode)), payload);
	return payload;
}

export async function updatePresentationStatus(pinCode: string, status: string) {
	await update(databaseRef(firebaseDatabase(), presentationPath(pinCode)), { status });
}

export function subscribeToPresentation(pinCode: string, callback: (data: PresentationFirebaseData | null) => void) {
	return onValue(databaseRef(firebaseDatabase(), presentationPath(pinCode)), (snapshot) => {
		callback(snapshot.exists() ? (snapshot.val() as PresentationFirebaseData) : null);
	});
}
