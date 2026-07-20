"""그래프 상태.

앱은 무상태다. 진행 중인 대화는 전부 체크포인터에 있고, FastAPI는 아무것도
기억하지 않는다(ADR 0001). 그래서 이 TypedDict가 사실상 이 앱의 전부다.
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
    """카운터 reducer. `None`이 오면 0으로 리셋한다.

    `operator.add`만 쓰면 값을 **줄일 수 없다.** 항목이 바뀔 때 재작성 횟수를
    되돌리지 못해서, 두 번째 항목이 시작부터 상한(`MAX_REVISE`)에 걸린 채로
    출발한다. 원본에서 실제로 밟은 함정이라 회귀 테스트로 묶어 둔다.

    TODO(구현): `update is None`이면 0, 아니면 `current + update`.
    """
    raise NotImplementedError


class ReviewState(TypedDict):
    """성과 리뷰 초안 코치의 그래프 상태."""

    #: 대화 기록. 질문도 그냥 `AIMessage`로 여기 쌓인다 — 그래서 새로고침
    #: 복원이 별도 구현 없이 따라온다(ADR 0001).
    messages: Annotated[list[AnyMessage], add_messages]

    profile: Profile
    achievements: Annotated[list[Achievement], operator.add]

    draft: str | None
    #: 5축 채점 결과. 축이 빠져 있거나 값이 이상하면 전부 미달로 정규화한다
    #: ("판정 불가 = 미달"). `is_passing_tags` 참조.
    tags: dict[Axis, bool] | None

    #: draft ⇄ tag 루프를 몇 번 돌았나. `MAX_REVISE`에서 멈춘다(ADR 0003).
    revise_count: Annotated[int, reset_or_add]

    #: 프론트 액션 칩이 실어 보낸 의도. LLM 분류는 건너뛰지만 상태 게이트는
    #: 그대로 통과해야 한다(ADR 0002).
    client_intent: Intent | None
