"""환경 설정."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    #: Postgres 연결 문자열. 체크포인터가 상태의 유일한 저장소다(ADR 0001).
    database_url: str = "postgresql://agent:agent@localhost:5432/agent"

    #: 실제 LLM 클라이언트는 아직 없다. `fake`만 유효하며, 다른 값을 주면
    #: 기동 시점에 설정 검증이 막는다 — 조용히 잘못된 모드로 뜨지 않게.
    llm_mode: Literal["fake"] = "fake"
