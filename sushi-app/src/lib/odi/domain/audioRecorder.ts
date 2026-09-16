export function encodeWav(samples: Float32Array, rate: number) {
	const buffer = new ArrayBuffer(44 + samples.length * 2),
		view = new DataView(buffer);
	function text(offset: number, s: string) {
		for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
	}
	text(0, 'RIFF');
	view.setUint32(4, 36 + samples.length * 2, true);
	text(8, 'WAVE');
	text(12, 'fmt ');
	view.setUint32(16, 16, true);
	view.setUint16(20, 1, true);
	view.setUint16(22, 1, true);
	view.setUint32(24, rate, true);
	view.setUint32(28, rate * 2, true);
	view.setUint16(32, 2, true);
	view.setUint16(34, 16, true);
	text(36, 'data');
	view.setUint32(40, samples.length * 2, true);
	for (let i = 0; i < samples.length; i++) {
		const n = Math.max(-1, Math.min(1, samples[i]));
		view.setInt16(44 + i * 2, n < 0 ? n * 32768 : n * 32767, true);
	}
	return new Blob([buffer], { type: 'audio/wav' });
}
export class AudioRecorder {
	private chunks: Float32Array[] = [];
	private node: AudioWorkletNode | null = null;
	private finished = false;
	private samples = 0;
	private constructor(
		private context: AudioContext,
		private stream: MediaStream
	) {}
	static async start(onlevel: (level: number) => void, oninterrupted: () => void) {
		if (!navigator.mediaDevices?.getUserMedia)
			throw new Error('마이크 녹음은 HTTPS 또는 localhost에서 지원됩니다.');
		const stream = await navigator.mediaDevices.getUserMedia({
			audio: { channelCount: 1, echoCancellation: true },
			video: false
		});
		const context = new AudioContext(),
			recorder = new AudioRecorder(context, stream);
		try {
			await context.audioWorklet.addModule('/odi-audio-capture.js');
			const source = context.createMediaStreamSource(stream),
				node = new AudioWorkletNode(context, 'odi-audio-capture');
			recorder.node = node;
			node.port.onmessage = (event) => {
				if (recorder.finished) return;
				const incoming = event.data as Float32Array;
				const chunk = incoming.subarray(
					0,
					Math.max(0, context.sampleRate * 180 - recorder.samples)
				);
				recorder.samples += chunk.length;
				if (chunk.length === 0) return;
				recorder.chunks.push(chunk);
				if (recorder.samples >= context.sampleRate * 180) oninterrupted();
				onlevel(Math.sqrt(chunk.reduce((sum, n) => sum + n * n, 0) / chunk.length));
			};
			const silent = context.createGain();
			silent.gain.value = 0;
			source.connect(node);
			node.connect(silent).connect(context.destination);
			await context.resume();
			stream.getTracks().forEach(
				(t) =>
					(t.onended = () => {
						if (!recorder.finished) oninterrupted();
					})
			);
			return recorder;
		} catch (e) {
			await recorder.dispose();
			throw e;
		}
	}
	async finish() {
		const rate = this.context.sampleRate;
		await this.dispose();
		const length = this.chunks.reduce((n, c) => n + c.length, 0);
		if (length < rate) throw new Error('1초 이상 녹음해 주세요.');
		const pcm = new Float32Array(length);
		let offset = 0;
		for (const chunk of this.chunks) {
			pcm.set(chunk, offset);
			offset += chunk.length;
		}
		this.chunks = [];
		if (Math.sqrt(pcm.reduce((n, v) => n + v * v, 0) / length) < 0.001)
			throw new Error('음성이 들리지 않아요. 마이크를 확인하고 다시 녹음해 주세요.');
		const offline = new OfflineAudioContext(1, Math.ceil((length / rate) * 16000), 16000),
			audio = offline.createBuffer(1, length, rate);
		audio.copyToChannel(pcm, 0);
		const source = offline.createBufferSource();
		source.buffer = audio;
		source.connect(offline.destination);
		source.start();
		const rendered = await offline.startRendering();
		return encodeWav(rendered.getChannelData(0), 16000);
	}
	async dispose() {
		this.finished = true;
		this.stream.getTracks().forEach((t) => t.stop());
		this.node?.disconnect();
		if (this.context.state !== 'closed') await this.context.close();
	}
}
