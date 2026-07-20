"""재작성 카운터 reducer — 리셋이 되는가.

원본에서 실제로 밟은 함정의 회귀 테스트. `operator.add`로 카운터를 만들면
값을 **줄일 수 없어서**, 항목이 바뀔 때 재작성 횟수가 안 돌아간다. 그러면
두 번째 항목이 시작부터 상한에 걸린 채로 출발한다.
"""

import operator

from agent.intents import MAX_REVISE
from agent.state import reset_or_add


def test_증가한다():
    assert reset_or_add(0, 1) == 1
    assert reset_or_add(2, 1) == 3


def test_None이_오면_0으로_리셋된다():
    """이게 `operator.add`로는 안 되는 부분이다."""
    assert reset_or_add(2, None) == 0


def test_리셋_후_다시_증가할_수_있다():
    count = reset_or_add(MAX_REVISE, None)
    assert reset_or_add(count, 1) == 1


def test_operator_add로는_리셋이_불가능하다는_사실():
    """왜 커스텀 reducer가 필요한지를 못 박아 둔다.

    `operator.add`는 어떤 값을 줘도 현재 값 아래로 내려갈 수 없다.
    항목 전환 시 카운터가 상한에 남아 있으면 다음 초안이 한 번도
    다시 쓰이지 못한다.
    """
    stuck = MAX_REVISE
    assert operator.add(stuck, 0) == MAX_REVISE
    assert operator.add(stuck, 1) > MAX_REVISE
