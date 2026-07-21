# STYLESEED lock

디자인 드리프트 방지용 잠금. UI 작업 시 이 값을 따른다. (StyleSeed **toss** 스킨 — lx-raize 패턴)

```yaml
skin: toss
accent: '#3182F6'        # Toss blue (src/styles/theme.css --color-accent)
accent_hover: '#1B64DA'
ink: '#191F28'           # 강조 텍스트
ink_soft: '#4E5968'      # 보조 텍스트 (순수 #000 금지)
line: '#E5E8EB'
canvas: '#F2F4F6'
radius: 12px             # rounded-ss
dark: on                 # @media(prefers-color-scheme) + [data-theme] 둘 다 (theme.css)
motion: minimal          # CSS 트랜지션/펄스만. Framer 미도입
font: Pretendard (CDN)   # 한글이 주 콘텐츠
stack: Vite + React 19 + TS + Tailwind v4 + à la carte + lucide-react
```

## 규칙 (StyleSeed 74룰 중 핵심)
- **한 accent(Toss blue)만**, 나머지는 그레이스케일.
- 텍스트는 `--color-ink` / `--color-ink-soft` (순수 #000 금지).
- 그림자는 ≤8% 불투명, 한 방향.
- 로딩 / 에러(SSE `error`) / 빈 상태를 실제로 렌더.
- 8px 그리드. 컴포넌트는 필요분만 룰 따라 생성(48 라이브러리 통짜 도입 안 함).

## 상태 표시 — 이모지 금지, 아이콘+라벨+상태색
5축 채점 배지(warn/danger 구분은 어느 축이 실패했나로 프론트가 판단):

| 상태 | 조건 | lucide | 색 | 라벨 |
|---|---|---|---|---|
| 통과 | `tags[축] === true` | `Check` | `--color-good` | 통과 |
| 미달 | 품질축(구체성·기여도·문제해결·정량성) false | `Minus` | `--color-warn` | 미달 |
| 차단 | 과장허위 false | `X` | `--color-danger` | 차단 |
| 채점 중 | 루프 진행, tag 미정착 | 중립 펄스 | `--color-ink-faint` | 채점 중 |

색 단독 금지 — 아이콘+라벨 병기(a11y). 품질게이트: `/ss-review`·`/ss-score`(≥80)·`/ss-a11y`·`/ss-feedback`.
