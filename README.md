# interrupt-free-langgraph-agent

`interrupt()` 없이 짠 LangGraph 대화 에이전트. **매 POST가 한 번의 실행으로 끝나고, 질문은 그냥 `AIMessage`로 남는다.**

```
POST #1  START → router → interview   → AIMessage("그 수치는 어떻게 측정했나요?")  → END
POST #2  START → router → interview   → AIMessage("본인 기여는 어디까지였나요?")   → END
POST #3  START → router → draft ⇄ tag → AIMessage(초안)                      → END
```

## 왜

LangGraph 표준은 `interrupt()`로 그래프를 멈추고 `Command(resume)`로 재개하는 것이다. 웹 앱에서는 이게 잘 안 맞는다 — 브라우저는 언제든 새로고침되고, 멈춰 있는 그래프를 그 사이에 들고 있어야 한다.

여기서는 멈추지 않는다. 질문이 필요하면 노드가 `AIMessage`를 남기고 END로 나온 뒤 다음 POST를 기다린다. 질문이 일반 메시지라 체크포인터가 전부 보관하고, **새로고침 복원이 별도 구현 없이 따라온다.** 앱은 무상태가 된다.

설계 결정과 트레이드오프는 [`docs/adr/`](docs/adr/)에 있다.

## 상태

구현 중. 라우터·게이트·self-eval 분기까지 동작하고 테스트로 묶여 있다.
워커 노드(LLM 호출)와 FastAPI·프론트는 아직이다.

## 개발

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

## License

MIT
