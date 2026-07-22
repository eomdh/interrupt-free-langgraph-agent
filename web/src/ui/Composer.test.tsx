// @vitest-environment jsdom
/**
 * 입력창의 계약.
 *
 * 의도를 고르는 장치는 여기 없다 — 말한 내용이 곧 의도이고 분류가 읽는다
 * (ADR 0008). 동의 버튼은 `ActionButtons` 가 따로 그린다.
 */
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { Composer } from './Composer';

afterEach(cleanup);

function setup(disabled = false) {
  const user = userEvent.setup();
  const onSend = vi.fn();
  render(<Composer onSend={onSend} disabled={disabled} />);

  return {
    user,
    onSend,
    box: screen.getByLabelText('메시지') as HTMLTextAreaElement,
    send: screen.getByRole('button', { name: '보내기' }) as HTMLButtonElement,
  };
}

describe('전송 조건', () => {
  it('적은 내용을 그대로 보낸다', async () => {
    const { user, onSend, box, send } = setup();

    await user.type(box, '결제 지연을 줄였어요');
    await user.click(send);

    expect(onSend).toHaveBeenCalledWith('결제 지연을 줄였어요');
  });

  it('공백뿐인 입력은 보내지 않는다', async () => {
    const { user, onSend, box, send } = setup();

    await user.type(box, '   ');

    expect(send.disabled).toBe(true);
    await user.click(send);
    expect(onSend).not.toHaveBeenCalled();
  });

  it('앞뒤 공백을 털어서 보낸다', async () => {
    const { user, onSend, box, send } = setup();

    await user.type(box, '  결제 지연을 줄였어요  ');
    await user.click(send);

    expect(onSend).toHaveBeenCalledWith('결제 지연을 줄였어요');
  });

  it('보내고 나면 입력창이 비워진다', async () => {
    const { user, box, send } = setup();

    await user.type(box, '안녕');
    await user.click(send);

    expect(box.value).toBe('');
  });

  it('턴이 도는 중에는 잠긴다 — 매 POST 가 한 턴이다', () => {
    const { box, send } = setup(true);

    expect(box.disabled).toBe(true);
    expect(send.disabled).toBe(true);
  });
});

describe('키보드', () => {
  it('Enter 로 보낸다', async () => {
    const { user, onSend, box } = setup();

    await user.type(box, '안녕{Enter}');

    expect(onSend).toHaveBeenCalledWith('안녕');
  });

  it('Shift+Enter 는 줄바꿈이라 보내지 않는다', async () => {
    const { user, onSend, box } = setup();

    await user.type(box, '첫 줄{Shift>}{Enter}{/Shift}둘째 줄');

    expect(onSend).not.toHaveBeenCalled();
    expect(box.value).toContain('\n');
  });
});
