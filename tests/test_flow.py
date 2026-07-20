"""전 구간 통합 — 목 LLM으로 온보딩부터 확정까지 돈다.

**매 `ainvoke`가 POST 한 번이다.** 중간에 멈추는 지점이 없고, 다음 호출이
곧 재개다(ADR 0001). 같은 `thread_id`로 부르면 체크포인터가 앞 대화를
들고 있으므로 요청에는 이번 턴 입력만 넘긴다.
"""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph
from agent.intents import AXES
from agent.llm import FakeLLM

ACHIEVEMENT = {
    "title": "결제 지연 개선",
    "situation": "피크 시간대 결제 p95가 1.2초였다",
    "task": "지연을 줄인다",
    "action": "N+1 조회를 배치로 묶고 인덱스를 다시 잡았다",
    "result": "p95 340ms",
}


def _tags(**overrides) -> str:
    scored = {axis: True for axis in AXES}
    scored.update(overrides)
    return json.dumps(scored, ensure_ascii=False)


def _llm(**overrides) -> FakeLLM:
    responses = {
        "onboard": json.dumps({"role": "백엔드 엔지니어", "period": "2026 상반기"}),
        "analyze": json.dumps([ACHIEVEMENT], ensure_ascii=False),
        "interview": "그 수치는 어떻게 측정했나요?",
        "draft": "2026 상반기에 결제 지연을 개선했다. p95를 1.2초에서 340ms로 줄였다.",
        "tag": _tags(),
        "blocked": "매출 30% 증가",
        "respond": "네, 편하게 말씀해주세요.",
    }
    responses.update(overrides)
    return FakeLLM(responses)


def _blank() -> dict:
    """새 스레드의 초기 상태. API가 스레드를 열 때 넣어주는 값이다."""
    return {
        "messages": [],
        "profile": {},
        "achievements": [],
        "draft": None,
        "tags": None,
        "revise_count": 0,
        "client_intent": None,
    }


def _turn(text: str, intent: str | None = None) -> dict:
    """POST 한 번치 입력.

    `client_intent`는 **매 턴 명시한다.** 안 넘기면 지난 턴의 칩이 상태에
    남아 다시 게이트를 연다.
    """
    return {"messages": [HumanMessage(text)], "client_intent": intent}


def _last_reply(state: dict) -> str:
    return str(state["messages"][-1].content)


@pytest.fixture
def run():
    """같은 스레드로 여러 턴을 던지는 러너."""
    llm = _llm()
    graph = build_graph(llm, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    state: dict = {}

    async def _run(payload: dict) -> dict:
        nonlocal state
        state = await graph.ainvoke(payload, config)
        return state

    _run.llm = llm  # type: ignore[attr-defined]
    return _run


async def test_온보딩부터_확정까지_한_번에_돈다(run):
    # 1턴 — 아직 프로필이 없다. 무슨 말을 해도 온보딩으로 간다.
    state = await run(_blank() | _turn("성과 리뷰 써야 해"))
    assert state["profile"] == {"role": "백엔드 엔지니어", "period": "2026 상반기"}

    # 2턴 — 한 일을 서술하면 성과로 쪼갠다.
    state = await run(_turn("결제 지연을 줄였어요", intent="provide_info"))
    assert len(state["achievements"]) == 1

    # 3턴 — 동의가 있어야 초안이 나온다. 채점을 통과해 그대로 전달된다.
    state = await run(_turn("초안 써줘", intent="write_now"))
    assert state["draft"]
    assert state["tags"] == {axis: True for axis in AXES}
    assert "이대로 확정할까요?" in _last_reply(state)

    # 4턴 — 확정.
    state = await run(_turn("좋아 이대로", intent="proceed"))
    assert "확정했습니다" in _last_reply(state)


async def test_새로고침_복원_대신_체크포인터가_대화를_들고_있다(run):
    """질문이 특수 상태가 아니라 그냥 `AIMessage`라 대화가 통째로 남는다."""
    await run(_blank() | _turn("리뷰 써야 해"))
    state = await run(_turn("결제 지연을 줄였어요", intent="provide_info"))

    # 두 턴이 전부 남아 있다 — 사람 발화 2, 에이전트 답 2.
    assert sum(isinstance(m, HumanMessage) for m in state["messages"]) == 2
    assert sum(isinstance(m, AIMessage) for m in state["messages"]) == 2


async def test_동의_없이는_초안이_안_나온다(run):
    await run(_blank() | _turn("리뷰 써야 해"))
    state = await run(_turn("결제 지연을 줄였어요", intent="provide_info"))
    assert state["draft"] is None

    # 재료가 모여도 제안까지만 한다.
    state = await run(_turn("그리고 또 뭐 하지", intent="continue"))
    assert state["draft"] is None
    assert "초안을 써볼까요?" in _last_reply(state)


async def test_채점이_미달이면_상한까지_다시_쓴다():
    """정량성만 계속 미달 — 상한에서 미달인 채로 내보낸다(ADR 0003)."""
    llm = _llm(tag=_tags(정량성=False))
    graph = build_graph(llm, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t2"}}

    await graph.ainvoke(_blank() | _turn("리뷰 써야 해"), config)
    await graph.ainvoke(_turn("결제 지연을 줄였어요", intent="provide_info"), config)
    state = await graph.ainvoke(_turn("초안 써줘", intent="write_now"), config)

    assert state["revise_count"] == 2  # 첫 초안 0 → 재작성 2회
    assert len([c for c in llm.calls if c["task"] == "draft"]) == 3
    assert "정량성" in _last_reply(state)


async def test_허위가_안_걷히면_초안_대신_막힌다():
    """과장허위만 계속 미달 — 초안이 사용자에게 안 간다(ADR 0005)."""
    llm = _llm(tag=_tags(과장허위=False))
    graph = build_graph(llm, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t3"}}

    await graph.ainvoke(_blank() | _turn("리뷰 써야 해"), config)
    await graph.ainvoke(_turn("결제 지연을 줄였어요", intent="provide_info"), config)
    state = await graph.ainvoke(_turn("초안 써줘", intent="write_now"), config)

    reply = _last_reply(state)
    assert "내보내지 않았습니다" in reply
    assert "매출 30% 증가" in reply  # 어느 문장이 문제였는지 짚어준다
    assert state["draft"] not in reply  # 초안 본문은 새어 나가지 않는다


async def test_채점은_0도_생성은_0점4로_부른다(run):
    """같은 입력에 같은 판정이 나와야 한다(ADR 0003)."""
    await run(_blank() | _turn("리뷰 써야 해"))
    await run(_turn("결제 지연을 줄였어요", intent="provide_info"))
    await run(_turn("초안 써줘", intent="write_now"))

    calls = {c["task"]: c["temperature"] for c in run.llm.calls}
    assert calls["tag"] == 0.0
    assert calls["draft"] == 0.4
