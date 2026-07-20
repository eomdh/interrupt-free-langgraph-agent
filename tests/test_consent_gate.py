"""동의 게이트 — 에이전트가 사용자를 앞지르지 못하는가(ADR 0002).

되돌리기 비싼 두 전이(생성·확정)를 의도 없이 넘어가면 실패다.
"""

from agent.router import route_from_router

ACHIEVEMENT = {"title": "결제 지연 개선", "result": "p95 1.2s → 340ms"}


def test_재료가_충분해도_write_now가_없으면_draft로_안_간다(onboarded):
    """이게 이 앱이 막으려는 실패다 — 준비됐다고 에이전트가 먼저 쓰는 것."""
    state = onboarded(client_intent="provide_info", achievements=[ACHIEVEMENT])
    assert route_from_router(state) != "draft"


def test_write_now와_재료가_둘_다_있어야_draft(onboarded):
    state = onboarded(client_intent="write_now", achievements=[ACHIEVEMENT])
    assert route_from_router(state) == "draft"


def test_write_now가_있어도_재료가_없으면_draft로_안_간다(onboarded):
    """의도만으로는 못 간다. 상태 게이트가 별도로 걸린다."""
    state = onboarded(client_intent="write_now", achievements=[])
    assert route_from_router(state) != "draft"


def test_초안이_있어도_proceed가_없으면_finalize로_안_간다(onboarded):
    state = onboarded(client_intent="provide_info", draft="초안 본문")
    assert route_from_router(state) != "finalize"


def test_proceed와_초안이_둘_다_있어야_finalize(onboarded):
    state = onboarded(client_intent="proceed", draft="초안 본문")
    assert route_from_router(state) == "finalize"


def test_조작된_client_intent도_상태_게이트를_못_뚫는다(onboarded):
    """액션 칩은 LLM 분류를 건너뛸 뿐, 게이트를 건너뛰지 않는다.

    API를 직접 때려 proceed를 보내도 초안이 없으면 확정될 수 없다 —
    신뢰 경계가 LLM이 아니라 상태에 있다는 뜻이다.
    """
    state = onboarded(client_intent="proceed", draft=None)
    assert route_from_router(state) != "finalize"


# --- 막혔을 때 어디로 가나 ---
#
# 위 테스트들은 "거기로 가면 안 된다"만 본다. 막힌 사용자를 어디로 보낼지는
# 별개 판단이고, 여기서 못 박는다. 원칙은 "게이트를 충족시키는 방향" —
# respond로 떨구면 사용자는 왜 막혔는지 모른 채 멈춘다.


def test_재료가_없어서_막히면_더_캐묻는다(onboarded):
    state = onboarded(client_intent="write_now", achievements=[])
    assert route_from_router(state) == "interview"


def test_초안이_없는데_proceed면_재료를_보고_제안한다(onboarded):
    state = onboarded(client_intent="proceed", draft=None, achievements=[ACHIEVEMENT])
    assert route_from_router(state) == "propose_draft"


def test_초안도_재료도_없는데_proceed면_캐묻는다(onboarded):
    state = onboarded(client_intent="proceed", draft=None, achievements=[])
    assert route_from_router(state) == "interview"


def test_초안이_없는데_revise면_제안으로_되돌린다(onboarded):
    state = onboarded(client_intent="revise", draft=None, achievements=[ACHIEVEMENT])
    assert route_from_router(state) == "propose_draft"
