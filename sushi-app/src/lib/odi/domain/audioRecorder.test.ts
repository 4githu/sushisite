import { it, expect } from 'vitest';
import { encodeWav } from './audioRecorder';
it('encodes mono PCM16 WAV with correct duration and clipping', async () => {
	const bytes = await encodeWav(new Float32Array([0, -1, 1, 2]), 16000).arrayBuffer();
	const view = new DataView(bytes);
	expect(bytes.byteLength).toBe(52);
	expect(view.getUint32(24, true)).toBe(16000);
	expect(view.getInt16(46, true)).toBe(-32768);
	expect(view.getInt16(50, true)).toBe(32767);
});
