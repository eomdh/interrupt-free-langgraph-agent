"""LLM 경계.

노드는 이 프로토콜만 안다. 실제 구현이 무엇이든, 목이든 상관하지 않는다.
그래서 API 키 없이도 그래프 전 구간이 돈다(관리 규약 §8.2).
"""

from typing import Protocol


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
