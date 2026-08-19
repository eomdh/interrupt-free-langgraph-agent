"""평가 러너 — 실제 모델로 채점관을 잰다.

    uv run python -m evals.run --dry-run     # 모델 없이 룰만 (무료)
    uv run python -m evals.run               # 케이스마다 1회
    uv run python -m evals.run --repeat 3    # 판정 흔들림까지

**CI에서 안 돈다.** 네트워크와 토큰이 필요하고, 무료 등급은 하루 호출 수가
막혀 있다. 대신 집계는 `evals/metrics.py`에 순수 함수로 떼어 일반 테스트가
덮는다 — 평가 코드가 틀리면 평가 결과를 못 믿는다.

`make_tag`를 **그대로** 부른다. 프롬프트를 복사해 따로 부르면 그 사본이
드리프트해서, 어느 날부터 평가가 프로덕션이 아닌 것을 재게 된다.
"""

import argparse
import asyncio
import json

from agent.intents import AXES, HALLUCINATION_AXIS
from agent.llm import LLM, OpenAICompatibleLLM
from agent.nodes import _loads, _unsupported_numbers, make_tag
from agent.settings import Settings
from evals.cases import CASES, PROFILE, Case
from evals.metrics import (
    CaseOutcome,
    Verdict,
    normalize,
    rule_flips,
    score_all,
    unstable_axes,
)


class RecordingLLM:
    """실제 LLM을 감싸 원본 응답을 붙잡아 둔다.

    `make_tag`는 결정적 룰까지 적용한 뒤의 판정만 돌려주므로, 모델 단독
    판정이 무엇이었는지가 남지 않는다. 그러면 **룰이 무엇을 뒤집었는지**
    귀속할 수 없다. 프롬프트를 복사해 한 번 더 부르는 대신(사본은 드리프트하고
    호출 수도 두 배가 된다) 경계에서 원본을 기록한다.
    """

    def __init__(self, inner: LLM) -> None:
        self._inner = inner
        self.last_raw = ""

    async def complete(self, prompt: str, *, task: str, temperature: float = 0.0) -> str:
        raw = await self._inner.complete(prompt, task=task, temperature=temperature)
        self.last_raw = raw
        return raw


def _state(case: Case) -> dict:
    return {"draft": case.draft, "achievements": case.achievements, "profile": PROFILE}


def _material(case: Case) -> str:
    """`make_tag`가 룰에 넘기는 것과 같은 재료 문자열."""
    return json.dumps([case.achievements, PROFILE], ensure_ascii=False)


async def run_case(llm: LLM, case: Case) -> CaseOutcome:
    recorder = RecordingLLM(llm)
    tags = (await make_tag(recorder)(_state(case)))["tags"]
    return CaseOutcome(
        case_id=case.id,
        expected=normalize(case.expected),
        actual=normalize(tags),
        model_said=normalize(_loads(recorder.last_raw, {})),
    )


# --- 보고 ---

_MARK = {True: "통과", False: "미달"}


def _print_cases(outcomes: list[CaseOutcome], cases: dict[str, Case]) -> None:
    print("\n케이스별 (틀린 축만)")
    print("-" * 72)
    for outcome in outcomes:
        wrong = [axis for axis in AXES if outcome.expected[axis] != outcome.actual[axis]]
        hard = " ⟨어려움⟩" if cases[outcome.case_id].hard else ""
        if not wrong:
            print(f"  ✓ {outcome.case_id}{hard}")
            continue
        detail = ", ".join(
            f"{axis}: 사람={_MARK[outcome.expected[axis]]} 모델={_MARK[outcome.actual[axis]]}"
            for axis in wrong
        )
        print(f"  ✗ {outcome.case_id}{hard} — {detail}")


def _print_axes(outcomes: list[CaseOutcome]) -> None:
    print("\n축별 성적")
    print("-" * 72)
    print(f"  {'축':<10} {'일치':>6} {'누출':>6} {'헛경보':>7}   일치율")
    for axis, score in score_all(outcomes).items():
        gate = "  ← 하드 게이트" if axis == HALLUCINATION_AXIS else ""
        print(
            f"  {axis:<10} {score.agree:>6} {score.miss:>6} {score.false_alarm:>7}"
            f"   {score.accuracy:.0%}{gate}"
        )
    print("\n  누출 = 사람은 미달인데 모델이 통과. 과장허위에서 이건 근거 없는")
    print("  초안을 사용자에게 내보낸다는 뜻이라, 헛경보와 값이 다르다(ADR 0005).")


