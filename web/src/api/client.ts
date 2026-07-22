/**
 * 백엔드 경계. 여기만 네트워크를 안다.
 *
 * 연결(`connect`)과 `fetch` 를 주입받는다 — 백엔드가 LLM 을 프로토콜로 받아
 * 목으로 전 구간을 돌린 것과 같은 이유다(`agent/llm.py`). 덕분에 이 계층의
 * 계약을 서버 없이 테스트한다.
 */
import { connectSSE } from 'fetch-sse-client';

import type { AgentAction } from '@/core/state';
import type { ErrorEvent, Intent, LoopEvent, NodeEvent, ThreadView } from '@/core/types';

/** 주입 지점. 기본은 실제 연결. */
export type Connect = typeof connectSSE;

/**
 * 한 턴의 입력.
 *
 * `client_intent` 를 **매 턴 명시한다.** 칩을 안 눌렀으면 `null` 이다 — 생략하면
 * 지난 턴의 칩이 상태에 남아 동의 게이트를 다시 연다(ADR 0002).
 */
export interface TurnRequest {
  text: string;
  client_intent: Intent | null;
}

/**
 * 스레드를 읽어 온다. 없으면 `null` — 아직 안 연 스레드는 오류가 아니다.
 *
 * 복원 코드가 따로 없다는 게 요점이다. 질문이 특수 상태가 아니라 그냥 메시지라
 * 대화를 읽으면 그게 곧 화면이다(ADR 0001).
 */
export async function fetchThread(
  threadId: string,
  options: { fetchFn?: typeof fetch; signal?: AbortSignal } = {},
): Promise<ThreadView | null> {
  const { fetchFn = fetch, signal } = options;
  const response = await fetchFn(`/threads/${encodeURIComponent(threadId)}`, { signal });

  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`스레드를 못 읽었습니다 (${response.status})`);
  return (await response.json()) as ThreadView;
}

/** SSE 프레임 하나를 리듀서가 아는 액션으로. 모르는 이벤트·깨진 JSON 은 흘린다. */
function toAction(event: string, raw: string): AgentAction | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }

  switch (event) {
    case 'node':
      return { type: 'node', data: data as NodeEvent };
    case 'loop':
      return { type: 'loop', data: data as LoopEvent };
    case 'done':
      return { type: 'done', data: data as ThreadView };
    case 'error':
      return { type: 'error', data: data as ErrorEvent };
    default:
      return null;
  }
}

function reason(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * 한 턴을 스트리밍으로 돌리고, 리듀서에 넣을 액션을 순서대로 내놓는다.
 *
 * **`reconnect: false` 가 핵심이다.** `connectSSE` 는 장수 스트림용이라 기본이
 * 재접속인데, 우리 스트림은 매 POST 가 한 턴이고 `done` 에서 정상 종료된다.
 * 기본값을 두면 서버가 스트림을 닫는 순간 클라이언트가 재접속하며 **그 턴을 다시
 * POST** 한다 — 턴이 중복 실행된다(ADR 0001·0006).
 *
 * 그래서 `done`·`error` 를 보면 즉시 끊고, 둘 다 없이 끝나면 그것도 오류로
 * 알린다. 화면이 스트리밍 상태에 매달린 채 남으면 안 된다.
 */
export async function* streamTurn(
  threadId: string,
  body: TurnRequest,
  options: { signal?: AbortSignal; connect?: Connect } = {},
): AsyncGenerator<AgentAction> {
  const { signal, connect = connectSSE } = options;

  try {
    const stream = connect(`/threads/${encodeURIComponent(threadId)}/turns/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal,
      reconnect: false,
    });

    for await (const frame of stream) {
      const action = toAction(frame.event, frame.data);
      if (action === null) continue;

      yield action;
      if (action.type === 'done' || action.type === 'error') return;
    }

    yield { type: 'error', data: { detail: '스트림이 끝까지 오지 않았습니다' } };
  } catch (error) {
    // 사용자가 취소한 것은 정상 종료다 — 오류로 보이면 안 된다.
    if (signal?.aborted) return;
    yield { type: 'error', data: { detail: reason(error) } };
  }
}
