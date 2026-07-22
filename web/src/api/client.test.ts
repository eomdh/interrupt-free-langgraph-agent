/**
 * 백엔드 경계의 계약. 연결을 주입해 서버 없이 때린다.
 *
 * 여기서 잡는 것: 1턴 스트림 계약(재접속 금지·done 에서 끊기), 칩이 매 턴
 * 명시되는가, 비정상 종료가 화면을 매달아 두지 않는가. 마지막 한 건은 **실제
 * 백엔드가 뱉은 프레임**을 라이브러리 정식 파서에 통과시켜 리듀서까지 확인한다.
 */
import { type ConnectSSEOptions, type SSEvent, parseSSE } from 'fetch-sse-client';
import { describe, expect, it } from 'vitest';

import { type Connect, type TurnRequest, fetchThread, streamTurn } from './client';
import { applyEvent, initialState } from '@/core/state';
import type { AgentAction } from '@/core/state';

const BODY: TurnRequest = { text: '초안 써줘', client_intent: 'write_now' };

interface Frame {
  event: string;
  data: string;
}

interface Spy {
  url?: string;
  options?: ConnectSSEOptions;
  /** 소비자가 실제로 끌어간 프레임 수 — done 뒤로 안 읽는지 보려고 센다. */
  pulled: number;
}

function fakeConnect(frames: Frame[], spy?: Spy): Connect {
  const connect = async function* (
    input: string | URL,
    options?: ConnectSSEOptions,
  ): AsyncGenerator<SSEvent> {
    if (spy) {
      spy.url = String(input);
      spy.options = options;
    }
    for (const frame of frames) {
      if (spy) spy.pulled += 1;
      yield { event: frame.event, data: frame.data };
    }
  };
  return connect as Connect;
}

function throwingConnect(error: Error): Connect {
  const connect = async function* (): AsyncGenerator<SSEvent> {
    throw error;
  };
  return connect as Connect;
}

const frame = (event: string, data: unknown): Frame => ({ event, data: JSON.stringify(data) });

const doneFrame = frame('done', { thread_id: 't1', messages: [], tags: null, actions: [] });

async function collect<T>(source: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const item of source) out.push(item);
  return out;
}

describe('1턴 스트림 계약', () => {
  it('재접속을 끄고 연결한다 — 켜져 있으면 턴이 중복 실행된다', async () => {
    const spy: Spy = { pulled: 0 };
    await collect(streamTurn('t1', BODY, { connect: fakeConnect([doneFrame], spy) }));

    expect(spy.options?.reconnect).toBe(false);
    expect(spy.options?.method).toBe('POST');
    expect(spy.url).toBe('/threads/t1/turns/stream');
  });

  it('칩 의도를 매 턴 바디에 명시한다 — 안 눌렀으면 null (ADR 0002)', async () => {
    const spy: Spy = { pulled: 0 };
    await collect(
      streamTurn(
        't1',
        { text: '고마워', client_intent: null },
        { connect: fakeConnect([doneFrame], spy) },
      ),
    );

    expect(JSON.parse(String(spy.options?.body))).toEqual({ text: '고마워', client_intent: null });
  });

  it('스레드 id 를 경로에 안전하게 넣는다', async () => {
    const spy: Spy = { pulled: 0 };
    await collect(streamTurn('a/b?c', BODY, { connect: fakeConnect([doneFrame], spy) }));

    expect(spy.url).toBe('/threads/a%2Fb%3Fc/turns/stream');
  });

  it.each([
    ['done', doneFrame],
    ['error', frame('error', { detail: '터짐' })],
  ])('%s 를 보면 그 뒤로는 읽지 않는다', async (_label, closing) => {
    const spy: Spy = { pulled: 0 };
    const after = frame('node', { node: 'respond', seq: 9 });

    const actions = await collect(
      streamTurn('t1', BODY, { connect: fakeConnect([closing, after], spy) }),
    );

    expect(actions).toHaveLength(1);
    expect(spy.pulled).toBe(1); // 뒤 프레임을 끌어가지 않았다
  });
});

describe('비정상 종료', () => {
  it('done 없이 끝나면 오류를 낸다 — 화면이 스트리밍에 매달리면 안 된다', async () => {
    const actions = await collect(
      streamTurn('t1', BODY, {
        connect: fakeConnect([frame('node', { node: 'onboard', seq: 1 })]),
      }),
    );

    expect(actions.at(-1)).toEqual({
      type: 'error',
      data: { detail: '스트림이 끝까지 오지 않았습니다' },
    });
  });

  it('연결이 실패하면 사유를 알린다', async () => {
    const actions = await collect(
      streamTurn('t1', BODY, { connect: throwingConnect(new Error('SSE request failed with status 500')) }),
    );

    expect(actions).toEqual([{ type: 'error', data: { detail: 'SSE request failed with status 500' } }]);
  });

  it('취소는 오류가 아니다', async () => {
    const controller = new AbortController();
    controller.abort();

    const actions = await collect(
      streamTurn('t1', BODY, {
        signal: controller.signal,
        connect: throwingConnect(new Error('aborted')),
      }),
    );

    expect(actions).toEqual([]);
  });
});

