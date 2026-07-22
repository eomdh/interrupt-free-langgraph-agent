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
      <header className="border-b border-line bg-surface">
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
          <Composer onSend={send} disabled={state.streaming} />
        </div>

        <ArtifactPanel state={state} />
      </main>
    </div>
  );
}
