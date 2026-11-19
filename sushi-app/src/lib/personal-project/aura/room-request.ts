import type { ClinicRound } from '../shared/types';

export type RoomRequestPreview = {
  text: string | null;
  inPersonCount: number;
  nearbyRemoteCount: number;
  excludedRemoteCount: number;
  unverifiedCount: number;
  reason: 'ready' | 'no_in_person' | 'unverified' | 'invalid_round';
};

const day = (value: Date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(value);
const clock = (value: number) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(value);

export function buildRoomRequestPreview(date: Date, rounds: ClinicRound[]): RoomRequestPreview {
  const active = rounds.filter(round => round.attendanceStatus !== 'cancelled');
  const selected = active.filter(round => Number.isFinite(Date.parse(round.startTime)) && day(new Date(round.startTime)) === day(date));
  const unverifiedCount = selected.filter(round => !['in_person', 'remote'].includes(round.modality)).length;
  const onsite = selected.filter(round => round.modality === 'in_person');
  const remote = selected.filter(round => round.modality === 'remote');
  const base = { inPersonCount: onsite.length, nearbyRemoteCount: 0, excludedRemoteCount: remote.length, unverifiedCount };
  if (unverifiedCount) return { ...base, text: null, reason: 'unverified' };
  if (selected.some(round => !Number.isFinite(Date.parse(round.endTime)) || Date.parse(round.startTime) >= Date.parse(round.endTime) || !round.id || !round.schoolId || !round.targets.length || round.targets.some(target => !target.id || !target.studentName)) || new Set(selected.map(round => round.id)).size !== selected.length) {
    return { ...base, text: null, reason: 'invalid_round' };
  }
  if (!onsite.length) return { ...base, text: null, reason: 'no_in_person' };
  const nearby = remote.filter(r => onsite.some(p => Math.max(0, Date.parse(p.startTime) - Date.parse(r.endTime), Date.parse(r.startTime) - Date.parse(p.endTime)) < 3_600_000));
  const included = [...onsite, ...nearby].sort((a, b) => Date.parse(a.startTime) - Date.parse(b.startTime) || a.id - b.id);
  const weekday = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', weekday: 'short' }).format(date).replace('요일', '');
  const parts = day(date).split('-');
  const lines = included.map(round => `${clock(Date.parse(round.startTime))}-${clock(Date.parse(round.endTime))} ${round.schoolName} ${round.targets.map(t => t.studentName).join(', ')}${round.modality === 'remote' ? ' (비대면)' : ''}`);
  return { ...base, nearbyRemoteCount: nearby.length, excludedRemoteCount: remote.length - nearby.length, text: `${Number(parts[1])}/${Number(parts[2])}(${weekday})\n${lines.join('\n')}\n\n위 일정의 강의실 배정 부탁드립니다.`, reason: 'ready' };
}
