/**
 * 배지 상태 매핑. 백엔드는 bool 만 주므로, "경고"와 "차단"을 가르는 판단은
 * 여기가 유일한 자리다(ADR 0005·0007).
 */
import { describe, expect, it } from 'vitest';

import { AXIS_STATUS_LABEL, axisStatus } from './scoring';
import { AXES, type Tags } from './types';

const passing = (over: Partial<Tags> = {}): Tags => ({
  구체성: true,
  기여도: true,
  문제해결: true,
  정량성: true,
  과장허위: true,
  ...over,
});

describe('축 상태', () => {
  it('통과한 축은 전부 pass', () => {
    const tags = passing();
    expect(AXES.map((axis) => axisStatus(axis, tags))).toEqual(AXES.map(() => 'pass'));
  });

  it('품질 축 미달은 warn — 상한에서 미달인 채로 나갈 수 있다(ADR 0003)', () => {
    const tags = passing({ 정량성: false });
    expect(axisStatus('정량성', tags)).toBe('warn');
  });

  it('과장허위 미달은 block — 안 걷히면 초안 자체가 안 나간다(ADR 0005)', () => {
    const tags = passing({ 과장허위: false });
    expect(axisStatus('과장허위', tags)).toBe('block');
  });

  it('채점 전이면 scoring', () => {
    expect(axisStatus('구체성', null)).toBe('scoring');
    expect(axisStatus('구체성', undefined)).toBe('scoring');
  });

  it('true 가 아닌 값은 통과로 봐주지 않는다 — "판정 불가 = 미달"', () => {
    // 서버가 스키마를 어겨도 fail-safe 여야 한다. 백엔드 is_passing_tags 와 같은 규칙.
    for (const bogus of [1, 'true', {}, [], 'yes']) {
      const tags = passing({ 정량성: bogus as unknown as boolean });
      expect(axisStatus('정량성', tags)).toBe('warn');
    }
  });
});

describe('라벨', () => {
  it('네 상태 모두 혼자서도 뜻이 통하는 말을 갖는다', () => {
    // 색 단독 금지(ADR 0007) — 라벨이 비면 접근성 보장이 깨진다.
    for (const label of Object.values(AXIS_STATUS_LABEL)) {
      expect(label.trim().length).toBeGreaterThan(0);
    }
    expect(AXIS_STATUS_LABEL.block).toBe('차단');
  });
});
