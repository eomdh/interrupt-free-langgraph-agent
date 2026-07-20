# interrupt-free-langgraph-agent

[![CI](https://github.com/eomdh/interrupt-free-langgraph-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/eomdh/interrupt-free-langgraph-agent/actions/workflows/ci.yml)

`interrupt()` 없이 짠 LangGraph 대화 에이전트. **매 POST가 한 번의 실행으로 끝나고, 질문은 그냥 `AIMessage`로 남는다.**

```
POST #1  START → router → interview   → AIMessage("그 수치는 어떻게 측정했나요?")  → END
POST #2  START → router → interview   → AIMessage("본인 기여는 어디까지였나요?")   → END
POST #3  START → router → draft ⇄ tag → AIMessage(초안)                      → END
```

## 돌려보기

```bash
docker compose up --build          # app + postgres
```

`interrupt()`를 안 쓴 값어치는 **앱을 죽여보면** 드러난다.

```bash
curl -X POST localhost:8000/threads/demo/turns \
     -H 'content-type: application/json' -d '{"text":"성과 리뷰 써야 해"}'

docker compose restart app         # 프로세스 메모리를 날린다

curl localhost:8000/threads/demo   # 대화가 그대로 있다
```

복원 코드는 없다. 질문이 특수 상태가 아니라 그냥 `AIMessage`라 체크포인터가 대화를 통째로 들고 있고, 앱은 아무것도 기억하지 않는다.

기본은 **목 모드**다. 키 없이 흐름·게이트·복원이 전부 돈다. 대신 글은 정해진 응답이라 품질을 볼 게 없다.

### 실제 모델 붙이기

```bash
cp .env.example .env      # LLM_MODE=openai + 키·모델 채우기
docker compose up --build
```

OpenAI 호환이면 무엇이든 된다 — `OPENAI_BASE_URL`만 바꾸면 OpenRouter·OpenAI·Groq·Ollama로 옮겨간다. 제공자별 SDK를 안 쓴 이유다. 키나 모델이 비어 있으면 **기동 시점에** 막는다. 첫 호출까지 가서 터지면 이미 사용자가 대화를 시작한 뒤라서.

## 왜

LangGraph 표준은 `interrupt()`로 그래프를 멈추고 `Command(resume)`로 재개하는 것이다. 웹 앱에서는 이게 잘 안 맞는다 — 브라우저는 언제든 새로고침되고, 멈춰 있는 그래프를 그 사이에 들고 있어야 한다.

여기서는 멈추지 않는다. 질문이 필요하면 노드가 `AIMessage`를 남기고 END로 나온 뒤 다음 POST를 기다린다. 질문이 일반 메시지라 체크포인터가 전부 보관하고, **새로고침 복원이 별도 구현 없이 따라온다.** 앱은 무상태가 된다.

설계 결정과 트레이드오프는 [`docs/adr/`](docs/adr/)에 있다.

## 상태

백엔드는 끝까지 돈다. 테스트 58개.

- 동의 게이트 — 에이전트가 사용자를 앞지르지 못한다. 조작된 요청도 상태 게이트를 못 뚫는다
- 채점 fail-safe — 축이 빠지거나 값이 이상하면 전부 미달로 본다 ("판정 불가 = 미달")
- 허위 차단 — 근거를 확인 못 한 초안은 상한에 닿아도 내보내지 않는다. HTTP 응답에도 안 싣는다
- 무상태 앱 + Postgres 체크포인터 — 재시작해도 대화가 남는다

프론트(노드 진행 스텝퍼)와 진행 스트림(SSE)은 아직이다.

읽어볼 만한 곳은 [`tests/test_consent_gate.py`](tests/test_consent_gate.py)다. 이 앱이 막으려는 실패가 뭔지 거기 다 있다.

## 개발

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

## License

MIT
