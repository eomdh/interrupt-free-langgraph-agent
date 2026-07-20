"""그래프 조립.

한 번의 `ainvoke`가 START에서 END까지 끝난다. 중간에 멈추는 지점이 없다 —
그게 이 앱의 핵심 결정이다(ADR 0001).

    START → router ─┬→ onboard       → END
                    ├→ analyze       → END
                    ├→ interview     → END
                    ├→ propose_draft → END
                    ├→ draft ⇄ tag   → END   (미달이면 되돌아감, MAX_REVISE 상한)
                    ├→ finalize      → END
                    └→ respond       → END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent import nodes
from agent.intents import MAX_REVISE
from agent.router import is_passing_tags, route_from_router
from agent.state import ReviewState

_WORKERS = {
    "onboard": nodes.onboard,
    "analyze": nodes.analyze,
    "interview": nodes.interview,
    "propose_draft": nodes.propose_draft,
    "draft": nodes.draft,
    "tag": nodes.tag,
    "finalize": nodes.finalize,
    "respond": nodes.respond,
}


def route_after_tag(state: ReviewState) -> str:
    """채점 뒤 갈림길 — 다시 쓸 것인가 끝낼 것인가.

    상한에 걸리면 **미달인 채로 내보낸다.** 억지로 통과시키면 사용자가
    완성됐다고 믿는다(ADR 0003).
    """
    if is_passing_tags(state.get("tags")):
        return END
    if state.get("revise_count", 0) >= MAX_REVISE:
        return END
    return "draft"


def build_graph(checkpointer=None) -> "StateGraph":
    """그래프를 조립해 컴파일한다.

    체크포인터가 상태의 유일한 저장소다. 운영에서는 Postgres, 테스트에서는
    `MemorySaver`를 넣는다.
    """
    builder = StateGraph(ReviewState)

    for name, fn in _WORKERS.items():
        builder.add_node(name, fn)

    # router는 노드가 아니라 START의 분기다 — 매 POST가 여기서 시작한다.
    builder.add_conditional_edges(START, route_from_router, list(_WORKERS))

    # draft ⇄ tag 자율 루프. 그 외 워커는 한 번 돌고 곧장 END.
    builder.add_edge("draft", "tag")
    builder.add_conditional_edges("tag", route_after_tag, ["draft", END])
    for name in _WORKERS:
        if name not in ("draft", "tag"):
            builder.add_edge(name, END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