def _print_rule(outcomes: list[CaseOutcome]) -> None:
    flipped = rule_flips(outcomes, HALLUCINATION_AXIS)
    print("\n결정적 룰이 모델 판정을 뒤집은 케이스")
    print("-" * 72)
    if not flipped:
        print("  없음 — 이번 셋에서 룰은 값을 내지 않았다.")
        return
    for case_id in flipped:
        print(f"  {case_id}")
    print("\n  룰은 취소만 한다(통과를 부여하지 않는다). 여기 이름이 있다는 건")
    print("  하이브리드가 실제로 값을 냈다는 뜻이고, 동시에 헛경보의 출처이기도 하다.")


def _print_stability(runs: dict[str, list[Verdict]]) -> None:
    print("\n판정 흔들림 (temperature 0, 같은 입력 반복)")
    print("-" * 72)
    shaky = {case_id: unstable_axes(verdicts) for case_id, verdicts in runs.items()}
    shaky = {case_id: axes for case_id, axes in shaky.items() if axes}
    if not shaky:
        print("  전 케이스 전 축이 매번 같았다.")
        print("  → ADR 0003이 MAX_REVISE 의 근거로 든 '판정 비결정성'은")
        print("     적어도 이 모델·이 셋에서는 관측되지 않았다. ADR에 적어둘 것.")
        return
    for case_id, axes in shaky.items():
        print(f"  {case_id}: {' · '.join(axes)}")
    print("\n  → 같은 입력에 판정이 갈린다. ADR 0003이 상한을 종료 보장으로")
    print("     삼은 근거가 관측으로 확인됐다.")


def report(outcomes: list[CaseOutcome], runs: dict[str, list[Verdict]], model: str) -> None:
    cases = {case.id: case for case in CASES}
    solid = [o for o in outcomes if not cases[o.case_id].hard]

    print(f"\n{'=' * 72}")
    print(f"채점관 평가 — {model}")
    print(f"케이스 {len(outcomes)}건 (어려움 {len(outcomes) - len(solid)}건 포함)")
    print("=" * 72)

    _print_cases(outcomes, cases)
    _print_axes(outcomes)
    if solid and len(solid) != len(outcomes):
        print("\n  어려움 케이스를 뺀 축별 일치율")
        for axis, score in score_all(solid).items():
            print(f"  {axis:<10} {score.accuracy:>6.0%}")
    _print_rule(outcomes)
    if runs:
        _print_stability(runs)
    print()


# --- 원본 판정 보관 ---
#
# 무료 등급은 하루 호출 수가 막혀 있는데, 라벨을 한 글자 고칠 때마다 다시
# 돌리면 검토가 유료가 된다. 모델이 뭐라고 했는지는 라벨과 무관하므로 따로
# 저장해 두고, 라벨을 고친 뒤에는 호출 없이 다시 집계한다.


def save_runs(path: str, model: str, repeat: int, records: list[dict]) -> None:
    payload = {"model": model, "repeat": repeat, "runs": records}
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    print(f"\n원본 판정 {len(records)}건을 {path} 에 저장했다.")


def load_runs(path: str) -> tuple[list[CaseOutcome], dict[str, list[Verdict]], str]:
    """저장된 판정에 **현재** 라벨을 얹어 다시 집계한다. 모델 호출 0회.

    케이스가 사라졌거나 id 가 바뀌었으면 건너뛰고 알린다. 조용히 빼면 표본이
    줄어든 채로 일치율이 멀쩡해 보인다.
    """
    with open(path, encoding="utf-8") as fp:
        payload = json.load(fp)

    cases = {case.id: case for case in CASES}
    outcomes: list[CaseOutcome] = []
    runs: dict[str, list[Verdict]] = {}
    dropped: set[str] = set()

    for record in payload["runs"]:
        case = cases.get(record["case_id"])
        if case is None:
            dropped.add(record["case_id"])
            continue
        actual = normalize(record["actual"])
        if record["turn"] == 0:
            outcomes.append(
                CaseOutcome(
                    case_id=case.id,
                    expected=normalize(case.expected),
                    actual=actual,
                    model_said=normalize(record["model_said"]),
                )
            )
        runs.setdefault(case.id, []).append(actual)

    if dropped:
        names = ", ".join(sorted(dropped))
        print(f"\n저장본에만 있고 지금 셋에 없는 케이스 {len(dropped)}건은 뺐다: {names}")
    missing = sorted(set(cases) - set(runs))
    if missing:
        print(f"저장본에 없는 케이스 {len(missing)}건은 빠졌다: {', '.join(missing)}")
    return outcomes, runs, payload["model"]


# --- 룰만 미리 보기 (모델 없이) ---