describe('프레임 해석', () => {
  it('모르는 이벤트와 깨진 JSON 은 흘린다', async () => {
    const actions = await collect(
      streamTurn('t1', BODY, {
        connect: fakeConnect([
          { event: 'ping', data: '{}' }, // 계약에 없는 이벤트
          { event: 'node', data: '{{{' }, // 깨진 페이로드
          doneFrame,
        ]),
      }),
    );

    expect(actions.map((a) => a.type)).toEqual(['done']);
  });
});

describe('스레드 읽기', () => {
  const fakeFetch = (status: number, body?: unknown): typeof fetch =>
    (async () =>
      new Response(body === undefined ? null : JSON.stringify(body), { status })) as typeof fetch;

  it('없는 스레드는 null — 아직 안 연 스레드는 오류가 아니다', async () => {
    expect(await fetchThread('없음', { fetchFn: fakeFetch(404) })).toBeNull();
  });

  it('대화를 그대로 돌려준다 (ADR 0001)', async () => {
    const view = {
      thread_id: 't1',
      messages: [{ role: 'user' as const, content: '리뷰 써야 해' }],
      tags: null,
      actions: [],
    };
    expect(await fetchThread('t1', { fetchFn: fakeFetch(200, view) })).toEqual(view);
  });

  it('그 밖의 실패는 삼키지 않는다', async () => {
    await expect(fetchThread('t1', { fetchFn: fakeFetch(500) })).rejects.toThrow('500');
  });
});

describe('실제 백엔드 프레임', () => {
  // 백엔드 스모크에서 그대로 받아 적은 SSE. 상한까지 재작성하다 내보내는 턴이다.
  const RAW = `event: loop
data: {"node": "draft", "seq": 1, "attempt": 1}

event: loop
data: {"node": "tag", "seq": 2, "attempt": 1, "tags": {"구체성": true, "기여도": true, "문제해결": true, "정량성": false, "과장허위": true}}

event: loop
data: {"node": "draft", "seq": 3, "attempt": 2}

event: loop
data: {"node": "tag", "seq": 4, "attempt": 2, "tags": {"구체성": true, "기여도": true, "문제해결": true, "정량성": false, "과장허위": true}}

event: loop
data: {"node": "draft", "seq": 5, "attempt": 3}

event: loop
data: {"node": "tag", "seq": 6, "attempt": 3, "tags": {"구체성": true, "기여도": true, "문제해결": true, "정량성": false, "과장허위": true}}

event: node
data: {"node": "deliver", "seq": 7}

event: done
data: {"thread_id": "demo", "messages": [{"role": "user", "content": "초안 써줘"}, {"role": "assistant", "content": "2026 상반기에 결제 지연을 개선했다.\\n\\n(아직 약한 부분: 정량성)\\n\\n이대로 확정할까요?"}], "tags": {"구체성": true, "기여도": true, "문제해결": true, "정량성": false, "과장허위": true}, "actions": ["proceed", "revise"]}

`;

  /** 라이브러리 정식 파서에 태운다. 청크를 일부러 프레임 중간에서 쪼갠다. */
  function connectRaw(raw: string): Connect {
    const connect = async function* (): AsyncGenerator<SSEvent> {
      const bytes = new TextEncoder().encode(raw);
      const cut = 37; // 한글·프레임 경계를 가로지르는 지점
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(bytes.slice(0, cut));
          controller.enqueue(bytes.slice(cut));
          controller.close();
        },
      });
      yield* parseSSE(stream);
    };
    return connect as Connect;
  }

  it('raw 바이트가 파서·매핑·리듀서를 지나 최종 상태가 된다', async () => {
    const actions = await collect(streamTurn('demo', BODY, { connect: connectRaw(RAW) }));

    const start: AgentAction = { type: 'turnStart', text: '초안 써줘' };
    const final = actions.reduce(applyEvent, applyEvent(initialState('demo'), start));

    expect(actions.map((a) => a.type)).toEqual([
      'loop', 'loop', 'loop', 'loop', 'loop', 'loop', 'node', 'done',
    ]);
    expect(final.attempt).toBe(3); // MAX_REVISE=2 → 첫 초안 + 재작성 2회
    expect(final.furthest).toBe('deliver');
    expect(final.tags?.정량성).toBe(false);
    expect(final.actions).toEqual(['proceed', 'revise']); // 초안이 나왔으니 확정·재작성이 열린다
    expect(final.streaming).toBe(false);
    expect(final.error).toBeNull();
    // 초안은 deliver 가 만든 메시지로만 도달한다(ADR 0005).
    expect(final.messages.at(-1)?.content).toContain('이대로 확정할까요?');
  });
});
