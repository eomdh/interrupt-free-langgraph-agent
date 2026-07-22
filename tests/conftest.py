import json

import pytest

from agent.intents import AXES
from agent.llm import FakeLLM
from agent.state import ReviewState

ACHIEVEMENT = {
    "title": "결제 지연 개선",
    "situation": "피크 시간대 결제 p95가 1.2초였다",
    "task": "지연을 줄인다",
    "action": "N+1 조회를 배치로 묶고 인덱스를 다시 잡았다",
    "result": "p95 340ms",
}


@pytest.fixture
def tags_json():
    """5축 채점 결과를 LLM 출력 모양(JSON 문자열)으로."""

    def _make(**overrides) -> str:
        scored = {axis: True for axis in AXES} | overrides
        return json.dumps(scored, ensure_ascii=False)

    return _make


@pytest.fixture
def make_llm(tags_json):
    """전 구간을 돌리기에 충분한 목. 축별 판정만 갈아끼우면 분기가 바뀐다."""

    def _make(**overrides) -> FakeLLM:
        responses = {
            # 목은 고정 응답이라 진짜 분류를 못 한다. `continue`로 두면 분류가
            # 없던 때와 같은 흐름이 되고, 칩을 넘긴 턴은 분류를 아예 건너뛴다.
            # 분류 자체의 판단은 `test_classify.py`에서 따로 때린다.
            "classify": "continue",
            "onboard": json.dumps({"role": "백엔드 엔지니어", "period": "2026 상반기"}),
            "analyze": json.dumps([ACHIEVEMENT], ensure_ascii=False),
            "interview": "그 수치는 어떻게 측정했나요?",
            "draft": "2026 상반기에 결제 지연을 개선했다. p95를 1.2초에서 340ms로 줄였다.",
            "tag": tags_json(),
            "blocked": "매출 30% 증가",
            "respond": "네, 편하게 말씀해주세요.",
        }
        return FakeLLM(responses | overrides)

    return _make


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
