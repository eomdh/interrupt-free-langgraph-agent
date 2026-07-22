/**
 * 5축 채점표.
 *
 * 표시 규칙은 `web/STYLESEED.md` 에 잠겨 있다 — **아이콘 + 라벨 + 상태색**의
 * 삼중 인코딩이고 이모지를 쓰지 않는다. 색 하나로만 구분하면 색각 이상에서
 * 상태가 사라지는데, 채점표는 이 앱의 핵심 정보라 그러면 안 된다(ADR 0007).
 *
 * warn 과 block 을 가르는 판단은 `core/scoring` 에 있다 — 품질 축은 상한에서
 * 미달인 채로 나갈 수 있지만 과장허위는 초안 자체를 막는다(ADR 0005).
 */
import { Check, LoaderCircle, Minus, X } from 'lucide-react';

import { AXIS_STATUS_LABEL, type AxisStatus, axisStatus } from '@/core/scoring';
import { AXES, type Tags } from '@/core/types';

const ICON = {
  pass: Check,
  warn: Minus,
  block: X,
  scoring: LoaderCircle,
} as const satisfies Record<AxisStatus, unknown>;

const TONE: Record<AxisStatus, string> = {
  pass: 'text-good',
  warn: 'text-warn',
  block: 'text-danger',
  scoring: 'text-ink-faint',
};

interface Props {
  tags: Tags | null;
}

export function Scorecard({ tags }: Props) {
  return (
    <ul className="flex flex-col gap-1.5">
      {AXES.map((axis) => {
        const status = axisStatus(axis, tags);
        const Icon = ICON[status];

        return (
          <li key={axis} className="flex items-center gap-2 text-sm">
            <Icon
              className={`size-4 shrink-0 ${TONE[status]} ${status === 'scoring' ? 'animate-spin' : ''}`}
              aria-hidden
            />
            <span className="text-ink-soft">{axis}</span>
            <span className={`ml-auto text-xs ${TONE[status]}`}>{AXIS_STATUS_LABEL[status]}</span>
          </li>
        );
      })}
    </ul>
  );
}
