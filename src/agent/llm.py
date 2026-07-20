"""LLM 경계.

노드는 이 프로토콜만 안다. 실제 구현이 무엇이든, 목이든 상관하지 않는다.
그래서 API 키 없이도 그래프 전 구간이 돈다(관리 규약 §8.2).
"""

from typing import Any, Protocol

import httpx


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
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._model = model
        # 테스트는 `client`에 목 전송을 넣어 실제 호출 없이 요청 모양을 본다.
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def complete(self, prompt: str, *, task: str, temperature: float = 0.0) -> str:
        try:
            response = await self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        except httpx.HTTPError as error:
            raise LLMError(f"'{task}' 호출 실패: {error}") from error

        if response.status_code >= 400:
            raise LLMError(f"'{task}' 호출이 {response.status_code}: {response.text[:200]}")

        return self._content(response.json(), task)

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
