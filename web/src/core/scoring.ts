/**
 * 채점 배지 상태.
 *
 * 표시 규칙은 `web/STYLESEED.md` 에 잠겨 있다 — lucide 아이콘 + 라벨 + 상태색의
 * 삼중 인코딩이고, **색 단독으로 상태를 구분하지 않는다**(ADR 0007).
 */
import { HALLUCINATION_AXIS, type Axis, type Tags } from './types';

export type AxisStatus = 'pass' | 'warn' | 'block' | 'scoring';

/** 배지 라벨. 아이콘·색과 함께 쓰이고, 혼자서도 상태를 말할 수 있어야 한다. */
export const AXIS_STATUS_LABEL: Record<AxisStatus, string> = {
  pass: '통과',
  warn: '미달',
  block: '차단',
  scoring: '채점 중',
};

/**
 * 축 하나의 배지 상태.
 *
 * 백엔드는 bool 만 준다 — 미달을 "경고"로 볼지 "차단"으로 볼지는 **어느 축이냐**로
 * 갈린다. 품질 축은 상한에서 미달인 채로 나갈 수 있지만(ADR 0003), 과장허위는
 * 안 걷히면 초안 자체가 안 나간다(ADR 0005). 그 차이를 화면에서도 구분한다.
 *
 * `=== true` 로만 통과시킨다. 백엔드 `is_passing_tags` 와 같은 fail-safe 다 —
 * 값이 이상하면 통과로 봐주지 않는다("판정 불가 = 미달").
 */
export function axisStatus(axis: Axis, tags: Tags | null | undefined): AxisStatus {
  if (!tags) return 'scoring';
  if (tags[axis] === true) return 'pass';
  return axis === HALLUCINATION_AXIS ? 'block' : 'warn';
}
