/**
 * 산출물 패널 — 초안이 어떤 상태인지.
 *
 * **초안 본문을 여기 다시 싣지 않는다.** 초안은 `deliver` 가 메시지로 바꾼 것만
 * 사용자에게 닿고(ADR 0005), 그건 대화에 이미 있다. 서버가 주는 것은 5축 채점뿐이라
 * (`ThreadView` 에 draft 가 없다) 이 패널이 보여줄 산출물은 **그 초안에 대한 판정**이다.
 *
 * 복사해 붙일 깨끗한 초안 본문을 따로 주려면 백엔드가 전달된 초안만 내려주는
 * 필드를 새로 열어야 한다 — 이번 범위 밖이다.
 */

import { type AgentState, visibleTags } from '@/core/state';
import { Scorecard } from './Scorecard';

interface Props {
  state: AgentState;
}

export function ArtifactPanel({ state }: Props) {
  const tags = visibleTags(state);
  const scoring = state.streaming && state.activePhase === 'draft';

  return (
    <aside className="flex flex-col gap-3 rounded-ss border border-line bg-surface p-4">
      <div className="flex items-baseline gap-2">
        <h2 className="text-sm font-semibold text-ink">채점</h2>
        {scoring && (
          <span className="text-xs text-accent">
            {state.attempt > 0 ? `${state.attempt}회차 채점 중` : '채점 중'}
          </span>
        )}
      </div>

      {tags === null && !scoring ? (
        <p className="text-xs leading-relaxed text-ink-faint">
          초안을 쓰면 5축으로 채점합니다. 과장·허위가 걷히지 않으면 초안을 내보내지 않습니다.
        </p>
      ) : (
        <Scorecard tags={tags} />
      )}

      <p className="border-t border-line-soft pt-3 text-xs leading-relaxed text-ink-faint">
        품질 축은 상한에 닿으면 미달인 채로 나갑니다. 과장허위만은 양보하지 않습니다.
      </p>
    </aside>
  );
}
