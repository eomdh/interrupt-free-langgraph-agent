"""환경 설정."""

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    #: Postgres 연결 문자열. 체크포인터가 상태의 유일한 저장소다(ADR 0001).
    database_url: str = "postgresql://agent:agent@localhost:5432/agent"

    #: `fake`가 기본이다. 키 없이 클론해서 바로 돌려볼 수 있어야 한다(관리 규약 §8.2).
    llm_mode: Literal["fake", "openai"] = "fake"

    #: 빌드된 프론트가 놓인 자리. 있으면 같은 오리진에서 서빙한다 — 그래서 CORS가 없다.
    #: 로컬 개발에는 없다. 그때는 Vite가 프론트를 맡고 이 앱은 API만 내준다.
    web_dist: Path = Path("web-dist")

    #: OpenAI 호환 엔드포인트. OpenRouter · Groq · Ollama 전부 여기만 바꾸면 된다.
    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_api_key: str = ""
    llm_model: str = ""

    @model_validator(mode="after")
    def _require_credentials(self) -> "Settings":
        """`openai` 모드인데 키나 모델이 비면 **기동 시점에** 막는다.

        런타임에 첫 LLM 호출까지 가서야 터지면, 그때는 이미 사용자가 대화를
        시작한 뒤다.
        """
        if self.llm_mode != "openai":
            return self

        missing = [
            name
            for name, value in (("OPENAI_API_KEY", self.openai_api_key), ("LLM_MODEL", self.llm_model))
            if not value
        ]
        if missing:
            raise ValueError(f"LLM_MODE=openai면 {' · '.join(missing)}가 필요하다")
        return self
