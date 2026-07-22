// @vitest-environment jsdom
/**
 * 훅에 남은 것은 React 수명주기뿐이다 — 마운트 복원, 중복 전송 차단, 취소.
 * 판단은 `core/state`·`api/client` 에 있고 거기서 따로 검증한다.
 *
 * 이 파일이 없던 동안 스레드 교체 시 이전 턴이 안 끊기는 버그가 살아 있었다.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentAction } from '@/core/state';
import type { ThreadView } from '@/core/types';
import { useAgent } from './useAgent';

vi.mock('./client', () => ({
  fetchThread: vi.fn(),
  streamTurn: vi.fn(),
}));

const { fetchThread, streamTurn } = await import('./client');

const view = (over: Partial<ThreadView> = {}): ThreadView => ({
  thread_id: 't1',
  messages: [],
  tags: null,
  actions: [],
  ...over,
});

/** 원할 때까지 멈춰 있는 스트림. 취소·중복 전송을 관찰하려면 진행 중이어야 한다. */
function pendingStream() {
  let release: (() => void) | undefined;
  const started = new Promise<void>((resolve) => {
    release = resolve;
  });

  async function* stream(): AsyncGenerator<AgentAction> {
    await started;
    yield { type: 'done', data: view({ messages: [{ role: 'assistant', content: 'A 의 응답' }] }) };
  }

  return { stream, release: () => release?.() };
}

beforeEach(() => {
  vi.mocked(fetchThread).mockReset().mockResolvedValue(null);
  vi.mocked(streamTurn).mockReset();
});

describe('마운트', () => {
  it('대화를 읽어와 복원한다 (ADR 0001)', async () => {
    vi.mocked(fetchThread).mockResolvedValue(
      view({ messages: [{ role: 'user', content: '리뷰 써야 해' }] }),
    );

    const { result } = renderHook(() => useAgent('t1'));

    await waitFor(() => expect(result.current.state.messages).toHaveLength(1));
    expect(vi.mocked(fetchThread).mock.calls[0][0]).toBe('t1');
  });

  it('없는 스레드는 빈 상태로 시작한다 — 오류가 아니다', async () => {
    const { result } = renderHook(() => useAgent('새-스레드'));

    await waitFor(() => expect(vi.mocked(fetchThread)).toHaveBeenCalled());
    expect(result.current.state.messages).toEqual([]);
    expect(result.current.state.error).toBeNull();
  });
});

describe('전송', () => {
  it('턴이 도는 중에는 두 번째 전송을 무시한다 — 매 POST 가 한 턴이다', async () => {
    const { stream, release } = pendingStream();
    vi.mocked(streamTurn).mockImplementation(stream);

    const { result } = renderHook(() => useAgent('t1'));
    await waitFor(() => expect(vi.mocked(fetchThread)).toHaveBeenCalled());

    act(() => {
      void result.current.send('첫 번째');
      void result.current.send('두 번째');
    });

    expect(vi.mocked(streamTurn)).toHaveBeenCalledTimes(1);
    await act(async () => {
      release();
    });
  });

  it('의도를 그대로 실어 보낸다', async () => {
    vi.mocked(streamTurn).mockImplementation(async function* () {
      yield { type: 'done', data: view() };
    });

    const { result } = renderHook(() => useAgent('t1'));
    await waitFor(() => expect(vi.mocked(fetchThread)).toHaveBeenCalled());

    await act(async () => {
      await result.current.send('초안 써주세요', 'write_now');
    });

    expect(vi.mocked(streamTurn).mock.calls[0][1]).toEqual({
      text: '초안 써주세요',
      client_intent: 'write_now',
    });
  });
});

describe('스레드 교체', () => {
  it('진행 중인 턴을 끊는다 — 이전 스레드의 응답이 새 화면을 덮으면 안 된다', async () => {
    const { stream, release } = pendingStream();
    vi.mocked(streamTurn).mockImplementation(stream);

    const { result, rerender } = renderHook(({ id }) => useAgent(id), {
      initialProps: { id: 'A' },
    });
    await waitFor(() => expect(vi.mocked(fetchThread)).toHaveBeenCalled());

    act(() => {
      void result.current.send('A 에서 보낸 메시지');
    });

    // 스트림이 끝나기 전에 새 대화로 갈아탄다.
    rerender({ id: 'B' });
    await waitFor(() => expect(vi.mocked(fetchThread)).toHaveBeenCalledTimes(2));

    const signal = vi.mocked(streamTurn).mock.calls[0][2]?.signal;
    expect(signal?.aborted).toBe(true);

    // 뒤늦게 도착한 A 의 응답이 B 화면에 정착하지 않는다.
    await act(async () => {
      release();
    });
    expect(result.current.state.messages).toEqual([]);
  });
});
