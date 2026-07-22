// @vitest-environment jsdom
/**
 * 입력창의 계약.
 *
 * 핵심은 하나 — **칩이 전송 후에 남지 않는다.** 남으면 다음 평범한 메시지에도
 * 지난 의도가 실려 동의 게이트가 다시 열린다. 백엔드
 * `test_액션_칩을_생략하면_지난_칩이_남지_않는다` 와 짝을 이루는 검사다(ADR 0002).
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
    chip: (label: string) => screen.getByRole('button', { name: label }) as HTMLButtonElement,
  };
}

describe('의도 칩', () => {
  it('누른 칩의 의도가 전송에 실린다', async () => {
    const { user, onSend, box, send, chip } = setup();

    await user.click(chip('초안 써줘'));
    await user.type(box, '초안 부탁해');
    await user.click(send);

    expect(onSend).toHaveBeenCalledWith('초안 부탁해', 'write_now');
  });

  it('전송하면 선택이 풀린다 — 다음 턴에는 null 이 실린다', async () => {
    const { user, onSend, box, send, chip } = setup();

    await user.click(chip('초안 써줘'));
    await user.type(box, '초안 부탁해');
    await user.click(send);

    // 칩을 다시 안 눌렀다. 지난 칩이 남아 있으면 안 된다.
    await user.type(box, '고마워');
    await user.click(send);

    expect(onSend).toHaveBeenNthCalledWith(2, '고마워', null);
    expect(chip('초안 써줘').getAttribute('aria-pressed')).toBe('false');
  });

  it('같은 칩을 다시 누르면 해제된다', async () => {
    const { user, chip } = setup();

    await user.click(chip('확정'));
    expect(chip('확정').getAttribute('aria-pressed')).toBe('true');

    await user.click(chip('확정'));
    expect(chip('확정').getAttribute('aria-pressed')).toBe('false');
  });
});

describe('전송 조건', () => {
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

    expect(onSend).toHaveBeenCalledWith('결제 지연을 줄였어요', null);
  });

  it('보내고 나면 입력창이 비워진다', async () => {
    const { user, box, send } = setup();

    await user.type(box, '안녕');
    await user.click(send);

    expect(box.value).toBe('');
  });

  it('턴이 도는 중에는 잠긴다 — 매 POST 가 한 턴이다', () => {
    const { box, send, chip } = setup(true);

    expect(box.disabled).toBe(true);
    expect(send.disabled).toBe(true);
    expect(chip('초안 써줘').disabled).toBe(true);
  });
});

describe('키보드', () => {
  it('Enter 로 보낸다', async () => {
    const { user, onSend, box } = setup();

    await user.type(box, '안녕{Enter}');

    expect(onSend).toHaveBeenCalledWith('안녕', null);
  });

  it('Shift+Enter 는 줄바꿈이라 보내지 않는다', async () => {
    const { user, onSend, box } = setup();

    await user.type(box, '첫 줄{Shift>}{Enter}{/Shift}둘째 줄');

    expect(onSend).not.toHaveBeenCalled();
    expect(box.value).toContain('\n');
  });
});
