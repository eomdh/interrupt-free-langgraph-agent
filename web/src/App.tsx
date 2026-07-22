import { useAgent } from '@/api/useAgent';
import { useThreadId } from '@/lib/useThreadId';
import { Composer } from '@/ui/Composer';
import { Conversation } from '@/ui/Conversation';

export default function App() {
  const { threadId, reset } = useThreadId();
  const { state, send } = useAgent(threadId);

  return (
    <div className="min-h-dvh bg-canvas font-sans text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-3xl items-center gap-2 px-6 py-4">
          <span className="inline-block size-2.5 rounded-full bg-accent" aria-hidden />
          <h1 className="text-base font-semibold">성과 리뷰 초안 코치</h1>
          <button
            type="button"
            onClick={reset}
            className="ml-auto rounded-ss border border-line px-3 py-1 text-sm text-ink-soft transition-colors hover:border-ink-faint"
          >
            새 대화
          </button>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8">
        <Conversation messages={state.messages} streaming={state.streaming} error={state.error} />
        <Composer onSend={send} disabled={state.streaming} />
      </main>
    </div>
  );
}