def dry_run(cases: list[Case]) -> None:
    """모델을 안 부르고 결정적 룰이 어디서 터지는지만 본다. 호출 0회.

    라벨을 고치는 중에 쓰라고 둔다 — 케이스를 손볼 때마다 유료 호출을
    태울 이유가 없다.
    """
    print(f"\n케이스 {len(cases)}건 · 모델 호출 없음\n")
    print(f"  {'케이스':<24} {'사람 라벨':<10} 룰이 잡은 수치")
    print("-" * 72)
    for case in cases:
        unsupported = _unsupported_numbers(case.draft, _material(case))
        label = _MARK[case.expected[HALLUCINATION_AXIS]]
        found = " · ".join(sorted(unsupported)) if unsupported else "—"
        # 룰은 미달을 강제한다. 사람이 통과라 한 케이스에서 터지면 헛경보다.
        flag = " ← 헛경보" if unsupported and case.expected[HALLUCINATION_AXIS] else ""
        print(f"  {case.id:<24} {label:<10} {found}{flag}")
    print("\n  '룰이 잡은 수치'가 비어 있는데 사람 라벨이 미달이면, 그 케이스는")
    print("  모델만이 방어선이다 — 하이브리드가 아직 못 덮는 자리(ADR 0004).\n")


def _select(names: list[str] | None, limit: int | None) -> list[Case]:
    cases = [case for case in CASES if not names or case.id in names]
    return cases[:limit] if limit else cases


async def main() -> None:
    parser = argparse.ArgumentParser(description="채점관(tag 노드) 평가")
    parser.add_argument("--repeat", type=int, default=1, help="케이스당 반복 횟수 (흔들림 측정)")
    parser.add_argument("--limit", type=int, help="앞에서 N건만")
    parser.add_argument("--case", action="append", help="케이스 id (여러 번 지정 가능)")
    parser.add_argument("--dry-run", action="store_true", help="모델 없이 룰만 본다")
    parser.add_argument("--save", metavar="PATH", help="원본 판정을 JSON 으로 저장")
    parser.add_argument(
        "--rescore", metavar="PATH", help="저장본에 현재 라벨을 얹어 재집계 (호출 0회)"
    )
    args = parser.parse_args()

    if args.rescore:
        outcomes, runs, model = load_runs(args.rescore)
        report(outcomes, runs if any(len(v) > 1 for v in runs.values()) else {}, model)
        return

    cases = _select(args.case, args.limit)
    if not cases:
        raise SystemExit("고른 케이스가 없다.")

    if args.dry_run:
        dry_run(cases)
        return

    settings = Settings()
    if settings.llm_mode != "openai":
        raise SystemExit(
            "LLM_MODE=openai 가 필요하다. 목은 `task` 이름으로 고정 응답을 주므로\n"
            "채점관을 재는 것이 아니라 목을 재게 된다."
        )

    # 무료 등급은 하루 호출 수가 막혀 있다. 얼마나 쓸지 먼저 알린다.
    planned = len(cases) * args.repeat
    print(f"\n모델 호출 {planned}회 예정 ({len(cases)}건 × {args.repeat}회) — {settings.llm_model}")

    llm = OpenAICompatibleLLM(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
    )
    try:
        outcomes: list[CaseOutcome] = []
        runs: dict[str, list[Verdict]] = {}
        records: list[dict] = []
        for case in cases:
            for turn in range(args.repeat):
                outcome = await run_case(llm, case)
                if turn == 0:
                    outcomes.append(outcome)  # 성적은 첫 판정으로 낸다
                runs.setdefault(case.id, []).append(outcome.actual)
                records.append(
                    {
                        "case_id": case.id,
                        "turn": turn,
                        "actual": outcome.actual,
                        "model_said": outcome.model_said,
                    }
                )
                print(f"  · {case.id} ({turn + 1}/{args.repeat})")
    finally:
        await llm.aclose()
        # 저장은 반드시 finally 에서. 무료 등급은 업스트림이 붐비면 502 로 중간에
        # 죽는데(실제로 겪었다), 루프 뒤에서 저장하면 그때까지 태운 호출이 통째로
        # 사라진다. 부분 결과라도 남으면 이어서 채울 수 있다.
        if args.save and records:
            save_runs(args.save, settings.llm_model, args.repeat, records)

    if len(records) < planned:
        print(
            f"\n주의: {planned}회 예정 중 {len(records)}회만 끝났다. "
            "아래 집계는 그만큼만 본 것이다."
        )

    report(outcomes, runs if args.repeat > 1 else {}, settings.llm_model)


if __name__ == "__main__":
    asyncio.run(main())
