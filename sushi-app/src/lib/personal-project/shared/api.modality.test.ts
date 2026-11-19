import { afterEach, expect, it, vi } from 'vitest';
import { personalApi } from './api';

afterEach(() => vi.unstubAllGlobals());
it('fetches following preview and carries ordered IDs plus opaque state into the explicit patch', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({scope:'following',roundState:'opaque-state',rounds:[{id:8},{id:9}]}), {status:200})).mockResolvedValueOnce(new Response(JSON.stringify({affectedRoundIds:[8,9]}), {status:200}));
  vi.stubGlobal('fetch', fetcher);
  const preview = await personalApi.roundModalityPreview(8);
  await personalApi.updateRoundModalityFollowing(8, 'remote', preview);
  expect(fetcher.mock.calls[0][0]).toContain('/aura/rounds/8/modality-preview?scope=following');
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({scope:'following',modality:'remote',expected_round_ids:[8,9],expected_round_state:'opaque-state'});
});
