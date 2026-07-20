"""여러 테스트가 같이 쓰는 조각."""

from langchain_core.messages import HumanMessage


def turn(text: str, intent: str | None = None) -> dict:
    """POST 한 번치 입력.

    `client_intent`는 **매 턴 명시한다.** 안 넘기면 지난 턴의 칩이 상태에
    남아 다시 게이트를 연다.
    """
    return {"messages": [HumanMessage(text)], "client_intent": intent}


def last_reply(state: dict) -> str:
    return str(state["messages"][-1].content)
