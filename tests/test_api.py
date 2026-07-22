"""HTTP 경계 — POST 한 번이 한 턴이고, GET 하면 대화가 그대로 있다.

체크포인터는 `MemorySaver`를 쓴다. 운영은 Postgres지만(`agent.main`), 여기서
검증하는 건 **저장소 종류가 아니라 앱이 무상태라는 것**이다. 요청 사이에
아무것도 안 들고 있어야 GET이 저장소만 보고 대화를 복원할 수 있다.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from agent.api import create_app
from agent.graph import build_graph


@pytest.fixture
def client(make_llm):
    checkpointer = MemorySaver()
    app = create_app(build_graph(make_llm(), checkpointer))
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def blocked_client(make_llm, tags_json):
    """허위가 안 걷히는 목 — 초안이 막히는 경로."""
    app = create_app(build_graph(make_llm(tag=tags_json(과장허위=False)), MemorySaver()))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _turn(client, thread: str, text: str, intent: str | None = None) -> dict:
    body: dict = {"text": text}
    if intent is not None:
        body["client_intent"] = intent
    response = await client.post(f"/threads/{thread}/turns", json=body)
    assert response.status_code == 200, response.text
    return response.json()


async def test_첫_POST가_스레드를_연다(client):
    async with client:
        body = await _turn(client, "t1", "성과 리뷰 써야 해")

    assert body["thread_id"] == "t1"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]


async def test_GET이_대화를_그대로_복원한다(client):
    """복원 코드가 따로 없다. 질문이 그냥 메시지라 읽으면 그게 화면이다(ADR 0001)."""
    async with client:
        await _turn(client, "t1", "리뷰 써야 해")
        await _turn(client, "t1", "결제 지연을 줄였어요", intent="provide_info")

        response = await client.get("/threads/t1")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


async def test_없는_스레드는_404(client):
    async with client:
        response = await client.get("/threads/없음")
    assert response.status_code == 404


async def test_스레드는_서로_섞이지_않는다(client):
    async with client:
        await _turn(client, "a", "리뷰 써야 해")
        await _turn(client, "b", "나도 써야 해")
        first = await client.get("/threads/a")

    assert len(first.json()["messages"]) == 2


async def test_액션_칩을_생략하면_지난_칩이_남지_않는다(client):
    """`client_intent`는 요청 스키마가 매 턴 `None`으로 채운다.

    안 그러면 write_now 칩이 상태에 남아, 다음 평범한 메시지에도 초안이
    다시 생성된다.
    """
    async with client:
        await _turn(client, "t1", "리뷰 써야 해")
        await _turn(client, "t1", "결제 지연을 줄였어요", intent="provide_info")
        await _turn(client, "t1", "초안 써줘", intent="write_now")

        # 칩 없이 그냥 한마디. 초안이 또 생성되면 안 된다.
        body = await _turn(client, "t1", "고마워")

    assert "이대로 확정할까요?" not in body["messages"][-1]["content"]


async def test_막힌_초안은_응답에_실리지_않는다(blocked_client):
    """`draft`를 내려주지 않는 이유 — 막은 초안을 클라이언트가 읽으면
    ADR 0005가 무의미해진다."""
    async with blocked_client:
        await _turn(blocked_client, "t1", "리뷰 써야 해")
        await _turn(blocked_client, "t1", "결제 지연을 줄였어요", intent="provide_info")
        body = await _turn(blocked_client, "t1", "초안 써줘", intent="write_now")

    assert "draft" not in body
    assert "내보내지 않았습니다" in body["messages"][-1]["content"]
    assert body["tags"]["과장허위"] is False  # 왜 막혔는지는 보여준다


async def test_빈_입력은_거부한다(client):
    async with client:
        response = await client.post("/threads/t1/turns", json={"text": ""})
    assert response.status_code == 422


async def test_같은_스레드의_동시_턴은_직렬화된다(client):
    """`_seeded_payload`의 조회와 실행 사이가 TOCTOU다.

    직렬화하지 않으면 두 요청이 서로의 턴을 덮어 **어시스턴트 응답 하나가 통째로
    사라진다.** 이론이 아니라 같은 브라우저의 두 탭이면 재현된다 — 프론트의
    중복 전송 차단은 컴포넌트 단위라 탭 사이를 못 막는다.
    """
    async with client:
        await _turn(client, "t1", "리뷰 써야 해")

        await asyncio.gather(
            _turn(client, "t1", "결제 지연을 줄였어요", intent="provide_info"),
            _turn(client, "t1", "장애 대응도 했어요", intent="provide_info"),
        )

        restored = (await client.get("/threads/t1")).json()

    # 턴 3개 → user·assistant가 번갈아 3쌍. 하나도 안 사라진다.
    assert [m["role"] for m in restored["messages"]] == ["user", "assistant"] * 3


async def test_가능한_동의를_함께_내려준다(client):
    """화면은 이걸 버튼으로 그린다.

    상태에서 유도하므로 **새로고침해도 살아난다.** 스트림에서 어느 노드가
    돌았는지로 알아내면 복원이 안 되고, 서버 문구를 뒤지면 백엔드 카피에 묶인다.
    """
    async with client:
        body = await _turn(client, "t1", "리뷰 써야 해")
        assert body["actions"] == []  # 아직 재료가 없다

        body = await _turn(client, "t1", "결제 지연을 줄였어요", intent="provide_info")
        assert body["actions"] == ["write_now"]

        body = await _turn(client, "t1", "초안 써줘", intent="write_now")
        assert body["actions"] == ["proceed", "revise"]

        restored = await client.get("/threads/t1")

    assert restored.json()["actions"] == ["proceed", "revise"]


async def test_정적_마운트가_API_경로를_삼키지_않는다(make_llm, tmp_path):
    """빌드된 프론트를 같은 오리진에서 서빙한다. 순서가 함정이다.

    Starlette는 등록 순서로 매칭하므로 `"/"` 마운트를 API 라우트보다 먼저 걸면
    `/threads`·`/health`까지 정적 핸들러가 가로챈다. 그러면 프론트를 붙이는
    순간 백엔드가 통째로 죽는데, 그게 배포에서야 드러난다.
    """
    (tmp_path / "index.html").write_text("<!doctype html><title>셸</title>", encoding="utf-8")
    app = create_app(build_graph(make_llm(), MemorySaver()), static_dir=tmp_path)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async with client:
        health = await client.get("/health")
        body = await _turn(client, "t1", "리뷰 써야 해")
        shell = await client.get("/")

    assert health.json() == {"status": "ok"}  # API가 살아 있고
    assert body["thread_id"] == "t1"
    assert "셸" in shell.text  # 프론트도 나온다


async def test_프론트가_없으면_마운트하지_않는다(client):
    """개발 중에는 Vite가 프론트를 맡는다 — 이 앱은 API만 내주면 된다."""
    async with client:
        response = await client.get("/")
    assert response.status_code == 404


async def test_모르는_의도는_거부한다(client):
    """`Intent`가 Literal이라 스키마 단계에서 걸린다."""
    async with client:
        response = await client.post(
            "/threads/t1/turns", json={"text": "확정", "client_intent": "그냥_해줘"}
        )
    assert response.status_code == 422
