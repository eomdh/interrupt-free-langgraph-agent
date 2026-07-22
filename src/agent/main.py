"""운영 기동점 — `uvicorn agent.main:app`.

`LLM_MODE`가 두 갈래를 가른다. 기본값 `fake`는 키 없이 흐름과 복원을
확인하는 경로이고(관리 규약 §8.2), `openai`는 실제 모델을 부른다.
목 모드는 임시방편이 아니라 **클론한 사람이 밟는 기본 경로**다.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.api import create_app
from agent.graph import build_graph
from agent.llm import LLM, FakeLLM, OpenAICompatibleLLM
from agent.settings import Settings

settings = Settings()

DEMO_RESPONSES = {
    # 목은 입력과 무관하게 같은 답을 준다 — 즉 **목 모드에서는 의도 분류가
    # 동작하지 않는다.** `continue`로 두어 분류가 없던 때와 같게 만든다.
    # 목 모드에서 초안·확정으로 넘어가려면 액션 칩을 쓰면 된다.
    "classify": "continue",
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


def build_llm() -> LLM:
    """설정이 고른 LLM. 검증은 `Settings`가 기동 시점에 이미 끝냈다."""
    if settings.llm_mode == "fake":
        return FakeLLM(DEMO_RESPONSES)
    return OpenAICompatibleLLM(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Postgres 체크포인터를 열고 그래프를 조립한다.

    `setup()`이 체크포인트 테이블을 만든다. 이미 있으면 그냥 지나간다.
    """
    llm = build_llm()
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_graph(llm, checkpointer)
        try:
            yield
        finally:
            if isinstance(llm, OpenAICompatibleLLM):
                await llm.aclose()


app = create_app(lifespan=lifespan, static_dir=settings.web_dist)
