/**
 * 리듀서와 백엔드를 잇는 배선. **판단은 여기 없다** — 전이는 `core/state`,
 * 스트림 계약은 `api/client` 가 갖고 있고 둘 다 테스트로 잠겨 있다.
 * 여기 남은 것은 React 수명주기(마운트 복원·취소·중복 전송 방지)뿐이다.
 */
import { useCallback, useEffect, useReducer, useRef } from 'react';

import { fetchThread, streamTurn } from './client';
import { applyEvent, initialState } from '@/core/state';
import type { Intent } from '@/core/types';

export function useAgent(threadId: string) {
  const [state, dispatch] = useReducer(applyEvent, threadId, initialState);

  // 진행 중인 스트림을 언마운트·스레드 교체 때 끊는다.
  const abortRef = useRef<AbortController | null>(null);
  // 스트리밍 중 재전송 차단. state 를 보면 클로저가 낡으므로 ref 로 둔다.
  const busyRef = useRef(false);

  // 마운트하면 대화를 읽어 온다. 새로고침 복원이 여기서 나온다(ADR 0001).
  useEffect(() => {
    const controller = new AbortController();

    fetchThread(threadId, { signal: controller.signal })
      .then((view) => {
        if (controller.signal.aborted) return;
        // 아직 없는 스레드도 빈 뷰로 하이드레이트한다 — 스레드를 갈아탈 때
        // 지난 대화가 남지 않게 상태를 초기화하는 역할도 겸한다.
        dispatch({
          type: 'hydrate',
          view: view ?? { thread_id: threadId, messages: [], tags: null, actions: [] },
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        dispatch({
          type: 'error',
          data: { detail: error instanceof Error ? error.message : String(error) },
        });
      });

    return () => controller.abort();
  }, [threadId]);

  // 언마운트 시 진행 중인 턴을 끊는다.
  useEffect(() => () => abortRef.current?.abort(), []);

  const send = useCallback(
    async (text: string, intent: Intent | null = null) => {
      if (busyRef.current) return; // 한 번에 한 턴 — 매 POST 가 한 턴이다
      busyRef.current = true;

      const controller = new AbortController();
      abortRef.current = controller;

      dispatch({ type: 'turnStart', text });
      try {
        const turn = streamTurn(threadId, { text, client_intent: intent }, { signal: controller.signal });
        for await (const action of turn) {
          if (controller.signal.aborted) return;
          dispatch(action);
        }
      } finally {
        busyRef.current = false;
      }
    },
    [threadId],
  );

  return { state, send };
}
