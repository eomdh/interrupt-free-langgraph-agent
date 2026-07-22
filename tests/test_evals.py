"""평가 집계가 맞나.

러너는 실모델이 필요해 CI에서 못 돈다. 그러면 집계 코드는 **아무도 안 지킨다** —
그 상태로 낸 점수는 모델이 아니라 버그를 재는 것일 수 있다. 순수 함수로 떼어낸
덕에 여기서 네트워크 없이 덮는다.

골든 셋 자체의 무결성도 같이 본다. 라벨이 한 축이라도 빠지면 그 케이스는
조용히 미달로 읽히고, 점수는 멀쩡해 보이는 채로 틀린다.
"""

import pytest

from agent.intents import AXES, HALLUCINATION_AXIS
from evals.cases import CASES
from evals.metrics import (
    CaseOutcome,
    normalize,
    rule_flips,
    score_axis,
    unstable_axes,
)


def _outcome(case_id: str, *, expected: dict, actual: dict, model_said: dict | None = None):
    return CaseOutcome(
        case_id=case_id,
        expected=normalize(expected),
        actual=normalize(actual),
        model_said=normalize(model_said if model_said is not None else actual),
    )


def _all(value: bool) -> dict:
    return dict.fromkeys(AXES, value)


# --- fail-safe 는 프로덕션과 같은 규칙이어야 한다 ---


def test_빠진_축은_미달로_읽는다():
    """평가가 프로덕션보다 너그러우면 실제보다 좋은 점수가 나온다."""
    assert normalize({"구체성": True}) == _all(False) | {"구체성": True}


def test_참_같은_값은_통과가_아니다():
    """`1 == True` 라서 그냥 받으면 fail-safe 가 뚫린다(`is_passing_tags`와 같은 함정)."""
    assert normalize({axis: 1 for axis in AXES}) == _all(False)


def test_판정이_없으면_전부_미달():
    assert normalize(None) == _all(False)


# --- 틀린 방향을 나눈다 ---


def test_누출과_헛경보를_구분한다():
    """두 오류의 값이 다르다. 뭉치면 하드 게이트가 새는 걸 못 본다(ADR 0005)."""
    outcomes = [
        # 사람은 미달인데 모델이 통과 = 누출
        _outcome("샌다", expected=_all(False), actual=_all(True)),
        # 사람은 통과인데 모델이 미달 = 헛경보
        _outcome("엄격", expected=_all(True), actual=_all(False)),
        _outcome("맞음", expected=_all(True), actual=_all(True)),
    ]

    score = score_axis(outcomes, HALLUCINATION_AXIS)

    assert (score.agree, score.miss, score.false_alarm) == (1, 1, 1)
    assert score.total == 3
    assert score.accuracy == pytest.approx(1 / 3)


def test_케이스가_없으면_일치율은_0():
    """0으로 나누지 않는다."""
    assert score_axis([], HALLUCINATION_AXIS).accuracy == 0.0


# --- 룰 귀속 ---


def test_룰이_뒤집은_케이스만_센다():
    outcomes = [
        # 모델은 통과라 했는데 최종이 미달 = 룰이 취소했다
        _outcome("취소됨", expected=_all(False), actual=_all(False), model_said=_all(True)),
        # 모델도 최종도 통과 = 룰이 안 걸렸다
        _outcome("그대로", expected=_all(True), actual=_all(True), model_said=_all(True)),
    ]

    assert rule_flips(outcomes, HALLUCINATION_AXIS) == ["취소됨"]


def test_룰은_통과를_부여하지_않는다():
    """미달→통과 방향은 룰이 만들 수 없다. 세면 안 된다(`_unsupported_numbers`)."""
    outcomes = [
        _outcome("불가능", expected=_all(True), actual=_all(True), model_said=_all(False))
    ]

    assert rule_flips(outcomes, HALLUCINATION_AXIS) == []


# --- 흔들림 ---


def test_갈린_축만_집어낸다():
    runs = [
        _all(True),
        _all(True) | {HALLUCINATION_AXIS: False},
    ]

    assert unstable_axes(runs) == [HALLUCINATION_AXIS]


def test_한_번만_돌렸으면_흔들림을_말하지_않는다():
    """반복이 없으면 비결정성에 대해 아무것도 관측하지 않은 것이다."""
    assert unstable_axes([_all(True)]) == []


def test_매번_같으면_비어_있다():
    assert unstable_axes([_all(True), _all(True), _all(True)]) == []


# --- 골든 셋 무결성 ---


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_모든_케이스가_5축을_전부_라벨한다(case):
    """한 축이라도 빠지면 조용히 미달로 읽히고, 점수는 멀쩡해 보이는 채로 틀린다."""
    assert set(case.expected) == set(AXES)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_모든_케이스가_라벨_근거를_적었다(case):
    """근거 없는 라벨로 잰 점수는 모델이 아니라 라벨을 재는 것이다."""
    assert case.why.strip()
    assert case.draft.strip()


def test_케이스_id가_안_겹친다():
    """겹치면 흔들림 집계(`runs` dict)에서 한쪽이 조용히 덮인다."""
    ids = [case.id for case in CASES]
    assert len(ids) == len(set(ids))


def test_허위_케이스와_정상_케이스가_둘_다_있다():
    """한쪽만 있으면 일치율이 높아도 아무 말을 못 한다."""
    labels = {case.expected[HALLUCINATION_AXIS] for case in CASES}
    assert labels == {True, False}
