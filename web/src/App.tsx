// 스캐폴드 셸. toss 스킨이 실제로 배선됐는지 보이는 최소 화면 —
// accent 도트·canvas 배경·ink 텍스트·line 보더·rounded-ss 가 토큰에서 나온다.
// 다음 단계에서 상태 리듀서 · SSE 연결 · 스텝퍼 · 산출물 패널이 여기 올라간다.
export default function App() {
  return (
    <div className="min-h-dvh bg-canvas font-sans text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-6 py-4">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />
          <h1 className="text-base font-semibold">성과 리뷰 초안 코치</h1>
          <span className="ml-auto text-sm text-ink-faint">interrupt-free agent</span>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-16">
        <div className="rounded-ss border border-line bg-surface p-10 text-center">
          <p className="text-ink-soft">
            프론트 셸이 준비됐습니다. 다음: 상태 리듀서 · SSE 연결 · 진행 스텝퍼 · 산출물 패널.
          </p>
        </div>
      </main>
    </div>
  );
}
