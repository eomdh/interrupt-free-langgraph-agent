"""interrupt() 없이 짠 LangGraph 대화 에이전트."""

__all__ = ["build_graph"]


def __getattr__(name: str):
    # graph 모듈이 langgraph를 끌어오므로 필요할 때만 import 한다.
    if name == "build_graph":
        from agent.graph import build_graph

        return build_graph
    raise AttributeError(name)
