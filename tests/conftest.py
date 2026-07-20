import pytest

from agent.state import ReviewState


@pytest.fixture
def make_state():
    """빈 상태에서 시작해 필요한 필드만 덮어쓰는 팩토리."""

    def _make(**overrides) -> ReviewState:
        state: ReviewState = {
            "messages": [],
            "profile": {},
            "achievements": [],
            "draft": None,
            "tags": None,
            "revise_count": 0,
            "client_intent": None,
        }
        state.update(overrides)  # type: ignore[typeddict-item]
        return state

    return _make


@pytest.fixture
def onboarded(make_state):
    """온보딩이 끝난 상태 — 게이트 테스트의 출발점."""

    def _make(**overrides) -> ReviewState:
        return make_state(
            profile={"role": "백엔드 엔지니어", "period": "2026 상반기"},
            **overrides,
        )

    return _make


@pytest.fixture
def passing() -> dict:
    """5축 전부 통과인 채점 결과."""
    return {
        "구체성": True,
        "기여도": True,
        "문제해결": True,
        "정량성": True,
        "과장허위": True,
    }
