/**
 * 동의 버튼 — 서버가 "지금 가능하다"고 알려준 것만 그린다.
 *
 * 상시 칩이 아니라 **문맥 버튼**이다. 입력창과 경쟁하는 모드 선택이 아니라
 * 에이전트가 제안한 것에 대한 응답이라, *칩을 눌러 놓고 반대되는 말을 쓰면
 * 어느 쪽이 이기나* 하는 충돌이 아예 생기지 않는다(ADR 0009).
 *
 * 무엇을 그릴지 화면이 정하지 않는다. 정하는 순간 제안하는 것과 서버가
 * 허용하는 것이 갈라져서, 눌러도 아무 일이 없는 버튼이 생긴다.
 */
import type { Intent } from '@/core/types';

const KNOWN: readonly { intent: Intent; label: string }[] = [
  { intent: 'write_now', label: '초안 써주세요' },
  { intent: 'proceed', label: '이대로 확정' },
  { intent: 'revise', label: '다시 써주세요' },
];

interface Props {
  actions: Intent[];
  /** 누른 문구가 그대로 사용자 발화가 된다 — 대화에 흔적이 남아야 한다. */
  onPick: (text: string, intent: Intent) => void;
  disabled?: boolean;
}

export function ActionButtons({ actions, onPick, disabled = false }: Props) {
  // 서버가 준 순서를 따른다. 모르는 라벨은 그리지 않는다.
  const shown = actions
    .map((intent) => KNOWN.find((known) => known.intent === intent))
    .filter((known) => known !== undefined);

  if (shown.length === 0) return null;

  return (
    // biome-ignore lint/a11y/useSemanticElements: fieldset 은 폼 의미라 안 맞는다. 버튼 묶음엔 role=group 이 정확하다
    <div className="flex flex-wrap gap-2" role="group" aria-label="다음 동작">
      {shown.map(({ intent, label }, index) => (
        <button
          key={intent}
          type="button"
          disabled={disabled}
          onClick={() => onPick(label, intent)}
          className={[
            'rounded-ss px-3 py-1.5 text-sm transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
            // accent 는 하나만 — 첫 제안이 주 동작이고 나머지는 곁이다.
            index === 0
              ? 'bg-accent font-medium text-white hover:bg-accent-hover'
              : 'border border-line bg-surface text-ink-soft hover:border-ink-faint',
          ].join(' ')}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
