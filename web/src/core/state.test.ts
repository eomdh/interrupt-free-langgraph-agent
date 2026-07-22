/**
 * 이벤트 시퀀스 → 상태. 네트워크도 DOM 도 없이 전이만 때린다.
 *
 * 여기서 잡는 것: 낙관적 메시지가 중복으로 남지 않는가, 레일이 되감기지 않는가,
 * 진행이 끝나면 활성 표시가 사라지는가, 루프가 채점을 실어 나르는가.
 */
import { describe, expect, it } from 'vitest';

import { applyEvent, initialState, visibleTags, type AgentState } from './state';
import type { Tags, ThreadView } from './types';

const passing = (over: Partial<Tags> = {}): Tags => ({
  구체성: true,
  기여도: true,
  문제해결: true,
  정량성: true,
  과장허위: true,
  ...over,
});

const view = (over: Partial<ThreadView> = {}): ThreadView => ({
  thread_id: 't1',
  messages: [],
  tags: null,
  ...over,
});

/** 액션들을 차례로 접는다 — 실제 스트림이 오는 모양 그대로. */
const run = (state: AgentState, ...actions: Parameters<typeof applyEvent>[1][]) =>
  actions.reduce(applyEvent, state);

describe('턴 시작', () => {
  it('사용자 메시지를 먼저 붙이고 스트리밍을 연다', () => {
    const s = applyEvent(initialState('t1'), { type: 'turnStart', text: '리뷰 써야 해' });

    expect(s.messages).toEqual([{ role: 'user', content: '리뷰 써야 해' }]);
    expect(s.streaming).toBe(true);
    expect(s.error).toBeNull();
  });

  it('지난 턴의 진행 흔적을 지운다', () => {
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'tag', seq: 2, attempt: 3, tags: passing({ 정량성: false }) } },
      { type: 'done', data: view({ tags: passing({ 정량성: false }) }) },
      { type: 'turnStart', text: '고마워' },
    );

    expect(s.attempt).toBe(0);
    expect(s.liveTags).toBeNull();
  });
});

describe('진행 이벤트', () => {
  it('루프가 시도 횟수와 채점을 실어 나른다', () => {
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'draft', seq: 1, attempt: 1 } },
      { type: 'loop', data: { node: 'tag', seq: 2, attempt: 1, tags: passing({ 정량성: false }) } },
    );

    expect(s.attempt).toBe(1);
    expect(s.liveTags?.정량성).toBe(false);
    expect(s.activeNode).toBe('tag');
    expect(s.activePhase).toBe('draft');
  });

  it('draft 이벤트는 채점을 안 실으므로 직전 값을 유지한다', () => {
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'tag', seq: 2, attempt: 1, tags: passing({ 정량성: false }) } },
      { type: 'loop', data: { node: 'draft', seq: 3, attempt: 2 } },
    );

    expect(s.attempt).toBe(2);
    expect(s.liveTags?.정량성).toBe(false); // 재작성 중에도 직전 채점이 보인다
  });

  it('respond(잡담)는 단계를 올리지 않는다', () => {
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '고마워' },
      { type: 'node', data: { node: 'respond', seq: 1 } },
    );

    expect(s.activeNode).toBe('respond');
    expect(s.activePhase).toBeNull();
    expect(s.furthest).toBeNull();
  });

  it('레일은 되감기지 않는다', () => {
    const s = run(
      initialState('t1'),
      { type: 'node', data: { node: 'deliver', seq: 1 } },
      { type: 'node', data: { node: 'onboard', seq: 1 } }, // 뒤 단계로 돌아가도
    );

    expect(s.furthest).toBe('deliver'); // 도달한 최대치는 유지된다
  });
});

