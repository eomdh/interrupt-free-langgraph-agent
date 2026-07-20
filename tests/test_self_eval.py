"""self-eval 루프 — 언제 다시 쓰고 언제 멈추는가(ADR 0003)."""

import pytest
from langgraph.graph import END

from agent.graph import route_after_tag
from agent.intents import AXES, MAX_REVISE
from agent.router import is_passing_tags


def test_전_축_통과면_끝낸다(make_state, passing):
    state = make_state(tags=passing, revise_count=0)
    assert route_after_tag(state) == END


def test_미달이고_상한_전이면_다시_쓴다(make_state, passing):
    state = make_state(tags=passing | {"정량성": False}, revise_count=0)
    assert route_after_tag(state) == "draft"


def test_상한에_도달하면_미달인_채로_끝낸다(make_state, passing):
    """억지로 통과시키지 않는다. 무한 루프를 막는 유일한 종료 보장이다."""
    state = make_state(tags=passing | {"정량성": False}, revise_count=MAX_REVISE)
    assert route_after_tag(state) == END


def test_과장허위만_미달이어도_되돌린다(make_state, passing):
    """품질 축과 달리 이 축은 하드 게이트다(ADR 0004)."""
    state = make_state(tags=passing | {"과장허위": False}, revise_count=0)
    assert route_after_tag(state) == "draft"


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
