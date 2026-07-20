"""라우터 — 매 POST의 진입점.

`interrupt()`를 안 쓰기 때문에 모든 요청이 여기로 들어온다(ADR 0001).
그래서 라우터가 뚱뚱해지는데, 전이 규칙이 한곳에 모여 있는 편이 읽기 쉬워서
받아들인 트레이드오프다. 게이트가 대여섯 개를 넘으면 규칙 테이블로 분리한다.

핵심 원칙: **의도는 목적지를 제안할 뿐, 상태 게이트가 통과를 결정한다.**
조작된 `client_intent`가 들어와도 상태가 안 맞으면 못 간다(ADR 0002).
"""

from agent.intents import Intent, Node
from agent.state import ReviewState


def profile_ok(state: ReviewState) -> bool:
    """온보딩이 끝났나 — 직무와 평가 기간이 둘 다 있나."""
    raise NotImplementedError


def has_achievements(state: ReviewState) -> bool:
    """초안을 쓸 재료가 있나 — 성과가 하나라도 잡혔나."""
    raise NotImplementedError


def has_draft(state: ReviewState) -> bool:
    """확정할 대상이 있나 — 초안이 존재하나."""
    raise NotImplementedError


def is_passing_tags(tags: dict | None) -> bool:
    """5축이 전부 통과인가.

    fail-safe: 축이 누락됐거나 값이 불량이면 **미달로 정규화한다.**
    "판정 불가 = 미달"이 이 앱의 기본값이다 — 애매하면 통과시키지 않는다.

    `과장허위`는 다른 넷과 성격이 다르다. 이 축이 미달이면 나머지가 전부
    통과여도 재작성으로 되돌린다(ADR 0004의 하드 게이트).

    TODO(구현): `AXES` 전부를 순회하며 `tags.get(axis) is True`인지 확인.
    """
    raise NotImplementedError


def resolve_intent(state: ReviewState) -> Intent:
    """이번 턴의 의도를 정한다.

    `client_intent`가 있으면 그걸 쓰고(액션 칩 — LLM 분류 우회), 없으면
    마지막 사용자 발화를 LLM으로 분류한다. 분류가 애매하면 `continue`로
    떨어뜨려 진행 단계가 결정하게 한다.

    TODO(구현): 액션 칩 우선, 그다음 LLM 분류, 실패 시 `continue`.
    """
    raise NotImplementedError


def route_from_router(state: ReviewState) -> Node:
    """다음 노드를 고른다.

    계약:

    1. 온보딩이 안 끝났으면 무조건 `onboard`. 다른 의도는 전부 무시한다.
    2. `write_now`가 있고 `has_achievements`면 `draft`. 의도가 없으면 못 간다.
    3. `proceed`가 있고 `has_draft`면 `finalize`. 의도가 없으면 못 간다.
    4. `revise`는 초안이 있을 때만 `draft`로 되돌린다.
    5. `provide_info`는 `analyze`, `set_questions`는 `interview`.
    6. `continue`는 진행 단계로 판단한다 — 재료가 없으면 `interview`,
       있으면 초안을 제안하되 **넘어가지는 않는다**.
    7. 그 외(`chitchat`)는 `respond`.

    2·3번이 동의 게이트다. 여기서 의도가 없는데 넘어가면 에이전트가
    사용자를 앞지른 것이고, 그건 이 앱이 막으려는 실패다(ADR 0002).

    TODO(구현): 위 계약을 그대로. 게이트를 의도보다 먼저 확인할 것.
    """
    raise NotImplementedError
