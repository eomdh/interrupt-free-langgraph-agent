/**
 * 입력창.
 *
 * 의도를 고르는 장치가 여기 없다. 말한 내용이 곧 의도이고, 분류가 그걸
 * 읽는다(ADR 0008). 동의가 필요한 순간에는 서버가 알려준 문맥 버튼이
 * 따로 뜬다(ADR 0009) — 입력 경로가 둘로 갈려 서로 모순되는 일이 없다.
 */
import { useState } from 'react';

interface Props {
  onSend: (text: string) => void;
  /** 턴이 도는 중이면 잠근다 — 매 POST 가 한 턴이다(ADR 0001). */
  disabled?: boolean;
}

export function Composer({ onSend, disabled = false }: Props) {
  const [text, setText] = useState('');

  const trimmed = text.trim();
  const canSend = trimmed.length > 0 && !disabled;

  function submit() {
    if (!canSend) return;

    onSend(trimmed);
    setText('');
  }

  return (
    <form
      className="flex items-end gap-2 rounded-ss border border-line bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
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
    </form>
  );
}
