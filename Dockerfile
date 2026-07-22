# 프론트를 먼저 빌드하고 **산출물만** 런타임 이미지로 넘긴다.
# node 툴체인이 최종 이미지에 남지 않는다.
FROM node:22-alpine AS web

# github: 의존성(fetch-sse-client)을 받으려면 git 이 필요하다.
RUN apk add --no-cache git
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable

WORKDIR /web

# 의존성 먼저 굳혀 레이어 캐시를 살린다. pnpm-workspace.yaml 은 esbuild 의
# 설치 스크립트 허용 목록이라 이 단계에 같이 있어야 한다.
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm build


FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# 의존성 해석을 먼저 굳혀 레이어 캐시를 살린다. README는 hatchling이
# 패키지 메타데이터로 읽으므로 같이 넣는다.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv sync --no-dev

# 빌드된 프론트. `Settings.web_dist` 가 여기를 가리키고, 같은 오리진에서
# 서빙되므로 CORS 설정이 필요 없다.
COPY --from=web /web/dist ./web-dist

EXPOSE 8000

# 동기화된 venv 를 직접 부른다. `uv run` 은 실행할 때마다 의존성을 다시 맞추는데,
# 그러면 `--no-dev` 로 뺀 개발 의존성이 기동 때 도로 깔리고 컨테이너가 뜨는 데
# 수십 초가 걸린다 — README 의 "restart 직후 복원" 데모가 그 시간에 깨진다.
CMD [".venv/bin/uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
