"""의도 분류 — 자유 서술이 어떤 라벨로 떨어지는가.

여기서 잡는 것은 **분류가 실패하는 방향**이다. 모르는 답이 오면 게이트를 여는
게 아니라 제자리에 서야 한다(ADR 0008). 분류가 맞는지는 모델 몫이라 목으로
증명할 수 없고, 목으로 증명할 수 있는 건 "틀렸을 때 어디로 떨어지나"뿐이다.
"""

import pytest
from langchain_core.messages import HumanMessage

from agent.intents import INTENTS
from agent.llm import FakeLLM
from agent.nodes import _as_intent, make_classify


async def _classify(state, answer: str = "continue"):
    llm = FakeLLM({"classify": answer})
    result = await make_classify(llm)(state)
    return result, llm


@pytest.mark.parametrize("intent", INTENTS)
async def test_아는_라벨은_그대로_받는다(make_state, intent):
    state = make_state(messages=[HumanMessage("뭐라도 말한다")])
    result, _ = await _classify(state, intent)
    assert result["client_intent"] == intent


@pytest.mark.parametrize(
    "answer",
    ['"write_now"', "write_now.", "  WRITE_NOW  ", "라벨: write_now"],
)
async def test_군더더기가_붙어도_골라낸다(make_state, answer):
    """모델이 따옴표·마침표·설명을 붙이는 일이 흔하다. 정확 일치를 기대하지 않는다."""
    state = make_state(messages=[HumanMessage("초안 써주세요")])
    result, _ = await _classify(state, answer)
    assert result["client_intent"] == "write_now"


@pytest.mark.parametrize("answer", ["", "몰라요", "intent=삭제해줘", "{}"])
async def test_모르는_답은_비워_둔다(make_state, answer):
    """라우터가 `continue`로 읽는다 — 분류 실패는 **덜 나아가는** 쪽이다."""
    state = make_state(messages=[HumanMessage("음...")])
    result, _ = await _classify(state, answer)
    assert result["client_intent"] is None


async def test_칩이_있으면_분류하지_않는다(make_state):
    """사용자가 명시한 것이 우선이고, LLM 호출도 그만큼 아낀다(ADR 0002)."""
    state = make_state(
        messages=[HumanMessage("초안 써주세요")],
        client_intent="proceed",  # 칩으로 들어온 값
    )
    result, llm = await _classify(state, "write_now")

    assert result == {}  # 손대지 않는다
    assert llm.calls == []  # 부르지도 않는다


def test_라벨끼리_서로_부분_문자열이_아니다():
    """포함 검사로 골라내므로, 하나가 다른 것에 섞여 있으면 오분류가 된다."""
    for intent in INTENTS:
        others = [other for other in INTENTS if other != intent]
        assert not any(intent in other for other in others)


def test_먼저_나온_라벨을_고른다():
    """두 개가 섞여 오면 앞선 것을 고른다 — 결정적이어야 재현이 된다."""
    assert _as_intent("provide_info 아니면 write_now") == "provide_info"
