/**
 * 대화 전문.
 *
 * 질문이 특수 상태가 아니라 그냥 메시지라, **읽으면 그게 곧 화면이다**(ADR 0001).
 * 복원 로직이 따로 없는 이유이기도 하다.
 *
 * 빈 상태·진행 중·오류를 전부 실제로 렌더한다 — 스트리밍 UI 에서 이 셋이
 * 비어 있으면 사용자는 멈춘 화면과 도는 화면을 구분하지 못한다(STYLESEED.md).
 */
import { useEffect, useRef } from 'react';

import type { Message } from '@/core/types';

interface Props {
  messages: Message[];
  streaming: boolean;
  error: string | null;
}

export function Conversation({ messages, streaming, error }: Props) {
  const empty = messages.length === 0 && !streaming && error === null;
  const endRef = useRef<HTMLDivElement>(null);

  // 새 메시지가 붙으면 따라 내려간다. 안 그러면 턴마다 사용자가 스크롤해야 한다.
  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // jsdom 에는 scrollIntoView 가 없다 — 테스트에서 렌더할 때 터지지 않게 둔다.
    endRef.current?.scrollIntoView?.({ behavior: reduced ? 'auto' : 'smooth', block: 'end' });
  }, [messages.length, streaming]);

  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      {empty && <EmptyState />}
      {messages.map((message, index) => (
        <Bubble key={index} message={message} />
      ))}
      {streaming && <Thinking />}
      {error !== null && <ErrorNotice detail={error} />}
      {/* 아래에 sticky 로 붙은 버튼·입력창이 스크롤된 내용을 덮는다.
          scroll-margin 을 줘서 자동 스크롤이 그만큼 여유를 남기게 한다 —
          안 그러면 방금 온 메시지의 마지막 줄이 가려진다. */}
      <div ref={endRef} className="scroll-mb-44" />
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  const mine = message.role === 'user';

  return (
    <div className={mine ? 'flex justify-end' : 'flex justify-start'}>
      <div
        className={[
          // 초안에 줄바꿈이 들어 있다 — 접히면 형식이 무너진다.
          'max-w-[85%] whitespace-pre-wrap rounded-ss px-4 py-3 text-sm leading-relaxed',
          mine ? 'bg-accent-soft text-ink' : 'border border-line bg-surface text-ink',
        ].join(' ')}
      >
        {message.content}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-ss border border-dashed border-line bg-surface px-6 py-10 text-center">
      <p className="text-sm text-ink-soft">
        평가 기간에 한 일을 말해주세요. 인터뷰해서 성과 리뷰 초안을 같이 만듭니다.
      </p>
      <p className="mt-2 text-xs text-ink-faint">
        직무와 평가 기간부터 물어봅니다. 초안은 동의를 받은 뒤에 씁니다.
      </p>
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 rounded-ss border border-line bg-surface px-4 py-3">
        <span className="size-1.5 animate-pulse rounded-full bg-accent" aria-hidden />
        <span className="text-sm text-ink-soft">생각하는 중</span>
      </div>
    </div>
  );
}

function ErrorNotice({ detail }: { detail: string }) {
  return (
    <div
      role="alert"
      className="rounded-ss border border-danger bg-danger-soft px-4 py-3 text-sm text-ink"
    >
      <p className="font-medium">요청을 끝내지 못했습니다</p>
      <p className="mt-1 text-ink-soft">{detail}</p>
    </div>
  );
}
