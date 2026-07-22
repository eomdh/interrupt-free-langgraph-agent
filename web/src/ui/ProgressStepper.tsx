/**
 * 진행 스텝퍼.
 *
 * 이 앱이 보여주려는 것 자체다 — `interrupt()` 없이도 **자율 루프가 도는 게
 * 보인다.** draft⇄tag 가 상한까지 왕복하는 동안 이 레일이 뛰고, 몇 번째
 * 재작성인지가 같이 뜬다(ADR 0006 의 loop 이벤트).
 *
 * 레일은 되감기지 않는다. 잡담(`respond`)하러 가도 진행이 사라지면 안 된다 —
 * 판단은 `core/state` 의 `furthest` 가 갖고 있다.
 */
import { PHASES, type AgentState, type Phase } from '@/core/state';

const LABEL: Record<Phase, string> = {
  onboard: '온보딩',
  gather: '성과 수집',
  draft: '초안·채점',
  deliver: '산출',
};

type StepState = 'done' | 'active' | 'pending';

function stepStateOf(phase: Phase, state: AgentState): StepState {
  if (state.streaming && state.activePhase === phase) return 'active';

  const reached = state.furthest === null ? -1 : PHASES.indexOf(state.furthest);
  return PHASES.indexOf(phase) <= reached ? 'done' : 'pending';
}

const DOT: Record<StepState, string> = {
  done: 'bg-accent',
  active: 'bg-accent animate-pulse',
  pending: 'bg-line',
};

const TEXT: Record<StepState, string> = {
  done: 'text-ink',
  active: 'text-accent font-medium',
  pending: 'text-ink-faint',
};

interface Props {
  state: AgentState;
}

export function ProgressStepper({ state }: Props) {
  const looping = state.streaming && state.activePhase === 'draft';

  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-1" aria-label="진행 단계">
      {PHASES.map((phase, index) => {
        const step = stepStateOf(phase, state);

        return (
          // data-state 는 테스트가 색 클래스에 묶이지 않게 하는 의미론적 표식이다.
          <li key={phase} data-state={step} className="flex items-center gap-2">
            {index > 0 && <span className="h-px w-6 bg-line" aria-hidden />}

            <span className="flex items-center gap-1.5">
              <span className={`size-1.5 rounded-full ${DOT[step]}`} aria-hidden />
              <span
                className={`text-sm ${TEXT[step]}`}
                aria-current={step === 'active' ? 'step' : undefined}
              >
                {LABEL[phase]}
              </span>
            </span>

            {/* 루프가 도는 중일 때만, 초안·채점 칸 옆에 시도 횟수를 붙인다. */}
            {phase === 'draft' && looping && state.attempt > 0 && (
              <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs text-accent">
                재작성 {state.attempt}회차
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
