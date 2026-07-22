"""HTTP 경계.

**POST 한 번 = 그래프 실행 한 번 = 대화 한 턴.** 멈춰 있는 그래프를 들고
있지 않으므로 앱은 무상태다 — 재시작해도 대화가 안 깨진다. 상태는 전부
체크포인터에 있다(ADR 0001).

무상태는 **지속성**을 주지 동시성 안전을 주지는 않는다. 같은 스레드의 동시 턴은
인스턴스 안에서 락으로 직렬화하고, 여러 인스턴스로 늘리는 것은 범위 밖이다.

`GET /threads/{id}`가 그 설계의 값을 그대로 보여준다. 복원 로직이 따로 없다.
질문이 특수 상태가 아니라 그냥 메시지라, 대화를 읽으면 그게 곧 화면이다.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agent.intents import Intent
from agent.router import available_actions
from agent.state import new_thread_state
from agent.stream import HIDDEN_NODES, project_update, sse_frame

logger = logging.getLogger(__name__)


class TurnRequest(BaseModel):
    """한 턴의 입력.

    `client_intent`는 생략해도 `None`으로 채워진다. 그게 요점이다 — 매 턴
    반드시 덮이므로 지난 턴의 액션 칩이 게이트를 다시 열 수 없다.
    """

    # 상한이 없으면 프롬프트가 통째로 부풀고 토큰 비용이 요청 하나로 폭주한다.
    text: str = Field(min_length=1, max_length=4000)
    client_intent: Intent | None = None


class MessageView(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ThreadView(BaseModel):
    """스레드의 현재 모습.

    **초안 본문을 따로 내려주지 않는다.** 초안은 `deliver`가 메시지로 내보낼
    때만 사용자에게 도달해야 한다. 여기서 `draft`를 노출하면 `blocked`로 막은
    초안까지 클라이언트가 읽을 수 있어 ADR 0005가 무의미해진다.
    """

    thread_id: str
    messages: list[MessageView]
    tags: dict[str, bool] | None = None

    #: 지금 눌러서 의미가 있는 동의 액션. 화면이 이걸 버튼으로 그린다.
    #: 상태에서 유도하므로 새로고침해도 살아나고, 초안 본문은 여전히 안 실린다.
    actions: list[Intent] = Field(default_factory=list)


def _view(thread_id: str, values: dict) -> ThreadView:
    return ThreadView(
        thread_id=thread_id,
        messages=[
            MessageView(
                role="user" if isinstance(message, HumanMessage) else "assistant",
                content=str(message.content),
            )
            for message in values["messages"]
        ],
        tags=values.get("tags"),
        actions=available_actions(values),
    )


async def _seeded_payload(graph, config: dict, body: TurnRequest) -> dict:
    """이번 턴 입력을 만든다. 첫 턴이면 초기 상태를 먼저 깐다.

    JSON 턴과 스트림 턴이 **같은 준비를 쓰도록** 한곳에 둔다. 여기가 갈라지면
    두 경로가 다른 상태에서 시작해, 스트림으로 연 스레드와 POST로 연 스레드가
    미묘하게 달라진다.

    LangGraph는 안 넘긴 키를 아예 만들지 않으므로(`state.py`), 새 스레드는
    전 필드를 채워 넣어야 라우터의 직접 인덱싱이 `KeyError`를 안 낸다.
    """
    payload = {
        "messages": [HumanMessage(body.text)],
        "client_intent": body.client_intent,
    }
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        payload = new_thread_state() | payload
    return payload


def create_app(graph=None, lifespan=None, static_dir: Path | None = None) -> FastAPI:
    """앱을 만든다.

    그래프를 인자로 받으면 그대로 쓰고(테스트), 없으면 `lifespan`이 기동 시
    `app.state.graph`에 넣어준다(운영 — Postgres 연결이 필요하다).
    """
    app = FastAPI(title="성과 리뷰 초안 코치", lifespan=lifespan)
    app.state.graph = graph

    # 스레드마다 락 하나. 같은 스레드의 턴을 직렬화한다 — `_seeded_payload`의
    # `aget_state`와 `ainvoke` 사이가 TOCTOU라, 동시에 들어오면 한쪽 턴의 응답이
    # 통째로 사라진다. 같은 브라우저의 두 탭이면 바로 재현된다.
    #
    # **이건 인스턴스 안에서만 유효하다.** 여러 대로 늘리면 Postgres advisory
    # lock 같은 것이 필요하고, 그건 범위 밖이다(plan.md).
    #
    # dict는 본 스레드 수만큼 자란다. 데모 규모에서는 문제가 아니지만, 오래 도는
    # 서버라면 TTL 캐시로 바꿔야 한다 — 지금 그렇게 안 한 것은 알고 남긴 빚이다.
    locks: dict[str, asyncio.Lock] = {}

    def _turn_lock(thread_id: str) -> asyncio.Lock:
        lock = locks.get(thread_id)
        if lock is None:
            lock = locks[thread_id] = asyncio.Lock()
        return lock

    def _config(thread_id: str) -> dict:
        # `recursion_limit`은 심층 방어다. 루프 종료는 `MAX_REVISE`가 책임지지만,
        # 그 논리가 틀리면 LangGraph 기본값(10007)까지 도는 동안 LLM 호출이
        # 수천 번 나간다 — 한 번의 POST로. 구조적 상한을 여기서도 못 박는다.
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 12}

    @app.post("/threads/{thread_id}/turns", response_model=ThreadView)
    async def take_turn(thread_id: str, body: TurnRequest, request: Request) -> ThreadView:
        graph = request.app.state.graph
        config = _config(thread_id)

        # 시딩 판정과 실행이 한 임계구역 안에 있어야 한다. 밖에 두면 둘 다
        # "새 스레드"로 읽고 서로의 턴을 덮는다.
        async with _turn_lock(thread_id):
            payload = await _seeded_payload(graph, config, body)
            values = await graph.ainvoke(payload, config)

        return _view(thread_id, values)

    @app.post("/threads/{thread_id}/turns/stream")
    async def take_turn_stream(
        thread_id: str, body: TurnRequest, request: Request
    ) -> StreamingResponse:
        """POST 한 번을 스트리밍으로. 노드를 밟는 과정을 흘리고 END에서 닫는다.

        JSON 엔드포인트와 **같은 한 턴**이다 — 결과도 같다. 다만 그 사이의 노드
        전환을 SSE로 중계한다. 진행 이벤트는 메타데이터만 싣고(`stream.py`),
        초안 본문은 최종 `done`의 `ThreadView`로만 나간다(ADR 0005·0006).

        스트림이 시작되면 상태 코드를 못 바꾸므로, 실행 중 오류는 `error`
        이벤트로 내보낸다. 연결을 매단 채로 두지 않는다.
        """
        graph = request.app.state.graph
        config = _config(thread_id)

        async def events() -> AsyncIterator[str]:
            seq = 0
            attempt = 0
            try:
                # 락은 스트림이 끝날 때까지 잡고 있어야 한다. 시딩만 감싸면
                # 실행 도중 다른 턴이 끼어든다.
                async with _turn_lock(thread_id):
                    payload = await _seeded_payload(graph, config, body)
                    async for chunk in graph.astream(payload, config, stream_mode="updates"):
                        for node, delta in chunk.items():
                            # 내부 단계는 진행이 아니다. seq를 올리기 전에 걸러서
                            # 클라이언트가 보는 순번이 이어지게 둔다.
                            if node in HIDDEN_NODES:
                                continue
                            seq += 1
                            if node == "draft":
                                attempt += 1
                            yield project_update(node, delta or {}, seq=seq, attempt=attempt)

                    snapshot = await graph.aget_state(config)

                yield sse_frame("done", _view(thread_id, snapshot.values).model_dump())
            except Exception:  # noqa: BLE001 — 스트림 중 오류는 삼키지 말고 이벤트로
                # 예외 문자열을 그대로 내보내면 안 된다. `LLMError`는 업스트림
                # 응답 본문 일부를 담고, 체크포인터 실패는 내부 호스트·DB 사용자를
                # 담는다 — 인증 없는 클라이언트가 그걸 읽는다.
                # 사용자에겐 고정 문구와 참조 번호만, 상세는 서버 로그로.
                ref = uuid4().hex[:8]
                logger.exception("턴 실행 실패 (ref=%s, thread=%s)", ref, thread_id)
                yield sse_frame("error", {"detail": f"요청을 끝내지 못했습니다 (ref: {ref})"})

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/threads/{thread_id}", response_model=ThreadView)
    async def read_thread(thread_id: str, request: Request) -> ThreadView:
        snapshot = await request.app.state.graph.aget_state(_config(thread_id))
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="없는 스레드")
        return _view(thread_id, snapshot.values)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # 빌드된 프론트를 같은 오리진에서 서빙한다 — 그래서 CORS 가 없다.
    #
    # **마운트는 맨 마지막이어야 한다.** Starlette 는 등록 순서로 매칭하므로,
    # "/" 를 먼저 걸면 위의 /threads·/health 까지 정적 핸들러가 삼킨다.
    #
    # 없으면 그냥 안 붙는다. 개발 중에는 Vite 가 프론트를 서빙하고 이 앱은
    # API 만 내주면 된다.
    if static_dir is not None and static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")

    return app
