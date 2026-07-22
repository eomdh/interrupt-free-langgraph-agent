/**
 * 화면 상태와 그 전이. **순수 함수다** — DOM 도 네트워크도 없다.
 *
 * 백엔드가 라우터·게이트를 순수 함수로 두고 테스트로 잠근 것과 같은 이유다.
 * SSE 를 흉내 낼 필요 없이 이벤트 시퀀스만 넣으면 전이가 전부 검증된다.
 *
 * 불변식: `streaming === false` 이면 활성 표시(`activeNode`·`activePhase`)가 없다.
 * 진행 중일 때만 무언가 도는 것으로 보여야 한다.
 */
import type { ErrorEvent, LoopEvent, Message, NodeEvent, NodeName, Tags, ThreadView } from './types';

/** 화면이 보여주는 큰 단계. 노드보다 굵다 — 스텝퍼 레일이 이 단위다. */
export type Phase = 'onboard' | 'gather' | 'draft' | 'deliver';
export const PHASES: readonly Phase[] = ['onboard', 'gather', 'draft', 'deliver'];

/** 노드 → 단계. `respond`(잡담)는 진행이 아니라서 단계를 안 올린다. */
const NODE_PHASE: Record<NodeName, Phase | null> = {
  onboard: 'onboard',
  analyze: 'gather',
  interview: 'gather',
  propose_draft: 'gather',
  draft: 'draft',
  tag: 'draft',
  deliver: 'deliver',
  finalize: 'deliver',
  blocked: 'deliver',
  respond: null,
};

export function phaseOfNode(node: NodeName): Phase | null {
  return NODE_PHASE[node];
}

function rank(phase: Phase | null): number {
  return phase === null ? -1 : PHASES.indexOf(phase);
}

/** 레일은 되감기지 않는다 — 잡담하러 갔다고 진행이 사라지면 안 된다. */
function furthestOf(current: Phase | null, next: Phase | null): Phase | null {
  return rank(next) > rank(current) ? next : current;
}

export interface AgentState {
  threadId: string;
  /** 정착된 대화. `done` 이 서버 기준으로 통째로 갈아끼운다. */
  messages: Message[];
  /** 정착된 채점. */
  tags: Tags | null;

  /** 이번 턴이 도는 중인가. */
  streaming: boolean;
  /** 막 끝난 노드 — 진행 중일 때만 값이 있다. */
  activeNode: NodeName | null;
  /** 그 노드의 단계. `respond` 면 null. */
  activePhase: Phase | null;
  /** 레일이 칠할 최대 도달 단계. 턴을 넘어 누적된다. */
  furthest: Phase | null;
  /** 이번 턴의 draft 시도 횟수(ADR 0006). */
  attempt: number;
  /** 루프 도중 흘러온 채점. `done` 에서 `tags` 로 정착한다. */
  liveTags: Tags | null;
  error: string | null;
}

export function initialState(threadId: string): AgentState {
  return {
    threadId,
    messages: [],
    tags: null,
    streaming: false,
    activeNode: null,
    activePhase: null,
    furthest: null,
    attempt: 0,
    liveTags: null,
    error: null,
  };
}

/**
 * 화면이 보여줄 채점.
 *
 * 루프가 도는 동안에는 흘러온 값을, 턴이 끝나면 정착값을 쓴다. 덕분에 채점표가
 * 재작성 중에도 살아 움직이고, `done` 이후엔 서버가 정한 값으로 수렴한다.
 */
export function visibleTags(state: AgentState): Tags | null {
  return state.liveTags ?? state.tags;
}

export type AgentAction =
  | { type: 'hydrate'; view: ThreadView }
  | { type: 'turnStart'; text: string }
  | { type: 'node'; data: NodeEvent }
  | { type: 'loop'; data: LoopEvent }
  | { type: 'done'; data: ThreadView }
  | { type: 'error'; data: ErrorEvent };

export function applyEvent(state: AgentState, action: AgentAction): AgentState {
  switch (action.type) {
    case 'hydrate': {
      // 새로고침 복원(ADR 0001). 레일은 **아는 만큼만** 칠한다 — 채점이 있으면
      // 초안까지 갔던 것이고, 메시지만 있으면 온보딩까지다. `deliver` 도달 여부는
      // ThreadView 로 판별할 수 없어(초안 본문이 안 온다) 보수적으로 둔다.
      // 서버 문구를 문자열로 뒤져 알아내는 건 백엔드 카피에 묶이는 짓이라 안 한다.
      const { messages, tags, thread_id } = action.view;
      return {
        ...initialState(thread_id),
        messages,
        tags,
        furthest: tags ? 'draft' : messages.length > 0 ? 'onboard' : null,
      };
    }

    case 'turnStart':
      // 사용자 메시지를 먼저 붙여 화면이 즉시 반응하게 한다. `done` 이 서버
      // 기준으로 통째로 갈아끼우므로 중복으로 남지 않는다.
      return {
        ...state,
        messages: [...state.messages, { role: 'user', content: action.text }],
        streaming: true,
        activeNode: null,
        activePhase: null,
        attempt: 0,
        liveTags: null,
        error: null,
      };

    case 'node': {
      const phase = phaseOfNode(action.data.node);
      return {
        ...state,
        activeNode: action.data.node,
        activePhase: phase,
        furthest: furthestOf(state.furthest, phase),
      };
    }

    case 'loop':
      return {
        ...state,
        activeNode: action.data.node,
        activePhase: 'draft',
        furthest: furthestOf(state.furthest, 'draft'),
        attempt: action.data.attempt,
        // `draft` 이벤트에는 tags 가 없다 — 그때는 직전 채점을 유지한다.
        liveTags: action.data.tags ?? state.liveTags,
      };

    case 'done':
      // 서버가 정착시킨 모습으로 갈아끼우고 진행 표시를 내린다.
      return {
        ...state,
        messages: action.data.messages,
        tags: action.data.tags,
        streaming: false,
        activeNode: null,
        activePhase: null,
        liveTags: null,
      };

    case 'error':
      // 스트림이 열린 뒤의 실패. 낙관적으로 붙인 사용자 메시지는 남겨두고
      // 무엇이 터졌는지 보여준다 — 연결을 매단 채로 두지 않는다(ADR 0006).
      return {
        ...state,
        streaming: false,
        activeNode: null,
        activePhase: null,
        error: action.data.detail,
      };
  }
}
