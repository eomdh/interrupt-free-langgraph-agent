"""설정 검증 — 잘못된 조합으로는 아예 못 뜬다."""

import pytest
from pydantic import ValidationError

from agent.settings import Settings


def test_기본값은_목_모드():
    """키 없이 클론해서 바로 돌릴 수 있어야 한다(관리 규약 §8.2)."""
    assert Settings(_env_file=None).llm_mode == "fake"


def test_목_모드는_키가_없어도_된다():
    settings = Settings(_env_file=None, llm_mode="fake")
    assert settings.openai_api_key == ""


@pytest.mark.parametrize(
    ("api_key", "model"),
    [("", ""), ("sk-test", ""), ("", "some-model")],
)
def test_openai_모드인데_키나_모델이_비면_기동을_막는다(api_key, model):
    """런타임 첫 호출에서 터지면 이미 사용자가 대화를 시작한 뒤다."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_mode="openai", openai_api_key=api_key, llm_model=model)


def test_둘_다_있으면_뜬다():
    settings = Settings(
        _env_file=None, llm_mode="openai", openai_api_key="sk-test", llm_model="some-model"
    )
    assert settings.llm_mode == "openai"


def test_모르는_모드는_거부한다():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_mode="anthropic")
