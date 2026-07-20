"""LLM 출력 파싱 — 모델이 스키마를 안 지켜도 무너지지 않는다.

"JSON으로만 답하라"는 부탁이지 보장이 아니다. 모델을 갈아끼울 수 있는
설계라(`OPENAI_BASE_URL`) 특정 모델의 습관에 기대면 안 된다.
"""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph
from agent.intents import AXES
from agent.nodes import _loads, _strip_fence
from agent.state import new_thread_state
from tests.helpers import last_reply, turn


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('  ```json\n{"a": 1}\n```  ', '{"a": 1}'),
        ("```json\n[1, 2]\n```", "[1, 2]"),
    ],
)
def test_펜스를_벗긴다(raw, expected):
    assert _strip_fence(raw) == expected


def test_펜스가_없으면_그대로_둔다():
    assert _strip_fence("그냥 문장") == "그냥 문장"


@pytest.mark.parametrize("raw", ["", "설명만 하고 끝", "{망가진 json", "null"])
def test_못_읽으면_기본값(raw):
    assert _loads(raw, {}) == {}
    assert _loads(raw, []) == []


def test_타입이_다르면_기본값():
    """배열을 기대했는데 객체가 오면 받아주지 않는다."""
    assert _loads('{"a": 1}', []) == []
    assert _loads("[1, 2]", {}) == {}


async def test_펜스로_감싼_채점도_읽힌다(make_llm, tags_json):
    """모델이 마크다운을 붙여도 판정이 살아 있어야 한다.

    안 그러면 전 축이 미달로 떨어지고, 멀쩡한 초안이 매번 막힌다.
    """
    fenced = f"```json\n{tags_json()}\n```"
    graph = build_graph(make_llm(tag=fenced), MemorySaver())
    config = {"configurable": {"thread_id": "t"}}

    await graph.ainvoke(new_thread_state() | turn("리뷰 써야 해"), config)
    await graph.ainvoke(turn("결제 지연을 줄였어요", intent="provide_info"), config)
    state = await graph.ainvoke(turn("초안 써줘", intent="write_now"), config)

    assert state["tags"] == {axis: True for axis in AXES}
    assert "이대로 확정할까요?" in last_reply(state)


async def test_펜스로_감싼_성과_추출도_읽힌다(make_llm):
    fenced = '```json\n[{"title": "결제 지연 개선"}]\n```'
    graph = build_graph(make_llm(analyze=fenced), MemorySaver())
    config = {"configurable": {"thread_id": "t"}}

    await graph.ainvoke(new_thread_state() | turn("리뷰 써야 해"), config)
    state = await graph.ainvoke(turn("결제 지연을 줄였어요", intent="provide_info"), config)

    assert len(state["achievements"]) == 1
