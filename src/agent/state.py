"""그래프 상태.

앱은 무상태다. 진행 중인 대화는 전부 체크포인터에 있다(ADR 0001).
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from agent.intents import Axis, Intent


class Profile(TypedDict, total=False):
    """온보딩에서 받는 것. 둘 다 차야 `profile_ok`."""

    role: str  # 직무
    period: str  # 평가 기간


class Achievement(TypedDict, total=False):
    """성과 하나. STAR 조각으로 쪼개 둔다."""

    title: str
    situation: str
    task: str
    action: str
    result: str


def reset_or_add(current: int, update: int | None) -> int:
    """재작성 카운터 reducer. `None`은 값이 아니라 리셋 신호다.

    `operator.add`로는 값을 줄일 수 없어서, 항목이 바뀌어도 카운터가 0으로
    안 돌아간다. 변화가 없을 땐 노드가 키 자체를 반환하지 않는다.
    """
    if update is None:
        return 0
    return current + update


class ReviewState(TypedDict):
    """성과 리뷰 초안 코치의 그래프 상태."""

    #: 질문도 그냥 `AIMessage`로 쌓인다 — 새로고침 복원이 여기서 나온다(ADR 0001).
    messages: Annotated[list[AnyMessage], add_messages]

    profile: Profile
    achievements: Annotated[list[Achievement], operator.add]

    draft: str | None
    #: 5축 채점 결과. 판정 불가는 미달로 정규화한다(`is_passing_tags`).
    tags: dict[Axis, bool] | None

    #: draft ⇄ tag 루프 횟수. `MAX_REVISE`에서 멈춘다(ADR 0003).
    revise_count: Annotated[int, reset_or_add]

    #: 액션 칩이 실어 보낸 의도. 분류는 건너뛰어도 게이트는 통과해야 한다(ADR 0002).
    #: ⚠️ 이 필드는 안 덮으면 지난 턴 값이 남는다. **매 턴 명시해서 넣어야 한다** —
    #: 칩을 안 눌렀으면 `None`으로. 안 그러면 지난 칩이 게이트를 다시 연다.
    client_intent: Intent | None


def new_thread_state() -> ReviewState:
    """새 스레드의 초기 상태.

    LangGraph는 안 넘긴 키를 아예 만들지 않는다. 라우터가 `state["profile"]`처럼
    직접 인덱싱하므로, 첫 턴에는 전 필드를 채워 넣어야 `KeyError`가 안 난다.
    """
    return {
        "messages": [],
        "profile": {},
        "achievements": [],
        "draft": None,
        "tags": None,
        "revise_count": 0,
        "client_intent": None,
    }
