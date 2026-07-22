/**
 * 데모용 스레드 하나를 브라우저에 붙들어 둔다.
 *
 * 인증이 없다 — 스레드 ID 만으로 충분하다는 게 범위 결정이었다(plan.md).
 * 새로고침해도 같은 ID 를 쓰기 때문에, 대화가 복원되는 걸 실제로 볼 수 있다(ADR 0001).
 */
import { useCallback, useState } from 'react';

const KEY = 'interrupt-free-agent.threadId';

function freshId(): string {
  return crypto.randomUUID();
}

export function useThreadId(): { threadId: string; reset: () => void } {
  const [threadId, setThreadId] = useState(() => {
    const saved = localStorage.getItem(KEY);
    if (saved) return saved;

    const created = freshId();
    localStorage.setItem(KEY, created);
    return created;
  });

  const reset = useCallback(() => {
    const created = freshId();
    localStorage.setItem(KEY, created);
    setThreadId(created);
  }, []);

  return { threadId, reset };
}
