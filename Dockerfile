FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# 의존성 해석을 먼저 굳혀 레이어 캐시를 살린다. README는 hatchling이
# 패키지 메타데이터로 읽으므로 같이 넣는다.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
