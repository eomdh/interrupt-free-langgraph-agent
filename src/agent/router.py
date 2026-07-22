"""라우터 — 매 POST의 진입점.

`interrupt()`를 안 쓰기 때문에 모든 요청이 여기로 들어온다(ADR 0001).
그래서 라우터가 뚱뚱해지는데, 전이 규칙이 한곳에 모여 있는 편이 읽기 쉬워서
받아들인 트레이드오프다. 게이트가 대여섯 개를 넘으면 규칙 테이블로 분리한다.

핵심 원칙: **의도는 목적지를 제안할 뿐, 상태 게이트가 통과를 결정한다.**
조작된 `client_intent`가 들어와도 상태가 안 맞으면 못 간다(ADR 0002).
"""

from agent.intents import AXES, HALLUCINATION_AXIS, Intent, Node
from agent.state import ReviewState


def profile_ok(state: ReviewState) -> bool:
    """온보딩이 끝났나 — 직무와 평가 기간이 둘 다 있나."""
    if not state["profile"]:
        return False
    return bool(state["profile"].get("role") and state["profile"].get("period"))


def has_achievements(state: ReviewState) -> bool:
    """초안을 쓸 재료가 있나 — 성과가 하나라도 잡혔나."""
    return bool(state["achievements"])


def has_draft(state: ReviewState) -> bool:
    """확정할 대상이 있나 — 초안이 존재하나.

    빈 문자열은 초안으로 치지 않는다. 내용이 없는 걸 확정 가능한 상태로
    두면 안 된다.
    """
    return bool(state["draft"])


def is_passing_tags(tags: dict | None) -> bool:
    """5축이 전부 통과인가. 판정 불가는 미달로 본다.

    `tags`가 아니라 `AXES`를 순회한다. 모델이 축을 빠뜨리고 답해도 "없으니
    통과"가 되지 않게, 5축 전부를 기준으로 삼는다.

    값은 `is True`로만 통과시킨다. `1`이나 `"통과"` 같은 참 같은 값을
    받아주면 fail-safe가 뚫린다 — 파이썬에서 `1 == True`는 참이다.
    """
    if tags is None:
        return False
    return all(tags.get(axis) is True for axis in AXES)


def passes_hallucination_gate(tags: dict | None) -> bool:
    """과장·허위 축만 따로 본다.

    품질 축은 상한에서 미달인 채로 내보낼 수 있지만 이 축은 아니다. 그래서
    `is_passing_tags`와 별개로 물어볼 수 있어야 한다(ADR 0005).
    """
    if tags is None:
        return False
    return tags.get(HALLUCINATION_AXIS) is True


def available_actions(state: ReviewState) -> list[Intent]:
    """지금 눌러서 의미가 있는 동의 액션.

    화면은 이걸 버튼으로 그린다. **라우터가 전이를 정할 때 보는 게이트를 그대로
    본다** — 여기서 따로 판단하면 화면이 제안하는 것과 서버가 허용하는 것이
    갈라지고, 눌러도 아무 일이 없는 버튼이 생긴다.

    상태에서 유도하므로 새로고침해도 그대로 살아난다. 스트림에서 어느 노드가
    돌았는지로 알아내면 복원이 안 된다(ADR 0001의 값을 깎는다).
    """
    if not profile_ok(state):
        return []

    actions: list[Intent] = []
    if has_achievements(state) and not has_draft(state):
        actions.append("write_now")
    if has_draft(state):
        actions += ["proceed", "revise"]
    return actions


def resolve_intent(state: ReviewState) -> Intent:
    """이번 턴의 의도를 정한다.

    여기 오기 전에 `classify` 노드가 이미 채워 놨다 — 칩이 있으면 그대로 두고,
    없으면 마지막 발화를 분류해서 넣는다(ADR 0008). 그래서 이 함수는 상태만
    읽는 순수 함수로 남는다.

    비어 있으면 `continue`다. 분류가 실패했거나 모르는 라벨이 왔다는 뜻이고,
    그때는 진행 단계가 목적지를 정한다 — **덜 나아가는 쪽으로 떨어진다.**
    """
    if state["client_intent"] is not None:
        return state["client_intent"]
    return "continue"


def _progress(state: ReviewState) -> Node:
    """게이트에 막혔을 때 어디로 보낼까 — 게이트를 충족시키는 방향으로.

    `respond`로 떨구면 사용자는 왜 막혔는지 모른 채 멈춘다. 재료가 없으면
    더 캐묻고, 있으면 초안을 제안한다. 제안까지만 하고 넘어가지는 않는다.
    """
    return "propose_draft" if has_achievements(state) else "interview"


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
    """
    # 온보딩 검사가 맨 위여야 한다. 아래로 내리면 온보딩도 안 한 사용자가
    # 액션 칩으로 write_now를 보내 초안까지 뛸 수 있다.
    if not profile_ok(state):
        return "onboard"

    intent = resolve_intent(state)

    # 의도와 게이트를 둘 다 본다. 의도만 보면 재료 없이 초안을 쓰고,
    # 게이트만 보면 사용자를 앞지른다.
    if intent == "write_now":
        return "draft" if has_achievements(state) else "interview"

    if intent == "proceed":
        return "finalize" if has_draft(state) else _progress(state)

    if intent == "revise":
        return "draft" if has_draft(state) else _progress(state)

    if intent == "provide_info":
        return "analyze"

    if intent == "set_questions":
        return "interview"

    if intent == "continue":
        return _progress(state)

    return "respond"
