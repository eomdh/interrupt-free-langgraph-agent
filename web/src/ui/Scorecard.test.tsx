// @vitest-environment jsdom
/**
 * 채점표가 상태를 **색 말고도** 말하는가.
 *
 * ADR 0007 이 잠근 규칙이라 라벨이 실제로 렌더되는지를 본다. 아이콘만 있고
 * 라벨이 없으면 색각 이상에서 통과와 미달이 같아 보인다.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Scorecard } from './Scorecard';
import { AXES, type Tags } from '@/core/types';

afterEach(cleanup);

const passing = (over: Partial<Tags> = {}): Tags => ({
  구체성: true,
  기여도: true,
  문제해결: true,
  정량성: true,
  과장허위: true,
  ...over,
});

describe('축 표시', () => {
  it('다섯 축을 모두 이름과 함께 보여준다', () => {
    render(<Scorecard tags={passing()} />);

    for (const axis of AXES) {
      expect(screen.getByText(axis)).toBeTruthy();
    }
  });

  it('통과는 라벨로도 드러난다 — 색 단독 금지', () => {
    render(<Scorecard tags={passing()} />);

    expect(screen.getAllByText('통과')).toHaveLength(AXES.length);
  });

  it('품질 축 미달은 "미달", 과장허위 미달은 "차단"으로 구분한다', () => {
    render(<Scorecard tags={passing({ 정량성: false, 과장허위: false })} />);

    expect(screen.getByText('미달')).toBeTruthy();
    expect(screen.getByText('차단')).toBeTruthy();
  });

  it('채점 전에는 다섯 축 모두 "채점 중"', () => {
    render(<Scorecard tags={null} />);

    expect(screen.getAllByText('채점 중')).toHaveLength(AXES.length);
  });

  it('이모지를 쓰지 않는다', () => {
    const { container } = render(<Scorecard tags={passing({ 과장허위: false })} />);

    // 배지는 lucide SVG 로만 그린다 — 텍스트에 그림문자가 섞이면 안 된다.
    expect(container.querySelectorAll('svg')).toHaveLength(AXES.length);
    expect(container.textContent ?? '').not.toMatch(/\p{Extended_Pictographic}/u);
  });
});
