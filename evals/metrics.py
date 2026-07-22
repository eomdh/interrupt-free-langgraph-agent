"""평가 집계 — 순수 함수만.

네트워크도 모델도 부르지 않는다. 그래서 **이 파일은 일반 테스트가 덮는다**
(`tests/test_evals.py`). 러너는 실모델이 필요해 CI에서 못 도는데, 집계가
틀리면 평가 결과 자체를 믿을 수 없다 — 순수한 부분을 떼어낸 이유다.
"""

from dataclasses import dataclass

from agent.intents import AXES, Axis

#: 5축 판정 한 벌.
Verdict = dict[str, bool]


def normalize(raw: dict | None) -> Verdict:
    """축이 빠지거나 값이 이상하면 미달로 읽는다.

    프로덕션의 fail-safe(`router.is_passing_tags`)와 **같은 규칙이어야 한다.**
    평가가 더 너그러우면 실제보다 좋은 점수가 나오고, 그 점수는 거짓말이다.
    """
    raw = raw or {}
    return {axis: raw.get(axis) is True for axis in AXES}


@dataclass(frozen=True)
class CaseOutcome:
    """케이스 하나의 결과.

    `actual`과 `model_said`를 **따로** 들고 있다. `make_tag`는 결정적 룰까지
    적용한 뒤의 판정만 돌려주므로, 그것만 보면 하이브리드에서 룰이 무엇을
    했는지 귀속할 수 없다(`rule_flips`).
    """

    case_id: str
    expected: Verdict  # 사람이 붙인 라벨
    actual: Verdict  # 룰까지 적용한 최종 판정 = 프로덕션이 실제로 쓰는 값
    model_said: Verdict  # 룰 적용 전 모델 단독 판정


@dataclass(frozen=True)
class AxisScore:
    """축 하나의 성적.

    일치율 하나로 뭉치지 않고 **틀린 방향을 나눈다.** 두 오류의 값이 다르기
    때문이다 — `과장허위`에서 `miss`는 근거 없는 초안을 사용자에게 내보내는
    것이고(ADR 0005가 막으려는 바로 그 실패), `false_alarm`은 멀쩡한 초안을
    한 번 더 쓰게 하는 것이다. 뒤의 비용은 재작성 한 번, 앞의 비용은 신뢰다.
    """

    axis: Axis
    agree: int
    miss: int  # 사람은 미달인데 모델이 통과 — 게이트 누출
    false_alarm: int  # 사람은 통과인데 모델이 미달 — 헛경보

    @property
    def total(self) -> int:
        return self.agree + self.miss + self.false_alarm

    @property
    def accuracy(self) -> float:
        return self.agree / self.total if self.total else 0.0


def score_axis(outcomes: list[CaseOutcome], axis: Axis) -> AxisScore:
    agree = miss = false_alarm = 0
    for outcome in outcomes:
        expected, actual = outcome.expected[axis], outcome.actual[axis]
        if expected == actual:
            agree += 1
        elif actual:  # 사람은 False 라 했는데 모델이 True
            miss += 1
        else:
            false_alarm += 1
    return AxisScore(axis=axis, agree=agree, miss=miss, false_alarm=false_alarm)


def score_all(outcomes: list[CaseOutcome]) -> dict[Axis, AxisScore]:
    return {axis: score_axis(outcomes, axis) for axis in AXES}


def rule_flips(outcomes: list[CaseOutcome], axis: Axis) -> list[str]:
    """결정적 룰이 모델 판정을 뒤집은 케이스.

    하이브리드의 기여도를 귀속한다(ADR 0004). 여기 이름이 없으면 룰은 그냥
    안 도는 코드다 — "룰과 LLM을 같이 쓴다"가 문서에만 있는지 실제로 값을
    내는지가 이 목록으로 갈린다.

    룰은 **취소만 한다.** True→False 만 세는 이유다(`nodes._unsupported_numbers`).
    """
    return [
        outcome.case_id
        for outcome in outcomes
        if outcome.model_said[axis] and not outcome.actual[axis]
    ]


def unstable_axes(runs: list[Verdict]) -> list[Axis]:
    """같은 입력을 여러 번 돌렸을 때 판정이 갈린 축.

    ADR 0003은 *"LLM 판정은 결정적이지 않아서 같은 초안이 돌 때마다 다르게
    찍힐 수 있다"*를 `MAX_REVISE`의 근거로 삼는다. 그건 **주장**이다.
    temperature 0으로 같은 케이스를 반복해서, 그 주장이 이 모델에서 참인지
    숫자로 만든다. 비어 있으면 그 근거는 이 모델에 한해 약하다는 뜻이다.
    """
    if len(runs) < 2:
        return []
    return [axis for axis in AXES if len({run[axis] for run in runs}) > 1]
