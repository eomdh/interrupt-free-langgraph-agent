"""LLM 경계.

노드는 이 프로토콜만 안다. 실제 구현이 무엇이든, 목이든 상관하지 않는다.
그래서 API 키 없이도 그래프 전 구간이 돈다(관리 규약 §8.2).
"""

import asyncio
import contextlib
from typing import Any, Protocol

import httpx

#: 잠깐 지나가는 실패. 무료 등급에서 429는 예외가 아니라 일상이다.
#: 5xx도 같이 본다 — 제공자 게이트웨이가 흔들릴 때 나오고, 다시 부르면 대개 된다.
_TRANSIENT = frozenset({408, 429})


def _is_transient(status: int) -> bool:
    return status in _TRANSIENT or status >= 500


class LLMError(RuntimeError):
    """LLM 호출이 실패했거나 응답이 예상과 다르다.

    조용히 빈 문자열을 돌려주지 않는다. 노드의 파싱 fail-safe가 그걸
    "판정 불가 = 미달"로 삼켜버려서, 진짜 장애가 품질 문제로 위장된다.
    """


class LLM(Protocol):
    """텍스트 하나를 받아 텍스트 하나를 돌려주는 것.

    `task`는 목킹용이 아니라 **관측용**이다. 어느 노드가 부른 호출인지
    로그·트레이스·토큰 비용 집계에 필요하다. 목이 그걸 재활용할 뿐이다.

    `temperature`는 노드마다 다르다 — 채점은 0, 생성은 0.4(ADR 0003).
    """

    async def complete(self, prompt: str, *, task: str, temperature: float = 0.0) -> str: ...


class FakeLLM:
    """결정적 목. `task` 이름으로 미리 정한 응답을 돌려준다.

    호출 기록을 남기므로 "채점은 temperature 0으로 불렀나" 같은 것도
    테스트에서 확인할 수 있다.
    """

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def complete(self, prompt: str, *, task: str, temperature: float = 0.0) -> str:
        self.calls.append({"task": task, "prompt": prompt, "temperature": temperature})
        if task not in self.responses:
            raise KeyError(f"목에 '{task}' 응답이 없다. 테스트에서 정의할 것.")
        return self.responses[task]


class OpenAICompatibleLLM:
    """OpenAI 호환 Chat Completions 클라이언트.

    OpenAI · OpenRouter · Groq · Ollama · LM Studio가 전부 같은 요청 스키마를
    쓴다. 그래서 구현은 하나고 `base_url`만 설정으로 바꾼다 — 제공자별 SDK를
    끌어오면 그만큼 갈아탈 때 코드가 묶인다.

    일시적인 실패는 지수 백오프로 몇 번 다시 부른다. 무료 등급 모델은 업스트림
    429가 잦아서, 재시도가 없으면 지나가는 스로틀 하나에 턴 전체가 죽는다.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
        retries: int = 2,
        retry_base_delay: float = 1.0,
        max_retry_delay: float = 8.0,
    ) -> None:
        self._model = model
        self._retries = retries
        self._retry_base_delay = retry_base_delay
        self._max_retry_delay = max_retry_delay
        # 테스트는 `client`에 목 전송을 넣어 실제 호출 없이 요청 모양을 본다.
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def complete(self, prompt: str, *, task: str, temperature: float = 0.0) -> str:
        """한 번 부른다. 잠깐 지나가는 실패는 몇 번 다시 시도한다.

        재시도는 실패를 삼키는 것과 다르다. `LLMError`가 있는 이유는 장애가
        품질 문제로 위장하는 걸 막기 위해서인데(빈 문자열을 돌려주면 채점
        fail-safe가 "판정 불가 = 미달"로 흡수한다), **일시적인 429를 다시 부르는
        건 삼키는 게 아니라 다루는 것**이다. 상한을 넘기면 그때는 올린다.

        영구적인 실패(키가 틀렸다, 모델명이 없다)는 **즉시 포기한다.** 세 번
        더 불러봐야 같은 답이고 사용자만 기다린다.
        """
        payload = {
            "model": self._model,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        for attempt in range(self._retries + 1):
            last = attempt == self._retries

            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as error:
                # 끊긴 연결·타임아웃도 대개 일시적이다.
                if last:
                    raise LLMError(f"'{task}' 호출 실패: {error}") from error
                await self._wait(attempt, None)
                continue

            if response.status_code < 400:
                return self._content(self._parse(response, task), task)

            if last or not _is_transient(response.status_code):
                raise LLMError(f"'{task}' 호출이 {response.status_code}: {response.text[:200]}")

            await self._wait(attempt, response.headers.get("retry-after"))

        raise AssertionError("도달할 수 없다 — 마지막 시도는 반드시 반환하거나 던진다")

    async def _wait(self, attempt: int, retry_after: str | None) -> None:
        """다음 시도까지 기다린다. 서버가 시간을 알려주면 그 말을 따른다."""
        delay = min(self._retry_base_delay * 2**attempt, self._max_retry_delay)

        if retry_after:
            # HTTP-date 형식은 안 다룬다 — 파싱이 안 되면 지수 백오프로 떨어진다.
            with contextlib.suppress(ValueError):
                delay = min(float(retry_after), self._max_retry_delay)

        await asyncio.sleep(delay)

    @staticmethod
    def _parse(response: httpx.Response, task: str) -> Any:
        """본문을 JSON으로 읽는다. 프록시가 HTML 오류 페이지를 200으로 주기도 한다."""
        try:
            return response.json()
        except ValueError as error:
            raise LLMError(f"'{task}' 응답이 JSON이 아니다: {response.text[:200]}") from error

    @staticmethod
    def _content(payload: Any, task: str) -> str:
        """응답에서 본문만 꺼낸다. 모양이 다르면 그 자리에서 깬다."""
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError(f"'{task}' 응답 스키마가 예상과 다르다: {str(payload)[:200]}") from error

        if not isinstance(content, str):
            raise LLMError(f"'{task}' 응답 본문이 문자열이 아니다: {type(content).__name__}")
        return content

    async def aclose(self) -> None:
        await self._client.aclose()
