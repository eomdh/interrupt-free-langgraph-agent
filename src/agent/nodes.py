"""워커 노드.

전부 같은 규칙을 따른다: **질문이 필요하면 `AIMessage`를 남기고 그냥 끝낸다.**
`interrupt()`로 멈추지 않는다. 다음 POST가 곧 재개다(ADR 0001).
"""

from agent.state import ReviewState


async def onboard(state: ReviewState) -> dict:
    """직무와 평가 기간을 받는다. 둘 중 하나라도 없으면 물어보고 끝낸다."""
    raise NotImplementedError


async def analyze(state: ReviewState) -> dict:
    """사용자 서술에서 성과 조각(STAR)을 뽑아 `achievements`에 더한다."""
    raise NotImplementedError


async def interview(state: ReviewState) -> dict:
    """부족한 축을 되묻는다.

    초안 품질의 상한이 여기서 정해진다. RAG가 없어서 외부 지식으로 메울
    수단이 없기 때문에(ADR 0004), 잘 캐묻는 것만이 유일한 보강 경로다.
    """
    raise NotImplementedError


async def propose_draft(state: ReviewState) -> dict:
    """초안을 쓸 준비가 됐다고 **제안만** 한다.

    여기서 `draft`로 넘어가지 않는다. "이제 초안을 써볼까요?"를 남기고 끝내면,
    사용자가 다음 POST에서 승인해야 진행된다(ADR 0002).
    """
    raise NotImplementedError


async def draft(state: ReviewState) -> dict:
    """초안을 쓴다.

    재작성으로 들어온 경우 `tags`에서 **미달인 축만** 힌트로 받는다. 전체를
    다시 쓰면 통과했던 축이 무너진다(ADR 0003).

    temperature 0.4 — 생성은 어휘 다양성이 필요하다.
    """
    raise NotImplementedError


async def tag(state: ReviewState) -> dict:
    """초안을 5축으로 채점한다.

    temperature 0 — 채점은 같은 입력에 같은 답이 나와야 한다.
    파싱에 실패한 축은 전부 미달로 정규화한다(`is_passing_tags` 참조).
    """
    raise NotImplementedError


async def finalize(state: ReviewState) -> dict:
    """확정한다. 상한에 걸려 미달인 채로 왔다면 **무엇이 부족한지 함께 알린다.**"""
    raise NotImplementedError


async def blocked(state: ReviewState) -> dict:
    """허위가 안 걷혀 초안을 막는다(ADR 0005).

    초안 대신 **어느 문장의 근거를 확인 못 했는지**를 돌려주고, 그 부분을
    사용자가 채우도록 유도한다. 결과물이 없는 채로 끝나는 게 허위가 섞인
    결과물보다 낫다.
    """
    raise NotImplementedError


async def respond(state: ReviewState) -> dict:
    """잡담 등 — 대화만 이어간다."""
    raise NotImplementedError
