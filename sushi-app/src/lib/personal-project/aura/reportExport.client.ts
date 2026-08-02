import html2canvas from 'html2canvas/dist/html2canvas.esm.js';
import { jsPDF } from 'jspdf';

export async function captureReport(element: HTMLElement) {
	return html2canvas(element, {
		scale: 2,
		backgroundColor: '#ffffff',
		useCORS: true
	});
}

export { jsPDF };
