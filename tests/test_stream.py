"""진행 스트림 — 노드 전환을 SSE로 중계하되, 초안 본문은 안 싣는다.

여기서 잡는 계약은 목으로 전부 덮인다: 이벤트 어휘·순서·누출 차단·JSON 패리티.
프롬프트 품질이나 실제 모델의 스트리밍은 여기 없다(그건 실모델 검증 대기 몫).

`text/event-stream`은 스트림이 끝에서 닫히므로 `client.post`가 본문을 통째로
읽는다. 그 텍스트를 프레임으로 파싱해서 이벤트 목록으로 본다.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from agent.api import create_app
from agent.graph import build_graph
from agent.llm import FakeLLM


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """SSE 본문을 `(event, data)` 목록으로. 빈 프레임은 버린다."""
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = ""
        data: dict = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        events.append((event, data))
    return events


async def _stream(client, thread: str, text: str, intent: str | None = None) -> list[tuple]:
    body: dict = {"text": text}
    if intent is not None:
        body["client_intent"] = intent
    response = await client.post(f"/threads/{thread}/turns/stream", json=body)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


async def _post(client, thread: str, text: str, intent: str | None = None) -> dict:
    body: dict = {"text": text}
    if intent is not None:
        body["client_intent"] = intent
    response = await client.post(f"/threads/{thread}/turns", json=body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def client(make_llm):
    app = create_app(build_graph(make_llm(), MemorySaver()))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def blocked_client(make_llm, tags_json):
    """허위가 안 걷히는 목 — 초안이 `blocked`로 막히는 경로."""
    app = create_app(build_graph(make_llm(tag=tags_json(과장허위=False)), MemorySaver()))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def quality_fail_client(make_llm, tags_json):
    """품질 축(정량성)만 미달인 목 — 상한까지 재작성하다 미달인 채 내보낸다."""
    app = create_app(build_graph(make_llm(tag=tags_json(정량성=False)), MemorySaver()))
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _run_to_draft(stream_or_post, client, thread: str) -> object:
    """온보딩→성과→초안 요청까지 밀어 넣는다. 마지막 턴 결과를 돌려준다."""
    await stream_or_post(client, thread, "리뷰 써야 해")
    await stream_or_post(client, thread, "결제 지연을 줄였어요", intent="provide_info")
    return await stream_or_post(client, thread, "초안 써줘", intent="write_now")


async def test_첫_턴은_node에서_시작해_done으로_닫힌다(client):
    """이벤트 순서 — 라우터가 고른 노드부터, 마지막은 항상 `done`."""
    async with client:
        events = await _stream(client, "t1", "성과 리뷰 써야 해")

    kinds = [event for event, _ in events]
    assert kinds[0] == "node"
    assert events[0][1]["node"] == "onboard"  # 프로필이 비어 라우터가 onboard로 보낸다
    assert kinds[-1] == "done"
    assert "done" not in kinds[:-1]  # done 뒤에는 아무것도 없다


async def test_내부_단계는_진행으로_안_나간다(client):
    """`classify`는 어디로 갈지 정하는 내부 단계다.

    내보내면 매 턴 첫머리에 의미 없는 깜빡임이 생기고, 스텝퍼가 매핑할 단계도
    없다. 순번도 거른 뒤에 매겨서 클라이언트가 보는 seq가 이어진다.
    """
    async with client:
        events = await _stream(client, "t1", "성과 리뷰 써야 해")

    assert "classify" not in [data.get("node") for _, data in events]
    assert [data["seq"] for event, data in events if event in ("node", "loop")] == [1]


async def test_done은_정착된_ThreadView를_싣는다(client):
    """마지막 이벤트가 대화의 현재 모습이다 — 프론트는 이걸로 화면을 그린다."""
    async with client:
        events = await _stream(client, "t1", "성과 리뷰 써야 해")

    event, data = events[-1]
    assert event == "done"
    assert data["thread_id"] == "t1"
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]


async def test_스트림과_JSON은_같은_결과에_이른다(client, make_llm):
    """같은 입력이면 `done`의 ThreadView == JSON 응답. 스트림이 진실과 갈라지면 안 된다."""
    async with client:
        streamed = await _run_to_draft(_stream, client, "s")
        posted = await _run_to_draft(_post, client, "j")

    done_event, done_data = streamed[-1]
    assert done_event == "done"
    # thread_id만 다르다(s vs j). 나머지 — 대화·채점 — 는 같아야 한다.
    assert done_data["messages"] == posted["messages"]
    assert done_data["tags"] == posted["tags"]


async def test_막힌_초안은_스트림_어디에도_안_샌다(blocked_client, make_llm):
    """ADR 0005의 스트림 판. `updates`가 draft 델타에 원본을 담아 주지만,
    투영이 화이트리스트라 진행 이벤트로 새지 않는다. blocked 경로는 초안을
    끝내 안 내보내므로 스트림 텍스트 어디에도 본문이 없어야 한다."""
    draft_text = make_llm().responses["draft"]

    async with blocked_client:
        await _post(blocked_client, "t1", "리뷰 써야 해")
        await _post(blocked_client, "t1", "결제 지연을 줄였어요", intent="provide_info")
        response = await blocked_client.post(
            "/threads/t1/turns/stream", json={"text": "초안 써줘", "client_intent": "write_now"}
        )
        raw = response.text

    events = parse_sse(raw)
    assert draft_text not in raw  # 원본 초안 본문이 스트림 어디에도 없다
    # draft·tag 노드는 돌았지만(loop 이벤트로 보인다), 본문은 안 실렸다.
    assert any(data.get("node") == "draft" for _, data in events)
    done = next(data for event, data in events if event == "done")
    assert "draft" not in done  # 최종 뷰에도 초안 키가 없다(ADR 0005)


async def test_재작성_루프가_loop_이벤트로_보인다(quality_fail_client):
    """draft⇄tag가 상한까지 도는 게 스트림에 드러난다 — 자율 루프가 '도는 중'."""
    async with quality_fail_client:
        events = await _run_to_draft(_stream, quality_fail_client, "t1")

    loops = [data for event, data in events if event == "loop"]
    draft_loops = [data for data in loops if data["node"] == "draft"]
    tag_loops = [data for data in loops if data["node"] == "tag"]

    # MAX_REVISE=2 → 첫 초안 + 2회 재작성 = draft 3번, 그 뒤 deliver.
    assert [data["attempt"] for data in draft_loops] == [1, 2, 3]
    # tag 이벤트는 어느 축이 미달인지 싣는다 — bool뿐이라 실어도 안전하다.
    assert all(data["tags"]["정량성"] is False for data in tag_loops)
    assert events[-1][0] == "done"  # 상한에서 멈추고 내보낸다(무한 루프 아님)


async def test_스트림_턴도_체크포인터에_남는다(client):
    """스트림도 `ainvoke`처럼 매 스텝을 체크포인트한다. GET하면 대화가 있다(ADR 0001)."""
    async with client:
        await _stream(client, "t1", "성과 리뷰 써야 해")
        restored = await client.get("/threads/t1")

    assert restored.status_code == 200
    assert [m["role"] for m in restored.json()["messages"]] == ["user", "assistant"]


async def test_실행_중_오류는_error_이벤트로_나온다():
    """스트림이 열린 뒤 노드가 터지면 상태 코드를 못 바꾼다. 연결을 매달지 말고
    `error`로 알린다 — 목에 'onboard' 응답이 없으면 첫 노드가 KeyError로 깨진다."""
    app = create_app(build_graph(FakeLLM({}), MemorySaver()))
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async with client:
        events = await _stream(client, "t1", "성과 리뷰 써야 해")

    assert any(event == "error" for event, _ in events)
    assert not any(event == "done" for event, _ in events)  # 완주 못 했다

    # 내부 사정은 안 내보낸다. LLMError 는 업스트림 응답 본문을, 체크포인터
    # 실패는 내부 호스트·DB 사용자를 담는데 여기 인증이 없다. 참조 번호만 준다.
    detail = next(data["detail"] for event, data in events if event == "error")
    assert "onboard" not in detail  # 예외 문자열이 그대로 새지 않는다
    assert "ref:" in detail
