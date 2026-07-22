"""진행 스트림 투영.

한 번의 `astream` 실행을 SSE 프레임으로 옮긴다. 여전히 매 POST=1턴이다 —
지속 연결이 아니라, 그 한 턴이 노드를 밟는 과정을 중계하고 END에서 닫는다(ADR 0001).

규칙은 하나다: **진행 이벤트는 초안 본문을 절대 싣지 않는다.**
`stream_mode="updates"`는 `draft` 노드의 델타에 원본 초안을 담아 내놓는데(그게
함정이다), 그대로 흘려보내면 `blocked`로 막을 초안이 이미 스트림으로 새어나간 뒤라
ADR 0005가 무의미해진다. `api.py`의 `ThreadView`가 `draft`를 일부러 뺀 것과 똑같은
함정이 여기 스트림 계층에 다시 생긴다.

그래서 화이트리스트로 간다 — 진행 이벤트는 노드명·순번·채점 라벨 같은 **메타데이터만**
싣고, 자유 텍스트는 하나도 싣지 않는다. 사용자에게 닿는 유일한 초안은 `deliver`가
`AIMessage`로 바꾼 것뿐이고, 그건 최종 `done` 이벤트의 `ThreadView`로 나간다(ADR 0006).
"""

import json

#: 초안 루프에 속한 노드 — 완료를 `loop` 이벤트로 알린다. 나머지는 `node` 이벤트.
LOOP_NODES = ("draft", "tag")

#: 진행으로 치지 않는 노드.
#:
#: `classify`는 어디로 갈지 정하는 내부 단계라, 사용자가 보는 "무슨 일을 하는
#: 중인가"에 해당하지 않는다. 내보내면 매 턴 첫머리에 의미 없는 깜빡임이 하나씩
#: 생기고, 스텝퍼가 매핑할 단계도 없다. 그래서 스트림 계약(ADR 0006)에서 뺀다.
HIDDEN_NODES = frozenset({"classify"})


def sse_frame(event: str, data: dict) -> str:
    """SSE 프레임 하나. `data`는 JSON 한 줄로 싣는다."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def project_update(node: str, delta: dict, *, seq: int, attempt: int) -> str:
    """`{node: delta}` 청크 하나를 안전한 SSE 프레임으로 옮긴다.

    화이트리스트 방식이다 — 아는 필드만 통과시키고 나머지 델타는 버린다. 특히
    `delta["draft"]`는 절대 싣지 않는다. 새 노드가 새 필드를 반환해도 기본이
    '안 내보냄'이라, 누출 경로가 조용히 열리지 않는다(ADR 0005·0006).

    `attempt`는 이번 턴에서 `draft`가 몇 번째로 도는지다. `state["revise_count"]`를
    그대로 옮기지 않는다 — 그 값은 델타가 아니라 리듀서 뒤에 있어서, 세는 쪽이
    리듀서 로직을 흉내 내야 한다. 스트림에서 `draft` 노드가 나온 횟수가 곧 시도
    횟수라 그걸 센다.
    """
    if node in LOOP_NODES:
        data: dict = {"node": node, "seq": seq, "attempt": attempt}
        if "tags" in delta:
            data["tags"] = delta["tags"]  # bool 5축뿐 — 안전하다
        return sse_frame("loop", data)
    return sse_frame("node", {"node": node, "seq": seq})
