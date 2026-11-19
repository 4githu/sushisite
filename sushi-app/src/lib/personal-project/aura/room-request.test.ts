import { describe, expect, it } from 'vitest';
import { buildRoomRequestPreview } from './room-request';
import type { ClinicRound } from '../shared/types';

const date = new Date('2026-10-29T12:00:00+09:00');
function round(id: number, start: string, end: string, modality: ClinicRound['modality'], attendanceStatus: ClinicRound['attendanceStatus'] = 'scheduled'): ClinicRound {
  return { id, schoolId: 1, schoolName: '가상고', startTime: `2026-10-29T${start}+09:00`, endTime: `2026-10-29T${end}+09:00`, modality, attendanceStatus, description: 'Zoom 온라인', targets: [{ id, studentName: `합성${id}`, report: null }] } as ClinicRound;
}
describe('copy-only classroom preview', () => {
  it('does not generate a request with no in-person round', () => {
    const result = buildRoomRequestPreview(date, [round(1, '10:00:00', '11:00:00', 'remote')]);
    expect(result.text).toBeNull();
    expect(result.inPersonCount).toBe(0);
  });
  it('includes nearby remote at 3599 seconds but excludes 3600 seconds in the same request', () => {
    const result = buildRoomRequestPreview(date, [round(1, '10:00:00', '11:00:00', 'in_person'), round(2, '11:59:59', '12:30:00', 'remote'), round(3, '12:00:00', '12:30:00', 'remote')]);
    expect(result.nearbyRemoteCount).toBe(1);
    expect(result.excludedRemoteCount).toBe(1);
    expect(result.text).toContain('합성2 (비대면)');
    expect(result.text).not.toContain('합성3');
    expect(result.text).not.toContain('불필요');
  });
  it('blocks ambiguous mode and invalid time instead of producing copyable text', () => {
    expect(buildRoomRequestPreview(date, [round(1, '10:00:00', '11:00:00', 'in_person'), round(2, '12:00:00', '13:00:00', 'unverified')]).text).toBeNull();
    expect(buildRoomRequestPreview(date, [round(1, '11:00:00', '10:00:00', 'in_person')]).text).toBeNull();
    expect(buildRoomRequestPreview(date, [{ ...round(1, '10:00:00', '11:00:00', 'in_person'), endTime: '' }]).reason).toBe('invalid_round');
    expect(buildRoomRequestPreview(date, [round(1, '10:00:00', '11:00:00', 'in_person'), { ...round(2, '10:00:00', '11:00:00', 'in_person'), startTime: '' }]).reason).toBe('ready');
  });
  it('ignores cancelled rounds and counts overlapping remote once', () => {
    const result = buildRoomRequestPreview(date, [round(1, '10:00:00', '11:00:00', 'in_person'), round(2, '12:00:00', '13:00:00', 'in_person'), round(3, '10:30:00', '12:30:00', 'remote'), round(4, '09:00:00', '10:00:00', 'unverified', 'cancelled')]);
    expect(result.nearbyRemoteCount).toBe(1);
    expect(result.unverifiedCount).toBe(0);
  });
});
