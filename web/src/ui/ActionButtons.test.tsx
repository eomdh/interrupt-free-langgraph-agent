// @vitest-environment jsdom
/**
 * 동의 버튼.
 *
 * 여기서 잡는 것은 **화면이 스스로 제안하지 않는다**는 것이다. 서버가 준
 * 목록만 그린다 — 그래야 제안하는 것과 서버가 허용하는 것이 안 갈라진다(ADR 0009).
 */
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Intent } from '@/core/types';
import { ActionButtons } from './ActionButtons';

afterEach(cleanup);

function setup(actions: Intent[], disabled = false) {
  const user = userEvent.setup();
  const onPick = vi.fn();
  const { container } = render(
    <ActionButtons actions={actions} onPick={onPick} disabled={disabled} />,
  );
  return { user, onPick, container };
}

describe('무엇을 그리나', () => {
  it('서버가 준 것만 그린다', () => {
    setup(['write_now']);

    expect(screen.getByRole('button', { name: '초안 써주세요' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: '이대로 확정' })).toBeNull();
  });

  it('줄 것이 없으면 아무것도 안 그린다', () => {
    const { container } = setup([]);
    expect(container.innerHTML).toBe('');
  });

  it('모르는 의도는 무시한다 — 계약이 늘어도 화면이 안 깨진다', () => {
    const { container } = setup(['provide_info', 'chitchat', 'continue']);
    expect(container.innerHTML).toBe('');
  });

  it('서버가 준 순서를 지킨다', () => {
    setup(['proceed', 'revise']);

    const labels = screen.getAllByRole('button').map((button) => button.textContent);
    expect(labels).toEqual(['이대로 확정', '다시 써주세요']);
  });
});

describe('누르면', () => {
  it('버튼 문구가 그대로 사용자 발화가 된다', async () => {
    const { user, onPick } = setup(['write_now']);

    await user.click(screen.getByRole('button', { name: '초안 써주세요' }));

    // 대화에 흔적이 남아야 나중에 읽었을 때 무슨 일이 있었는지 안다.
    expect(onPick).toHaveBeenCalledWith('초안 써주세요', 'write_now');
  });

  it('턴이 도는 중에는 못 누른다', () => {
    setup(['proceed', 'revise'], true);

    for (const button of screen.getAllByRole('button')) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
