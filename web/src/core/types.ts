/**
 * 백엔드 계약. 서버가 정하는 모양을 옮겨 적은 것이다 — 여기서 창작하면 계약이 갈라진다.
 *
 * 출처: `agent/intents.py`(축·의도·노드) · `agent/api.py`(ThreadView) ·
 * `agent/stream.py`(SSE 이벤트).
 */

/** 채점 5축. 앞의 넷은 "더 좋게"를, 과장허위만 "넘지 마라"를 잰다(ADR 0004). */
export const AXES = ['구체성', '기여도', '문제해결', '정량성', '과장허위'] as const;
export type Axis = (typeof AXES)[number];

/** 다른 넷과 성격이 다르다 — 안 걷히면 초안 자체가 막힌다(ADR 0005). */
export const HALLUCINATION_AXIS: Axis = '과장허위';

/** 5축 채점 결과. 서버는 언제나 다섯 축을 다 채워 보낸다. */
export type Tags = Record<Axis, boolean>;

/** 그래프 노드. 진행 이벤트가 이 이름으로 온다. */
export const NODES = [
  'onboard',
  'analyze',
  'interview',
  'propose_draft',
  'draft',
  'tag',
  'deliver',
  'finalize',
  'blocked',
  'respond',
] as const;
export type NodeName = (typeof NODES)[number];

/** 액션 칩이 실어 보내는 의도. 안 누르면 매 턴 null 로 보낸다(ADR 0002). */
export type Intent =
  | 'provide_info'
  | 'set_questions'
  | 'write_now'
  | 'revise'
  | 'proceed'
  | 'chitchat'
  | 'continue';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * 스레드의 현재 모습.
 *
 * **초안 본문이 없다** — 초안은 `deliver` 가 메시지로 바꾼 것만 사용자에게
 * 닿는다(ADR 0005). 프로필·성과 목록은 *입력*이라 애초에 안 내려온다.
 */
export interface ThreadView {
  thread_id: string;
  messages: Message[];
  tags: Tags | null;

  /**
   * 지금 눌러서 의미가 있는 동의 액션. 서버가 라우터의 게이트에서 유도해 준다.
   *
   * 화면이 스스로 정하지 않는다 — 정하는 순간 제안하는 것과 서버가 허용하는
   * 것이 갈라져서, 눌러도 아무 일이 없는 버튼이 생긴다.
   */
  actions: Intent[];
}

/** `event: node` — 라우터가 고른 노드가 끝났다. */
export interface NodeEvent {
  node: NodeName;
  /** 한 턴 안의 순번. 스트림이 순서를 보장하므로 리듀서는 안 쓴다(계약·디버그용). */
  seq: number;
}

/** `event: loop` — draft⇄tag 자율 루프가 한 칸 돌았다. */
export interface LoopEvent {
  node: 'draft' | 'tag';
  seq: number;
  /** 이번 턴에서 draft 가 몇 번째로 돈 것인가(ADR 0006). */
  attempt: number;
  /** `tag` 노드일 때만 온다. bool 뿐이라 진행 이벤트에 실려도 안전하다. */
  tags?: Tags;
}

/** `event: error` — 실행 중 예외. 스트림이 열린 뒤라 상태코드를 못 바꾼다. */
export interface ErrorEvent {
  detail: string;
}
