import { useAgent } from '@/api/useAgent';
import { useThreadId } from '@/lib/useThreadId';
import { ArtifactPanel } from '@/ui/ArtifactPanel';
import { Composer } from '@/ui/Composer';
import { Conversation } from '@/ui/Conversation';
import { ProgressStepper } from '@/ui/ProgressStepper';

export default function App() {
  const { threadId, reset } = useThreadId();
  const { state, send } = useAgent(threadId);

  return (
    <div className="min-h-dvh bg-canvas font-sans text-ink">
      {/* 스텝퍼가 헤더에 있다. 대화를 스크롤하는 동안 사라지면 정작 루프가
          도는 걸 못 본다 — 이 앱이 보여주려는 것이 그건데. */}
      <header className="sticky top-0 z-10 border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-3 gap-y-2 px-6 py-4">
          <span className="inline-block size-2.5 rounded-full bg-accent" aria-hidden />
          <h1 className="text-base font-semibold">성과 리뷰 초안 코치</h1>

          <div className="ml-auto flex items-center gap-3">
            <ProgressStepper state={state} />
            <button
              type="button"
              onClick={reset}
              className="rounded-ss border border-line px-3 py-1 text-sm text-ink-soft transition-colors hover:border-ink-faint"
            >
              새 대화
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-6 px-6 py-8 lg:grid-cols-[1fr_18rem] lg:items-start">
        <div className="flex flex-col gap-6">
          <Conversation messages={state.messages} streaming={state.streaming} error={state.error} />

          {/* 대화가 길어져도 입력창은 화면에 남는다. 채팅에서 매 턴 스크롤해
              내려가야 하면 그것만으로 못 쓸 물건이 된다. */}
          <div className="sticky bottom-0 -mx-1 bg-canvas px-1 pb-2 pt-2">
            <Composer onSend={send} disabled={state.streaming} />
          </div>
        </div>

        {/* 채점표도 대화를 스크롤하는 동안 계속 보여야 쓸모가 있다. */}
        <div className="lg:sticky lg:top-20">
          <ArtifactPanel state={state} />
        </div>
      </main>
    </div>
  );
}
