"""그래프 상태.

앱은 무상태다. 진행 중인 대화는 전부 체크포인터에 있다(ADR 0001).
"""

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


#: 한 스레드가 들고 갈 성과 상한. 누적된 전체가 매 턴 `interview`·`draft`·
#: `tag`·`blocked` 프롬프트에 다시 실리므로, 상한이 없으면 토큰 비용이 대화
#: 길이에 대해 2차로 는다. 넘치면 오래된 것부터 흘린다.
MAX_ACHIEVEMENTS = 20


def add_achievements(current: list[Achievement], update: list[Achievement]) -> list[Achievement]:
    """성과를 쌓되 상한을 지킨다. `operator.add`와 달리 무한히 자라지 않는다."""
    return (current + update)[-MAX_ACHIEVEMENTS:]


def reset_or_add(current: int, update: int | None) -> int:
    """시도 카운터 reducer. `None`은 값이 아니라 리셋 신호다.

    `operator.add`로는 값을 줄일 수 없어서, 턴이 바뀌어도 카운터가 0으로
    안 돌아간다. 변화가 없을 땐 노드가 키 자체를 반환하지 않는다.

    **리셋 신호는 턴 경계에서만 나온다**(`make_classify`). 이 신호를 상태
    내용으로 유추하면 그 유추가 틀리는 순간 루프가 안 멈춘다(ADR 0010).
    """
    if update is None:
        return 0
    return current + update


class ReviewState(TypedDict):
    """성과 리뷰 초안 코치의 그래프 상태."""

    #: 질문도 그냥 `AIMessage`로 쌓인다 — 새로고침 복원이 여기서 나온다(ADR 0001).
    messages: Annotated[list[AnyMessage], add_messages]

    profile: Profile
    achievements: Annotated[list[Achievement], add_achievements]

    draft: str | None
    #: 5축 채점 결과. 판정 불가는 미달로 정규화한다(`is_passing_tags`).
    tags: dict[Axis, bool] | None

    #: **이번 턴에** `draft`가 돈 횟수. `MAX_REVISE`를 넘으면 멈춘다(ADR 0003).
    #:
    #: 매 턴 첫 노드인 `classify`가 리셋한다. 초안 내용에서 "첫 초안인가"를
    #: 유추하면 안 된다 — 모델이 빈 초안을 주는 순간 그 유추가 매번 참이 되어
    #: 카운터가 영영 안 오르고 종료 보장이 통째로 깨진다(ADR 0010).
    draft_attempts: Annotated[int, reset_or_add]

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
        "draft_attempts": 0,
        "client_intent": None,
    }
