"""self-eval 루프 — 언제 다시 쓰고 언제 멈추는가(ADR 0003)."""

import pytest

from agent.graph import route_after_tag
from agent.intents import AXES, MAX_REVISE
from agent.router import is_passing_tags, passes_hallucination_gate


def test_전_축_통과면_내보낸다(make_state, passing):
    state = make_state(tags=passing, revise_count=0)
    assert route_after_tag(state) == "deliver"


def test_미달이고_상한_전이면_다시_쓴다(make_state, passing):
    state = make_state(tags=passing | {"정량성": False}, revise_count=0)
    assert route_after_tag(state) == "draft"


def test_상한에_도달하면_품질_미달은_내보낸다(make_state, passing):
    """억지로 통과시키지 않되, 결과물은 준다. 무엇이 부족한지 함께 알린다."""
    state = make_state(tags=passing | {"정량성": False}, revise_count=MAX_REVISE)
    assert route_after_tag(state) == "deliver"


def test_과장허위만_미달이어도_되돌린다(make_state, passing):
    """품질 축과 달리 이 축은 하드 게이트다(ADR 0004)."""
    state = make_state(tags=passing | {"과장허위": False}, revise_count=0)
    assert route_after_tag(state) == "draft"


def test_상한까지_허위가_안_걷히면_초안을_막는다(make_state, passing):
    """품질 축은 상한에서 양보하지만 허위 축은 안 한다(ADR 0005).

    근거를 확인 못 한 문장을 내보내느니 결과물 없이 끝내는 쪽을 고른다.
    """
    state = make_state(tags=passing | {"과장허위": False}, revise_count=MAX_REVISE)
    assert route_after_tag(state) == "blocked"


def test_품질과_허위가_같이_미달이면_상한에서도_막는다(make_state, passing):
    """허위가 섞여 있으면 다른 축의 상태와 무관하게 막힌다."""
    tags = passing | {"정량성": False, "과장허위": False}
    state = make_state(tags=tags, revise_count=MAX_REVISE)
    assert route_after_tag(state) == "blocked"


# --- 허위 축 단독 판정 ---


def test_허위_축이_통과면_게이트_통과(passing):
    assert passes_hallucination_gate(passing) is True


def test_허위_축이_미달이면_게이트_불통과(passing):
    assert passes_hallucination_gate(passing | {"과장허위": False}) is False


def test_허위_축이_없으면_불통과():
    """판정 불가는 미달 — 여기서도 같다."""
    assert passes_hallucination_gate({"구체성": True}) is False
    assert passes_hallucination_gate(None) is False


# --- fail-safe: 판정 불가 = 미달 ---


def test_전_축_통과면_통과다(passing):
    assert is_passing_tags(passing) is True


def test_tags가_없으면_미달():
    assert is_passing_tags(None) is False


@pytest.mark.parametrize("missing", AXES)
def test_축이_하나라도_빠지면_미달(missing):
    tags = {axis: True for axis in AXES if axis != missing}
    assert is_passing_tags(tags) is False


@pytest.mark.parametrize("junk", ["통과", 1, "", None, "❌"])
def test_불량_값은_전부_미달로_정규화(passing, junk):
    """모델이 bool이 아닌 걸 뱉어도 통과로 새지 않는다."""
    assert is_passing_tags(passing | {"구체성": junk}) is False
