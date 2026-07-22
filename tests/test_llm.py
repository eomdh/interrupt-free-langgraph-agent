"""OpenAI 호환 클라이언트 — 요청을 올바르게 만들고, 이상하면 조용히 넘기지 않는다.

목 전송을 쓰므로 키가 없어도 돈다. 다만 **이 테스트가 증명하는 건 요청의
모양뿐**이다. 실제 API가 그 요청을 받아주는지는 한 번은 진짜로 불러봐야
안다(README의 `LLM_MODE=openai` 절차).
"""

import asyncio

import httpx
import pytest

from agent.llm import LLMError, OpenAICompatibleLLM


def _llm(handler, **options) -> OpenAICompatibleLLM:
    # 재시도 횟수는 기본값 그대로 두되, 테스트가 실제로 기다릴 이유는 없다.
    # 지연을 직접 보는 테스트는 이 값을 넘겨 덮는다.
    options.setdefault("retry_base_delay", 0)

    return OpenAICompatibleLLM(
        base_url="https://example.test/v1",
        api_key="sk-test",
        model="test-model",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test/v1",
            headers={"Authorization": "Bearer sk-test"},
        ),
        **options,
    )


def _counting(*responses: httpx.Response):
    """정해둔 응답을 차례로 돌려주고, 몇 번 불렸는지 센다. 마지막 응답이 반복된다."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    return handler, calls


def _ok(content: str):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return handler


async def test_응답_본문을_꺼낸다():
    llm = _llm(_ok("초안입니다"))
    assert await llm.complete("써줘", task="draft") == "초안입니다"


async def test_모델과_temperature가_요청에_실린다():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(httpx.Response(200, content=request.content).json())
        return _ok("ok")(request)

    llm = _llm(handler)
    await llm.complete("채점해줘", task="tag", temperature=0.0)

    assert seen["model"] == "test-model"
    assert seen["temperature"] == 0.0
    assert seen["messages"] == [{"role": "user", "content": "채점해줘"}]


async def test_인증_헤더가_붙는다():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return _ok("ok")(request)

    await _llm(handler).complete("안녕", task="respond")
    assert seen["auth"] == "Bearer sk-test"


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_실패_응답은_LLMError로_올린다(status):
    """빈 문자열로 삼키면 노드의 fail-safe가 장애를 품질 문제로 위장한다."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="nope")

    with pytest.raises(LLMError) as caught:
        await _llm(handler).complete("써줘", task="draft")

    assert str(status) in str(caught.value)
    assert "draft" in str(caught.value)  # 어느 호출이 깨졌는지 남긴다


@pytest.mark.parametrize(
    "payload",
    [{}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {}}]}],
)
async def test_스키마가_다르면_LLMError(payload):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(LLMError):
        await _llm(handler).complete("써줘", task="draft")


async def test_네트워크_오류도_LLMError로_감싼다():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("연결 실패")

    with pytest.raises(LLMError):
        await _llm(handler).complete("써줘", task="draft")


async def test_JSON이_아니면_LLMError():
    """프록시가 HTML 오류 페이지를 200으로 주기도 한다."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>502 Bad Gateway</html>")

    with pytest.raises(LLMError, match="JSON"):
        await _llm(handler).complete("써줘", task="draft")


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_일시적_실패는_다시_시도한다(status):
    """무료 등급에서 429는 예외가 아니라 일상이다 — 하나에 턴이 죽으면 안 된다."""
    handler, calls = _counting(
        httpx.Response(status, text="throttled"),
        httpx.Response(200, json={"choices": [{"message": {"content": "됐다"}}]}),
    )

    assert await _llm(handler).complete("써줘", task="draft") == "됐다"
    assert len(calls) == 2


async def test_네트워크_오류도_다시_시도한다():
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("일시적 끊김")
        return httpx.Response(200, json={"choices": [{"message": {"content": "됐다"}}]})

    assert await _llm(handler).complete("써줘", task="draft") == "됐다"
    assert len(calls) == 2


async def test_상한을_넘으면_결국_올린다():
    """무한히 매달리지 않는다. 계속 실패하면 그건 진짜 장애다."""
    handler, calls = _counting(httpx.Response(429, text="throttled"))

    with pytest.raises(LLMError):
        await _llm(handler, retries=2).complete("써줘", task="draft")

    assert len(calls) == 3  # 첫 시도 + 재시도 2회


@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_영구적_실패는_즉시_포기한다(status):
    """키나 모델명이 틀린 걸 세 번 더 물어봐야 같은 답이다 — 사용자만 기다린다."""
    handler, calls = _counting(httpx.Response(status, text="nope"))

    with pytest.raises(LLMError):
        await _llm(handler).complete("써줘", task="draft")

    assert len(calls) == 1


async def test_서버가_알려준_대기시간을_따른다(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    handler, _ = _counting(
        httpx.Response(429, text="throttled", headers={"retry-after": "3"}),
        httpx.Response(200, json={"choices": [{"message": {"content": "됐다"}}]}),
    )
    # 기본 지연을 크게 둬도 서버가 말한 3초를 쓴다.
    await _llm(handler, retry_base_delay=30, max_retry_delay=60).complete("써줘", task="draft")

    assert slept == [3.0]
