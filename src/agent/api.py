"""HTTP 경계.

**POST 한 번 = 그래프 실행 한 번 = 대화 한 턴.** 멈춰 있는 그래프를 들고
있지 않으므로 앱은 무상태다 — 재시작해도, 인스턴스를 늘려도 대화가 안 깨진다.
상태는 전부 체크포인터에 있다(ADR 0001).

`GET /threads/{id}`가 그 설계의 값을 그대로 보여준다. 복원 로직이 따로 없다.
질문이 특수 상태가 아니라 그냥 메시지라, 대화를 읽으면 그게 곧 화면이다.
"""

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agent.intents import Intent
from agent.state import new_thread_state


class TurnRequest(BaseModel):
    """한 턴의 입력.

    `client_intent`는 생략해도 `None`으로 채워진다. 그게 요점이다 — 매 턴
    반드시 덮이므로 지난 턴의 액션 칩이 게이트를 다시 열 수 없다.
    """

    text: str = Field(min_length=1)
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


def create_app(graph=None, lifespan=None) -> FastAPI:
    """앱을 만든다.

    그래프를 인자로 받으면 그대로 쓰고(테스트), 없으면 `lifespan`이 기동 시
    `app.state.graph`에 넣어준다(운영 — Postgres 연결이 필요하다).
    """
    app = FastAPI(title="성과 리뷰 초안 코치", lifespan=lifespan)
    app.state.graph = graph

    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    @app.post("/threads/{thread_id}/turns", response_model=ThreadView)
    async def take_turn(thread_id: str, body: TurnRequest, request: Request) -> ThreadView:
        graph = request.app.state.graph
        config = _config(thread_id)
        payload = await _seeded_payload(graph, config, body)
        values = await graph.ainvoke(payload, config)
        return _view(thread_id, values)

    @app.get("/threads/{thread_id}", response_model=ThreadView)
    async def read_thread(thread_id: str, request: Request) -> ThreadView:
        snapshot = await request.app.state.graph.aget_state(_config(thread_id))
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="없는 스레드")
        return _view(thread_id, snapshot.values)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
