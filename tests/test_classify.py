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

    assert "client_intent" not in result  # 칩을 덮지 않는다
    assert llm.calls == []  # 부르지도 않는다


async def test_매_턴_재작성_예산을_되돌린다(make_state):
    """`classify`는 매 턴의 첫 노드라 리셋의 자리다(ADR 0010).

    상태 내용에서 "이번 턴의 첫 초안인가"를 유추하면, 모델이 빈 초안을 주는
    순간 그 유추가 매번 참이 되어 카운터가 영영 안 오르고 루프가 안 멈춘다.
    """
    for intent in (None, "write_now"):  # 분류를 타든 칩으로 건너뛰든
        state = make_state(messages=[HumanMessage("초안 써줘")], client_intent=intent)
        result, _ = await _classify(state, "write_now")
        assert result["draft_attempts"] is None  # None = 리셋 신호


def test_라벨끼리_서로_부분_문자열이_아니다():
    """포함 검사로 골라내므로, 하나가 다른 것에 섞여 있으면 오분류가 된다."""
    for intent in INTENTS:
        others = [other for other in INTENTS if other != intent]
        assert not any(intent in other for other in others)


@pytest.mark.parametrize(
    "answer",
    [
        "provide_info 아니면 write_now",
        "revise 를 원하지 않고 proceed 를 원한다",
        "이 발화는 write_now 가 아니라 provide_info 입니다",
    ],
)
def test_라벨이_둘_이상이면_고르지_않는다(answer):
    """앞선 것을 집으면 부정문에서 정반대로 분류된다.

    한때 이 동작을 "결정적이라 좋다"며 테스트로 고정해 뒀다 — 회귀 테스트가
    버그를 잠그고 있었던 셈이다. 무엇을 원하는지 모르겠으면 모른다고 답한다.
    """
    assert _as_intent(answer) is None
