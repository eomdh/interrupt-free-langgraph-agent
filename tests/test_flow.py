"""전 구간 통합 — 목 LLM으로 온보딩부터 확정까지 돈다.

**매 `ainvoke`가 POST 한 번이다.** 중간에 멈추는 지점이 없고, 다음 호출이
곧 재개다(ADR 0001). 같은 `thread_id`로 부르면 체크포인터가 앞 대화를
들고 있으므로 요청에는 이번 턴 입력만 넘긴다.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph
from agent.intents import AXES
from agent.state import new_thread_state
from tests.helpers import last_reply, turn


@pytest.fixture
def run(make_llm):
    """같은 스레드로 여러 턴을 던지는 러너."""
    llm = make_llm()
    graph = build_graph(llm, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}

    async def _run(payload: dict) -> dict:
        return await graph.ainvoke(payload, config)

    _run.llm = llm  # type: ignore[attr-defined]
    return _run


@pytest.fixture
def drive(make_llm):
    """목을 갈아끼운 채 초안 생성까지 밀어붙이는 러너."""

    async def _drive(**llm_overrides) -> tuple[dict, object]:
        llm = make_llm(**llm_overrides)
        graph = build_graph(llm, checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "t"}}

        await graph.ainvoke(new_thread_state() | turn("리뷰 써야 해"), config)
        await graph.ainvoke(turn("결제 지연을 줄였어요", intent="provide_info"), config)
        state = await graph.ainvoke(turn("초안 써줘", intent="write_now"), config)
        return state, llm

    return _drive


async def test_온보딩부터_확정까지_한_번에_돈다(run):
    # 1턴 — 아직 프로필이 없다. 무슨 말을 해도 온보딩으로 간다.
    state = await run(new_thread_state() | turn("성과 리뷰 써야 해"))
    assert state["profile"] == {"role": "백엔드 엔지니어", "period": "2026 상반기"}

    # 2턴 — 한 일을 서술하면 성과로 쪼갠다.
    state = await run(turn("결제 지연을 줄였어요", intent="provide_info"))
    assert len(state["achievements"]) == 1

    # 3턴 — 동의가 있어야 초안이 나온다. 채점을 통과해 그대로 전달된다.
    state = await run(turn("초안 써줘", intent="write_now"))
    assert state["draft"]
    assert state["tags"] == {axis: True for axis in AXES}
    assert "이대로 확정할까요?" in last_reply(state)

    # 4턴 — 확정.
    state = await run(turn("좋아 이대로", intent="proceed"))
    assert "확정했습니다" in last_reply(state)


async def test_복원_코드_없이_대화가_통째로_남는다(run):
    """질문이 특수 상태가 아니라 그냥 `AIMessage`라 체크포인터가 다 들고 있다."""
    await run(new_thread_state() | turn("리뷰 써야 해"))
    state = await run(turn("결제 지연을 줄였어요", intent="provide_info"))

    assert sum(isinstance(m, HumanMessage) for m in state["messages"]) == 2
    assert sum(isinstance(m, AIMessage) for m in state["messages"]) == 2


async def test_동의_없이는_초안이_안_나온다(run):
    await run(new_thread_state() | turn("리뷰 써야 해"))
    state = await run(turn("결제 지연을 줄였어요", intent="provide_info"))
    assert state["draft"] is None

    # 재료가 모여도 제안까지만 한다.
    state = await run(turn("그리고 또 뭐 하지", intent="continue"))
    assert state["draft"] is None
    assert "초안을 써볼까요?" in last_reply(state)


async def test_채점이_미달이면_상한까지_다시_쓴다(drive, tags_json):
    """정량성만 계속 미달 — 상한에서 미달인 채로 내보낸다(ADR 0003)."""
    state, llm = await drive(tag=tags_json(정량성=False))

    assert state["revise_count"] == 2  # 첫 초안 0 → 재작성 2회
    assert len([c for c in llm.calls if c["task"] == "draft"]) == 3
    assert "정량성" in last_reply(state)


async def test_허위가_안_걷히면_초안_대신_막힌다(drive, tags_json):
    """과장허위만 계속 미달 — 초안이 사용자에게 안 간다(ADR 0005)."""
    state, _ = await drive(tag=tags_json(과장허위=False))

    reply = last_reply(state)
    assert "내보내지 않았습니다" in reply
    assert "매출 30% 증가" in reply  # 어느 문장이 문제였는지 짚어준다
    assert state["draft"] not in reply  # 초안 본문은 새어 나가지 않는다


async def test_채점은_0도_생성은_0점4로_부른다(drive):
    """같은 입력에 같은 판정이 나와야 한다(ADR 0003)."""
    _, llm = await drive()

    temperatures = {c["task"]: c["temperature"] for c in llm.calls}
    assert temperatures["tag"] == 0.0
    assert temperatures["draft"] == 0.4
