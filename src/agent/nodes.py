"""워커 노드.

전부 같은 규칙을 따른다: **질문이 필요하면 `AIMessage`를 남기고 그냥 끝낸다.**
`interrupt()`로 멈추지 않는다. 다음 POST가 곧 재개다(ADR 0001).

각 노드는 `make_*(llm)` 팩토리다. LLM을 인자로 받아 클로저를 돌려주므로
주입이 타입으로 드러나고, 테스트마다 다른 LLM을 넣을 수 있다.
"""

import json
from collections.abc import Awaitable, Callable

from langchain_core.messages import AIMessage, HumanMessage

from agent.intents import AXES
from agent.llm import LLM
from agent.state import ReviewState

NodeFn = Callable[[ReviewState], Awaitable[dict]]


def _last_user_text(state: ReviewState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            return str(message.content)
    return ""


def _strip_fence(raw: str) -> str:
    """```json 펜스를 벗긴다.

    "JSON으로만 답하라"고 해도 마크다운으로 감싸는 모델이 많다. 모델을
    갈아끼울 수 있는 설계(`OPENAI_BASE_URL`)라 특정 모델의 습관에 기대지 않는다.
    """
    text = raw.strip()
    if not text.startswith("```"):
        return text
    body = text.removeprefix("```")
    _, _, body = body.partition("\n")  # ```json 같은 언어 태그 줄을 버린다
    return body.removesuffix("```").strip()


def _loads(raw: str, default):
    """LLM 출력을 JSON으로 읽는다. 타입이 안 맞아도 기본값으로 떨어진다.

    모델이 스키마를 지킨다는 보장이 없다. 파싱은 실패할 수 있는 일로 다룬다.
    """
    try:
        value = json.loads(_strip_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return default
    return value if isinstance(value, type(default)) else default


def _shortfalls(tags: dict | None) -> list[str]:
    """미달인 축. 판정이 없으면 전 축이 미달이다."""
    if not tags:
        return list(AXES)
    return [axis for axis in AXES if tags.get(axis) is not True]


_ONBOARD = """다음 대화에서 사용자의 직무와 평가 기간을 뽑아라.
JSON으로만 답하라: {{"role": "...", "period": "..."}}
찾을 수 없으면 빈 문자열로 둔다.

대화: {text}"""


def make_onboard(llm: LLM) -> NodeFn:
    async def onboard(state: ReviewState) -> dict:
        raw = await llm.complete(_ONBOARD.format(text=_last_user_text(state)), task="onboard")
        found = _loads(raw, {})

        profile = dict(state["profile"])
        for key in ("role", "period"):
            if found.get(key):
                profile[key] = found[key]

        missing = [
            label for key, label in (("role", "직무"), ("period", "평가 기간")) if not profile.get(key)
        ]
        if missing:
            reply = f"{' · '.join(missing)}를 알려주세요."
        else:
            reply = "좋습니다. 이번 기간에 한 일을 편하게 말씀해주세요."

        return {"profile": profile, "messages": [AIMessage(reply)]}

    return onboard


_ANALYZE = """다음 서술에서 성과를 STAR로 쪼개라.
JSON 배열로만 답하라: [{{"title": "", "situation": "", "task": "", "action": "", "result": ""}}]
성과로 볼 게 없으면 빈 배열.

서술: {text}"""


def make_analyze(llm: LLM) -> NodeFn:
    async def analyze(state: ReviewState) -> dict:
        raw = await llm.complete(_ANALYZE.format(text=_last_user_text(state)), task="analyze")
        items = [item for item in _loads(raw, []) if isinstance(item, dict)]

        if not items:
            reply = "성과로 잡을 만한 게 아직 안 보여요. 조금 더 구체적으로 말씀해주시겠어요?"
            return {"messages": [AIMessage(reply)]}

        titles = " · ".join(str(item.get("title", "제목 없음")) for item in items)
        return {
            "achievements": items,
            "messages": [AIMessage(f"정리했습니다 — {titles}. 더 있으면 말씀해주세요.")],
        }

    return analyze


_INTERVIEW = """성과 리뷰를 쓰기 위해 사용자에게 물을 질문을 하나만 만들어라.
이미 나온 성과: {achievements}
아직 약한 축: {weak}
질문 한 문장만 출력하라."""


def make_interview(llm: LLM) -> NodeFn:
    async def interview(state: ReviewState) -> dict:
        question = await llm.complete(
            _INTERVIEW.format(
                achievements=json.dumps(state["achievements"], ensure_ascii=False),
                weak=" · ".join(_shortfalls(state["tags"])),
            ),
            task="interview",
        )
        return {"messages": [AIMessage(question.strip())]}

    return interview


def make_propose_draft(llm: LLM) -> NodeFn:
    """초안을 쓰자고 제안만 한다. 여기서 넘어가지 않는다(ADR 0002).

    LLM을 쓰지 않는다. 동의를 구하는 문구는 매번 같아야 사용자가 같은
    약속으로 읽는다.
    """

    async def propose_draft(state: ReviewState) -> dict:
        count = len(state["achievements"])
        reply = f"성과 {count}건이 모였습니다. 이대로 초안을 써볼까요?"
        return {"messages": [AIMessage(reply)]}

    return propose_draft


_DRAFT = """아래 재료로 성과 리뷰 초안을 써라.
직무: {role} / 기간: {period}
성과: {achievements}
{hint}

규칙:
- 주어진 성과에 없는 사실을 쓰지 마라. 협업·교육·모니터링·배포처럼 그럴듯한
  내용이라도 재료에 없으면 넣지 않는다.
- 재료가 빈약하면 짧게 써라. 분량을 채우려고 지어내지 마라.
- 수치는 재료에 있는 것만 쓴다.

출력 형식:
- 사람이 인사 시스템에 그대로 붙여넣을 본문만 낸다.
- 규칙을 지켰다는 보고, 자기 평가, 머리말·맺음말을 쓰지 마라.
- STAR 항목 이름(상황/업무/실행/결과)을 소제목으로 노출하지 말고 산문으로 녹여라."""


def make_draft(llm: LLM) -> NodeFn:
    async def draft(state: ReviewState) -> dict:
        rewriting = bool(state["draft"])
        weak = _shortfalls(state["tags"]) if rewriting else []

        # 통과한 축은 건드리지 않는다. 전체를 다시 쓰면 통과했던 축이
        # 무너진다(ADR 0003).
        hint = f"다음 축이 부족하다. 그 부분만 보강하라: {' · '.join(weak)}" if weak else ""

        text = await llm.complete(
            _DRAFT.format(
                role=state["profile"].get("role", ""),
                period=state["profile"].get("period", ""),
                achievements=json.dumps(state["achievements"], ensure_ascii=False),
                hint=hint,
            ),
            task="draft",
            temperature=0.4,  # 생성은 어휘 다양성이 필요하다
        )

        return {
            "draft": text.strip(),
            # 첫 초안은 재작성이 아니다. None으로 카운터를 0으로 되돌린다.
            "revise_count": 1 if rewriting else None,
        }

    return draft


_TAG = """아래 초안을 5축으로 채점하라. **true = 통과, false = 미달**이다.

- 구체성: 무엇을 했는지 두루뭉술하지 않고 구체적이다
- 기여도: 본인이 한 일이 드러난다
- 문제해결: 어떤 문제를 어떻게 풀었는지 보인다
- 정량성: 수치나 규모가 들어 있다
- 과장허위: **초안의 모든 문장이 입력 성과로 뒷받침된다**
  (입력에 없는 내용이 하나라도 있으면 false)

JSON 객체로만 답하라. 예: {{"구체성": true, "기여도": true, "문제해결": true, "정량성": false, "과장허위": true}}

입력 성과: {achievements}
초안: {draft}"""


def make_tag(llm: LLM) -> NodeFn:
    async def tag(state: ReviewState) -> dict:
        raw = await llm.complete(
            _TAG.format(
                achievements=json.dumps(state["achievements"], ensure_ascii=False),
                draft=state["draft"],
            ),
            task="tag",
            temperature=0.0,  # 채점은 같은 입력에 같은 답이 나와야 한다
        )
        parsed = _loads(raw, {})

        # 축마다 따로 정규화한다. 스키마 전체를 거부하면 멀쩡한 축까지
        # 버리게 되고, 여기서 필요한 건 "판정 불가는 미달"이다.
        return {"tags": {axis: parsed.get(axis) is True for axis in AXES}}

    return tag


def make_deliver(llm: LLM) -> NodeFn:
    """채점을 통과한 초안을 내보낸다.

    `draft`가 직접 안 내보내는 이유 — 채점 전에 보여주면 허위가 걸린 초안도
    이미 사용자 눈에 들어간다. 그러면 막아봐야 늦다(ADR 0005).
    """

    async def deliver(state: ReviewState) -> dict:
        weak = _shortfalls(state["tags"])
        # 상한에 걸려 미달인 채로 나가는 경우. 조용히 통과시키지 않는다(ADR 0003).
        note = f"\n\n(아직 약한 부분: {' · '.join(weak)})" if weak else ""
        return {"messages": [AIMessage(f"{state['draft']}{note}\n\n이대로 확정할까요?")]}

    return deliver


def make_finalize(llm: LLM) -> NodeFn:
    async def finalize(state: ReviewState) -> dict:
        return {"messages": [AIMessage(f"확정했습니다.\n\n{state['draft']}")]}

    return finalize


_BLOCKED = """아래 초안에서 입력 성과에 근거가 없는 문장을 찾아 나열하라.
근거 없는 문장만 줄바꿈으로 나열하고, 없으면 빈 줄을 출력하라.

입력 성과: {achievements}
초안: {draft}"""


def make_blocked(llm: LLM) -> NodeFn:
    """허위가 안 걷혀 초안을 막는다(ADR 0005).

    무엇을 채우면 되는지 못 짚어주면 그냥 막다른 길이 된다. 그래서 어느
    문장이 문제였는지를 같이 돌려준다.
    """

    async def blocked(state: ReviewState) -> dict:
        unverified = await llm.complete(
            _BLOCKED.format(
                achievements=json.dumps(state["achievements"], ensure_ascii=False),
                draft=state["draft"],
            ),
            task="blocked",
        )
        reply = (
            "근거를 확인하지 못한 내용이 남아 있어 초안을 내보내지 않았습니다.\n\n"
            f"{unverified.strip()}\n\n"
            "실제로 있었던 일이라면 구체적으로 알려주세요. 반영해서 다시 쓰겠습니다."
        )
        return {"messages": [AIMessage(reply)]}

    return blocked


_RESPOND = """성과 리뷰 작성을 돕는 중이다. 사용자에게 짧게 답하라.

사용자: {text}"""


def make_respond(llm: LLM) -> NodeFn:
    async def respond(state: ReviewState) -> dict:
        reply = await llm.complete(
            _RESPOND.format(text=_last_user_text(state)), task="respond", temperature=0.4
        )
        return {"messages": [AIMessage(reply.strip())]}

    return respond
