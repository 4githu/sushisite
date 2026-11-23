export type PairingTransport = {
	pair: () => Promise<{ session_token: string; expires_in: number }>;
};

/** Deterministic in-memory stand-in; never opens a socket or stores session material. */
export function createFakePairingTransport(
	outcome: 'success' | 'failure' = 'success'
): PairingTransport {
	return {
		async pair() {
			if (outcome === 'failure') {
				throw new Error('FAKE_PAIRING_UNAVAILABLE');
			}
			return { session_token: 'not-a-real-session-token', expires_in: 60 };
		}
	};
}
