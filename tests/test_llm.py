"""OpenAI 호환 클라이언트 — 요청을 올바르게 만들고, 이상하면 조용히 넘기지 않는다.

목 전송을 쓰므로 키가 없어도 돈다. 다만 **이 테스트가 증명하는 건 요청의
모양뿐**이다. 실제 API가 그 요청을 받아주는지는 한 번은 진짜로 불러봐야
안다(README의 `LLM_MODE=openai` 절차).
"""

import httpx
import pytest

from agent.llm import LLMError, OpenAICompatibleLLM


def _llm(handler) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        base_url="https://example.test/v1",
        api_key="sk-test",
        model="test-model",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test/v1",
            headers={"Authorization": "Bearer sk-test"},
        ),
    )


def _ok(content: str):
    def handler(request: httpx.Request) -> httpx.Response:
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

    def handler(request: httpx.Request) -> httpx.Response:
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
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(LLMError):
        await _llm(handler).complete("써줘", task="draft")


async def test_네트워크_오류도_LLMError로_감싼다():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("연결 실패")

    with pytest.raises(LLMError):
        await _llm(handler).complete("써줘", task="draft")
