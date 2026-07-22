// @vitest-environment jsdom
/**
 * 스텝퍼가 진행을 정직하게 그리는가.
 *
 * 이 앱의 완료 기준이 "자율 루프가 도는 중으로 보인다"라, 여기서 잡는 것은
 * 색이 아니라 **의미**다 — 어느 단계가 도는 중인지, 몇 번째 재작성인지.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { type AgentState, applyEvent, initialState } from '@/core/state';
import type { Tags } from '@/core/types';
import { ProgressStepper } from './ProgressStepper';

afterEach(cleanup);

function stateWith(over: Partial<AgentState>): AgentState {
  return { ...initialState('t1'), ...over };
}

function stepOf(label: string): string | undefined {
  return screen.getByText(label).closest('li')?.dataset.state;
}

describe('단계 표시', () => {
  it('도달한 단계까지 완료로, 그 뒤는 대기로 그린다', () => {
    render(<ProgressStepper state={stateWith({ furthest: 'gather' })} />);

    expect(stepOf('온보딩')).toBe('done');
    expect(stepOf('성과 수집')).toBe('done');
    expect(stepOf('초안·채점')).toBe('pending');
    expect(stepOf('산출')).toBe('pending');
  });

  it('도는 중인 단계만 active 이고 aria-current 가 붙는다', () => {
    render(
      <ProgressStepper
        state={stateWith({ streaming: true, activePhase: 'draft', furthest: 'draft' })}
      />,
    );

    expect(stepOf('초안·채점')).toBe('active');
    expect(screen.getByText('초안·채점').getAttribute('aria-current')).toBe('step');
    expect(screen.getByText('온보딩').getAttribute('aria-current')).toBeNull();
  });

  it('턴이 끝나면 도는 표시가 사라진다', () => {
    // 스트리밍이 아니면 activePhase 가 무엇이든 active 가 없다(리듀서 불변식과 짝).
    render(<ProgressStepper state={stateWith({ streaming: false, furthest: 'deliver' })} />);

    expect(screen.queryByText('초안·채점')?.closest('li')?.dataset.state).toBe('done');
    expect(document.querySelector('[data-state="active"]')).toBeNull();
  });

  it('잡담 중에는 어떤 단계도 도는 중이 아니다', () => {
    // respond 는 단계를 안 올리므로 activePhase 가 null 이다.
    render(
      <ProgressStepper
        state={stateWith({ streaming: true, activePhase: null, furthest: 'gather' })}
      />,
    );

    expect(document.querySelector('[data-state="active"]')).toBeNull();
  });
});

describe('자율 루프', () => {
  it('재작성 횟수를 보여준다 — 루프가 도는 게 보이는 지점', () => {
    render(
      <ProgressStepper
        state={stateWith({ streaming: true, activePhase: 'draft', furthest: 'draft', attempt: 2 })}
      />,
    );

    expect(screen.getByText('재작성 2회차')).toBeTruthy();
  });

  it('실제 이벤트 순서대로 회차가 올라간다 — 마일스톤 완료 기준', () => {
    const scored: Tags = {
      구체성: true,
      기여도: true,
      문제해결: true,
      정량성: false,
      과장허위: true,
    };

    let state = applyEvent(initialState('demo'), { type: 'turnStart', text: '초안 써줘' });
    const { rerender } = render(<ProgressStepper state={state} />);

    const seen: string[] = [];
    const step = (node: 'draft' | 'tag', seq: number, attempt: number, tags?: Tags) => {
      state = applyEvent(state, { type: 'loop', data: { node, seq, attempt, tags } });
      rerender(<ProgressStepper state={state} />);
      const badge = screen.queryByText(/재작성/)?.textContent;
      if (badge) seen.push(badge);
    };

    // 백엔드 스모크와 같은 순서: draft⇄tag 3회(상한까지).
    step('draft', 1, 1);
    step('tag', 2, 1, scored);
    step('draft', 3, 2);
    step('tag', 4, 2, scored);
    step('draft', 5, 3);
    step('tag', 6, 3, scored);

    expect(seen).toEqual([
      '재작성 1회차',
      '재작성 1회차',
      '재작성 2회차',
      '재작성 2회차',
      '재작성 3회차',
      '재작성 3회차',
    ]);

    // 턴이 끝나면 도는 표시가 걷힌다.
    state = applyEvent(state, {
      type: 'done',
      data: { thread_id: 'demo', messages: [], tags: scored, actions: ['proceed', 'revise'] },
    });
    rerender(<ProgressStepper state={state} />);

    expect(screen.queryByText(/재작성/)).toBeNull();
    expect(document.querySelector('[data-state="active"]')).toBeNull();
    expect(screen.getByText('초안·채점').closest('li')?.dataset.state).toBe('done');
  });

  it('루프가 아닐 때는 재작성 표시가 없다', () => {
    render(
      <ProgressStepper state={stateWith({ streaming: false, furthest: 'deliver', attempt: 3 })} />,
    );

    expect(screen.queryByText(/재작성/)).toBeNull();
  });
});
