"""그래프 조립.

한 번의 `ainvoke`가 START에서 END까지 끝난다. 중간에 멈추는 지점이 없다 —
그게 이 앱의 핵심 결정이다(ADR 0001).

    START → router ─┬→ onboard       → END
                    ├→ analyze       → END
                    ├→ interview     → END
                    ├→ propose_draft → END
                    ├→ draft ⇄ tag ─┬→ deliver → END
                    │                └→ blocked → END
                    ├→ finalize      → END
                    └→ respond       → END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent import nodes
from agent.intents import MAX_REVISE
from agent.llm import LLM
from agent.router import is_passing_tags, passes_hallucination_gate, route_from_router
from agent.state import ReviewState

_NODE_FACTORIES = {
    "onboard": nodes.make_onboard,
    "analyze": nodes.make_analyze,
    "interview": nodes.make_interview,
    "propose_draft": nodes.make_propose_draft,
    "draft": nodes.make_draft,
    "tag": nodes.make_tag,
    "deliver": nodes.make_deliver,
    "finalize": nodes.make_finalize,
    "blocked": nodes.make_blocked,
    "respond": nodes.make_respond,
}

#: router가 고를 수 있는 목적지. `deliver`·`blocked`는 채점 뒤에서만 나온다.
_ROUTER_TARGETS = [name for name in _NODE_FACTORIES if name not in ("deliver", "blocked")]

#: 초안 루프에 속한 노드. 나머지는 한 번 돌고 곧장 END로 나간다.
_LOOP_NODES = ("draft", "tag")


def route_after_tag(state: ReviewState) -> str:
    """채점 뒤 갈림길 — 다시 쓸 것인가, 내보낼 것인가, 막을 것인가.

    상한에 걸리면 품질 축은 **미달인 채로 내보낸다.** 억지로 통과시키면
    사용자가 완성됐다고 믿는다(ADR 0003).

    허위 축은 양보하지 않는다. 상한까지 안 걷히면 초안 대신 `blocked`로
    빠진다 — 근거를 확인 못 한 문장은 내보내지 않는다(ADR 0005).
    """
    if is_passing_tags(state["tags"]):
        return "deliver"
    if state["revise_count"] >= MAX_REVISE:
        return "deliver" if passes_hallucination_gate(state["tags"]) else "blocked"
    return "draft"


def build_graph(llm: LLM, checkpointer=None):
    """그래프를 조립해 컴파일한다.

    LLM을 인자로 받아 각 노드에 넘긴다. 주입이 타입으로 드러나고, 테스트는
    목을 넣어 키 없이 전 구간을 돌릴 수 있다.

    체크포인터가 상태의 유일한 저장소다. 운영에서는 Postgres, 테스트에서는
    `MemorySaver`를 넣는다.
    """
    builder = StateGraph(ReviewState)

    for name, factory in _NODE_FACTORIES.items():
        builder.add_node(name, factory(llm))

    # router는 노드가 아니라 START의 분기다 — 매 POST가 여기서 시작한다.
    builder.add_conditional_edges(START, route_from_router, _ROUTER_TARGETS)

    # draft ⇄ tag 자율 루프.
    builder.add_edge("draft", "tag")
    builder.add_conditional_edges("tag", route_after_tag, ["draft", "deliver", "blocked"])

    for name in _NODE_FACTORIES:
        if name not in _LOOP_NODES:
            builder.add_edge(name, END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