describe('턴 종료', () => {
  it('done 이 서버 기준으로 대화를 갈아끼운다 — 낙관적 메시지가 중복으로 안 남는다', () => {
    const served = view({
      messages: [
        { role: 'user', content: '리뷰 써야 해' },
        { role: 'assistant', content: '직무 · 평가 기간를 알려주세요.' },
      ],
    });
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '리뷰 써야 해' },
      { type: 'node', data: { node: 'onboard', seq: 1 } },
      { type: 'done', data: served },
    );

    expect(s.messages).toEqual(served.messages);
    expect(s.messages.filter((m) => m.content === '리뷰 써야 해')).toHaveLength(1);
  });

  it('채점이 정착하고 라이브 값은 비워진다', () => {
    const settled = passing({ 정량성: false });
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'tag', seq: 2, attempt: 1, tags: settled } },
      { type: 'done', data: view({ tags: settled }) },
    );

    expect(s.tags).toEqual(settled);
    expect(s.liveTags).toBeNull();
  });

  it.each([
    ['done', { type: 'done', data: view() }],
    ['error', { type: 'error', data: { detail: '터짐' } }],
  ] as const)('%s 뒤에는 활성 표시가 남지 않는다', (_label, closing) => {
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'draft', seq: 1, attempt: 1 } },
      closing,
    );

    expect(s.streaming).toBe(false);
    expect(s.activeNode).toBeNull();
    expect(s.activePhase).toBeNull();
  });

  it('error 는 사유를 남기되 사용자 메시지를 지우지 않는다', () => {
    const s = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'error', data: { detail: "목에 'onboard' 응답이 없다" } },
    );

    expect(s.error).toContain('onboard');
    expect(s.messages).toEqual([{ role: 'user', content: '초안 써줘' }]);
  });
});

describe('새로고침 복원 (ADR 0001)', () => {
  it('채점이 있으면 초안 단계까지 칠한다', () => {
    const restored = applyEvent(initialState('t1'), {
      type: 'hydrate',
      view: view({ messages: [{ role: 'user', content: '안녕' }], tags: passing() }),
    });

    expect(restored.furthest).toBe('draft');
    expect(restored.tags).toEqual(passing());
    expect(restored.streaming).toBe(false);
  });

  it('메시지만 있으면 온보딩까지, 빈 스레드면 아무것도 안 칠한다', () => {
    const withMessages = applyEvent(initialState('t1'), {
      type: 'hydrate',
      view: view({ messages: [{ role: 'user', content: '안녕' }] }),
    });
    const empty = applyEvent(initialState('t1'), { type: 'hydrate', view: view() });

    expect(withMessages.furthest).toBe('onboard');
    expect(empty.furthest).toBeNull();
  });
});

describe('화면이 쓸 채점', () => {
  it('루프 중에는 흘러온 값을, 끝나면 정착값을 쓴다', () => {
    const live = passing({ 정량성: false });
    const settled = passing();

    const looping = run(
      initialState('t1'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'tag', seq: 2, attempt: 1, tags: live } },
    );
    expect(visibleTags(looping)).toEqual(live);

    const done = applyEvent(looping, { type: 'done', data: view({ tags: settled }) });
    expect(visibleTags(done)).toEqual(settled); // liveTags 가 비워져 정착값으로 수렴
  });

  it('아무것도 없으면 null — 채점 전이라는 뜻', () => {
    expect(visibleTags(initialState('t1'))).toBeNull();
  });
});

describe('전 구간', () => {
  it('상한까지 재작성하다 내보내는 턴이 그대로 재현된다', () => {
    // 백엔드 스모크와 같은 시퀀스: draft⇄tag 3회(정량성 미달) → deliver → done
    const settled = passing({ 정량성: false });
    const s = run(
      initialState('demo'),
      { type: 'turnStart', text: '초안 써줘' },
      { type: 'loop', data: { node: 'draft', seq: 1, attempt: 1 } },
      { type: 'loop', data: { node: 'tag', seq: 2, attempt: 1, tags: settled } },
      { type: 'loop', data: { node: 'draft', seq: 3, attempt: 2 } },
      { type: 'loop', data: { node: 'tag', seq: 4, attempt: 2, tags: settled } },
      { type: 'loop', data: { node: 'draft', seq: 5, attempt: 3 } },
      { type: 'loop', data: { node: 'tag', seq: 6, attempt: 3, tags: settled } },
      { type: 'node', data: { node: 'deliver', seq: 7 } },
      {
        type: 'done',
        data: view({
          thread_id: 'demo',
          messages: [{ role: 'assistant', content: '초안…\n\n이대로 확정할까요?' }],
          tags: settled,
        }),
      },
    );

    expect(s.furthest).toBe('deliver');
    expect(s.attempt).toBe(3); // MAX_REVISE=2 → 첫 초안 + 재작성 2회
    expect(s.tags).toEqual(settled);
    expect(s.streaming).toBe(false);
    expect(s.error).toBeNull();
  });
});
