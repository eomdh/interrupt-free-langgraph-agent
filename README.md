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

브라우저에서 **`localhost:8000`**. 프론트가 같은 이미지 안에서 빌드돼 함께 담기므로 명령은 이것 하나다. 초안을 요청하면 `draft ⇄ tag` 루프가 도는 게 스텝퍼에서 보이고, 5축 채점이 실시간으로 채워진다.

`interrupt()`를 안 쓴 값어치는 **앱을 죽여보면** 드러난다.

```bash
T=$(uuidgen)                       # 스레드 ID 가 곧 접근 권한이다

curl -X POST localhost:8000/threads/$T/turns \
     -H 'content-type: application/json' -d '{"text":"성과 리뷰 써야 해"}'

docker compose restart app         # 프로세스 메모리를 날린다

curl localhost:8000/threads/$T     # 대화가 그대로 있다
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

끝까지 돈다. 테스트는 백엔드 190개 · 프론트 65개.

- 동의 게이트 — 에이전트가 사용자를 앞지르지 못한다. 조작된 요청도 상태 게이트를 못 뚫는다
- 채점 fail-safe — 축이 빠지거나 값이 이상하면 전부 미달로 본다 ("판정 불가 = 미달")
- 허위 차단 — 근거를 확인 못 한 초안은 상한에 닿아도 내보내지 않는다. HTTP 응답에도 안 싣는다
- 무상태 앱 + Postgres 체크포인터 — 재시작해도 대화가 남는다
- 진행 스트림(SSE) — `POST /threads/{id}/turns/stream`이 노드 전환을 흘린다. 초안 본문은 안 싣는다 (ADR 0006)
- 진행 스텝퍼 + 채점 패널 — 자율 루프가 도는 게 화면에 보인다. 상태 배지는 아이콘과 라벨을 같이 써서 색 없이도 읽힌다 (ADR 0007)
- 채점관 평가 — 품질 서사가 통째로 `tag` 판정에 걸려 있는데, 목은 `task` 이름으로 답해서 **프롬프트 문구가 테스트에 안 보인다.** 손으로 라벨한 골든 셋으로 따로 잰다 ([`evals/`](evals/))

UI 는 [StyleSeed](https://github.com/bitjaru/styleseed)의 룰과 toss 스킨을 따른다. 확정값은 [`web/STYLESEED.md`](web/STYLESEED.md)에 잠겨 있다.

읽어볼 만한 곳은 [`tests/test_consent_gate.py`](tests/test_consent_gate.py)다. 이 앱이 막으려는 실패가 뭔지 거기 다 있다.

## 개발

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run python -m evals.run --dry-run   # 채점관 평가 — 모델 호출 없이 룰만
```

프론트는 `web/`에 있다. dev 서버는 `/threads`·`/health`를 `:8000`으로 프록시하므로, 백엔드를 먼저 띄워두면 같은 오리진처럼 동작한다.

```bash
pnpm --dir web install
pnpm --dir web dev        # :5173
pnpm --dir web test       # vitest
pnpm --dir web typecheck
pnpm --dir web lint       # biome
```

## License

MIT
