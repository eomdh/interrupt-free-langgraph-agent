"""라우터 전이 — 의도 × 상태 게이트가 어느 노드로 가는가."""

import pytest

from agent.router import available_actions, route_from_router


def test_온보딩_전에는_무슨_의도가_와도_onboard(make_state):
    """직무·기간이 없으면 다른 의도는 전부 무시된다."""
    for intent in ("provide_info", "write_now", "proceed", "chitchat"):
        state = make_state(client_intent=intent)
        assert route_from_router(state) == "onboard"


def test_직무만_있고_기간이_없으면_아직_onboard(make_state):
    state = make_state(profile={"role": "백엔드 엔지니어"}, client_intent="provide_info")
    assert route_from_router(state) == "onboard"


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ("provide_info", "analyze"),
        ("set_questions", "interview"),
        ("chitchat", "respond"),
    ],
)
def test_온보딩_후_의도별_목적지(onboarded, intent, expected):
    assert route_from_router(onboarded(client_intent=intent)) == expected


def test_continue는_재료가_없으면_interview로(onboarded):
    """의도가 불분명하면 진행 단계가 결정한다 — 아직 성과가 없으니 더 캐묻는다."""
    state = onboarded(client_intent="continue", achievements=[])
    assert route_from_router(state) == "interview"


def test_continue는_재료가_있어도_초안으로_넘어가지_않는다(onboarded):
    """제안까지만 한다. 넘어가려면 write_now가 필요하다(ADR 0002)."""
    state = onboarded(client_intent="continue", achievements=[{"title": "결제 지연 개선"}])
    assert route_from_router(state) == "propose_draft"


def test_revise는_초안이_있을_때만_draft로_되돌린다(onboarded):
    state = onboarded(client_intent="revise", draft="초안 본문")
    assert route_from_router(state) == "draft"


def test_초안이_없는데_revise면_draft로_가지_않는다(onboarded):
    state = onboarded(client_intent="revise", draft=None)
    assert route_from_router(state) != "draft"


def test_온보딩_전에는_누를_수_있는_동의가_없다(make_state):
    assert available_actions(make_state()) == []


def test_재료가_모이면_초안_생성을_제안한다(onboarded):
    state = onboarded(achievements=[{"title": "결제 지연 개선"}])
    assert available_actions(state) == ["write_now"]


def test_초안이_나오면_확정과_재작성이_열린다(onboarded):
    """이미 초안이 있으면 다시 생성하자는 제안은 안 한다 — 그건 재작성이다."""
    state = onboarded(achievements=[{"title": "결제 지연 개선"}], draft="초안 본문")
    assert available_actions(state) == ["proceed", "revise"]


@pytest.mark.parametrize(
    "state_kwargs",
    [
        {"achievements": [{"title": "결제 지연 개선"}]},
        {"achievements": [{"title": "결제 지연 개선"}], "draft": "초안 본문"},
    ],
)
def test_제안한_동의는_라우터가_실제로_받아준다(onboarded, state_kwargs):
    """눌러도 아무 일이 없는 버튼이 생기면 안 된다.

    화면이 제안하는 것과 서버가 허용하는 것이 갈라지는 순간 사용자는 앱을
    못 믿는다. 그래서 제안은 라우터가 보는 게이트에서 유도한다.
    """
    state = onboarded(**state_kwargs)

    for intent in available_actions(state):
        target = route_from_router({**state, "client_intent": intent})
        assert target in ("draft", "finalize"), f"{intent} → {target}"
