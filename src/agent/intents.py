"""발화 의도와 그래프 노드 이름.

의도는 두 경로로 들어온다. 자유 서술은 라우터가 LLM으로 분류하고, 프론트의
액션 칩은 `client_intent`에 실어 분류를 건너뛴다. **어느 경로로 왔든 상태
게이트는 똑같이 통과해야 한다** — 신뢰 경계가 LLM이 아니라 상태에 있다(ADR 0002).
"""

from typing import Literal

Intent = Literal[
    "provide_info",  # 성과·맥락을 서술한다
    "set_questions",  # 다룰 항목을 정해준다
    "write_now",  # 지금 초안을 써달라 — 생성 동의
    "revise",  # 초안을 고쳐달라
    "proceed",  # 이대로 확정하자 — 확정 동의
    "chitchat",  # 잡담
    "continue",  # 의도가 불분명하다 — 진행 단계에 맡긴다
]

Node = Literal[
    "onboard",  # 직무·평가 기간을 받는다
    "analyze",  # 서술에서 성과 조각을 뽑는다
    "interview",  # 부족한 축을 되묻는다
    "propose_draft",  # 초안을 쓰자고 제안만 한다
    "draft",  # 초안을 쓴다
    "tag",  # 5축으로 채점한다
    "deliver",  # 채점을 통과한 초안을 내보낸다
    "finalize",  # 확정한다
    "blocked",  # 허위가 안 걷혀 초안을 막는다(ADR 0005)
    "respond",  # 그 외 — 대화만 이어간다
]

#: 채점 5축. 앞의 넷은 "더 좋게"를 재고, `과장허위`만 "넘지 마라"를 잰다(ADR 0004).
Axis = Literal["구체성", "기여도", "문제해결", "정량성", "과장허위"]

AXES: tuple[Axis, ...] = ("구체성", "기여도", "문제해결", "정량성", "과장허위")

#: 다른 넷과 성격이 달라 따로 본다. 품질 축은 상한에서 양보하지만 이 축은 안 한다.
HALLUCINATION_AXIS: Axis = "과장허위"

#: 되돌리기 비싼 전이. 이 노드로 가려면 대응하는 의도가 반드시 있어야 한다(ADR 0002).
CONSENT_REQUIRED: dict[Node, Intent] = {
    "draft": "write_now",
    "finalize": "proceed",
}

#: 재작성 상한. 도달하면 미달인 채로 내보내고, 무엇이 부족한지 함께 알린다(ADR 0003).
MAX_REVISE = 2
