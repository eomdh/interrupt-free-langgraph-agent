/**
 * 액션 칩 — 분류를 건너뛰고 의도를 직접 실어 보낸다.
 *
 * 칩을 눌러도 **상태 게이트는 똑같이 통과해야 한다.** 의도는 목적지를 제안할
 * 뿐이고 통과는 서버가 정한다(ADR 0002). 그래서 여기서는 무엇을 보낼지만 고른다.
 */
import type { Intent } from '@/core/types';

const CHIPS: readonly { intent: Intent; label: string; hint: string }[] = [
  { intent: 'provide_info', label: '성과 얘기', hint: '한 일을 서술합니다' },
  { intent: 'write_now', label: '초안 써줘', hint: '초안 생성에 동의합니다' },
  { intent: 'revise', label: '고쳐줘', hint: '초안을 다시 씁니다' },
  { intent: 'proceed', label: '확정', hint: '이대로 확정합니다' },
];

interface Props {
  value: Intent | null;
  onChange: (intent: Intent | null) => void;
  disabled?: boolean;
}

export function IntentChips({ value, onChange, disabled = false }: Props) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="의도 선택">
      {CHIPS.map(({ intent, label, hint }) => {
        const selected = value === intent;
        return (
          <button
            key={intent}
            type="button"
            aria-pressed={selected}
            title={hint}
            disabled={disabled}
            onClick={() => onChange(selected ? null : intent)}
            className={[
              'rounded-full border px-3 py-1 text-sm transition-colors',
              'disabled:cursor-not-allowed disabled:opacity-50',
              selected
                ? 'border-accent bg-accent-soft text-accent'
                : 'border-line bg-surface text-ink-soft hover:border-ink-faint',
            ].join(' ')}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
