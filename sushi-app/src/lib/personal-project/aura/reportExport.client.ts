import html2canvas from 'html2canvas/dist/html2canvas.esm.js';
import { jsPDF } from 'jspdf';

export async function captureReport(element: HTMLElement) {
	return html2canvas(element, {
		// A4 출력에 충분한 해상도만 유지해 모바일에서도 PDF 용량을 줄입니다.
		scale: 1.25,
		backgroundColor: '#ffffff',
		useCORS: true
	});
}

export { jsPDF };
