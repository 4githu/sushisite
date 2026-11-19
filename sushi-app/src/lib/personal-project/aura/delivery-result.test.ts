import { describe, expect, it } from 'vitest';
import { deliveryView } from './delivery-result';

describe('synthetic clinic delivery results', () => {
 it('distinguishes verified fallback and does not invent a destination', () => {
  expect(deliveryView({sent:true, deliveryStatus:'verified', deliveryFormat:'text', destination:'본계정', fallbackReason:'both_rooms_confirmed_absent'}).message).toContain('학생 방에는 발송되지 않았습니다');
  expect(deliveryView({sent:true, deliveryStatus:'verified'}).message).not.toContain('undefined');
 });
 it('only unlocks a confirmed retryable pre-send failure', () => {
  expect(deliveryView({deliveryStatus:'not_started', retryable:true}).unlock).toBe(true);
  for (const result of [{deliveryStatus:'not_started'}, {deliveryStatus:'partial', retryable:true}, {deliveryStatus:'unknown'}, {}]) expect(deliveryView(result).unlock).toBe(false);
 });
 it('separates partial, unknown and completion pending', () => {
  expect(deliveryView({deliveryStatus:'partial'}).message).toContain('일부');
  expect(deliveryView({deliveryStatus:'unknown'}).message).toContain('확인');
  expect(deliveryView({sent:true, deliveryStatus:'verified', completionStatus:'pending'}).message).toContain('작성완료');
 });
});
