"""운영 기동점 — `uvicorn agent.main:app`.

지금은 **데모 모드로만 뜬다.** 실제 LLM 클라이언트는 아직 없고, 정해진
응답을 돌려주는 목이 그 자리를 채운다. 그래도 이 앱이 증명하려는 것 —
POST 한 번이 한 턴이고, 상태는 Postgres에만 있고, 재시작해도 대화가
남는다 — 는 그대로 확인된다.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.api import create_app
from agent.graph import build_graph
from agent.llm import FakeLLM
from agent.settings import Settings

settings = Settings()

DEMO_RESPONSES = {
    "onboard": '{"role": "백엔드 엔지니어", "period": "2026 상반기"}',
    "analyze": (
        '[{"title": "결제 지연 개선", "situation": "피크 시간대 결제 p95가 1.2초였다",'
        ' "task": "지연을 줄인다", "action": "N+1 조회를 배치로 묶고 인덱스를 다시 잡았다",'
        ' "result": "p95 340ms"}]'
    ),
    "interview": "그 수치는 어떻게 측정했나요?",
    "draft": "2026 상반기에는 결제 지연 개선을 맡았다. p95를 1.2초에서 340ms로 줄였다.",
    "tag": '{"구체성": true, "기여도": true, "문제해결": true, "정량성": true, "과장허위": true}',
    "blocked": "근거를 찾지 못한 문장",
    "respond": "네, 편하게 말씀해주세요.",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Postgres 체크포인터를 열고 그래프를 조립한다.

    `setup()`이 체크포인트 테이블을 만든다. 이미 있으면 그냥 지나간다.
    """
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_graph(FakeLLM(DEMO_RESPONSES), checkpointer)
        yield


app = create_app(lifespan=lifespan)
