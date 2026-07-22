/**
 * 입력창 + 액션 칩.
 *
 * 여기 유일한 계약: **칩은 전송 즉시 풀린다.** 눌린 채로 남으면 다음 평범한
 * 메시지에도 지난 의도가 실려 동의 게이트가 다시 열린다 — 백엔드
 * `test_액션_칩을_생략하면_지난_칩이_남지_않는다` 의 프론트 짝이다(ADR 0002).
 */
import { useState } from 'react';

import { IntentChips } from './IntentChips';
import type { Intent } from '@/core/types';

interface Props {
  onSend: (text: string, intent: Intent | null) => void;
  /** 턴이 도는 중이면 잠근다 — 매 POST 가 한 턴이다(ADR 0001). */
  disabled?: boolean;
}

export function Composer({ onSend, disabled = false }: Props) {
  const [text, setText] = useState('');
  const [intent, setIntent] = useState<Intent | null>(null);

  const trimmed = text.trim();
  const canSend = trimmed.length > 0 && !disabled;

  function submit() {
    if (!canSend) return;

    onSend(trimmed, intent);
    setText('');
    setIntent(null); // ← 계약. 칩은 이번 턴에만 유효하다.
  }

  return (
    <form
      className="flex flex-col gap-3 rounded-ss border border-line bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <IntentChips value={intent} onChange={setIntent} disabled={disabled} />

      <div className="flex items-end gap-2">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          rows={2}
          aria-label="메시지"
          placeholder="이번 기간에 한 일을 편하게 적어보세요"
          className={[
            'min-h-[2.75rem] flex-1 resize-y rounded-ss border border-line bg-surface-2 px-3 py-2',
            'text-sm text-ink placeholder:text-ink-faint',
            'focus:border-accent focus:outline-none disabled:opacity-50',
          ].join(' ')}
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={!canSend}
          className={[
            'rounded-ss bg-accent px-4 py-2 text-sm font-medium text-white transition-colors',
            'hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40',
          ].join(' ')}
        >
          보내기
        </button>
      </div>
    </form>
  );
}
