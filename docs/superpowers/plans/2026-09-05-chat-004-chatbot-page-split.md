# [CHAT-004] 챗봇 페이지 분할과 응답 파서 단일화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1,721줄짜리 챗봇 페이지에서 파서와 SSE 수신과 세션 관리와 음성 입력을 각각 별도 모듈로 떼어내고, 메시지 렌더를 메모이제이션된 컴포넌트로 바꿔 스트리밍 중의 전체 재파싱을 없앱니다.

**Architecture:** 순수 함수(파서, 스트림 이벤트 적용)를 먼저 떼어내 테스트 가능한 표면을 만들고, 그 위에 훅 세 개(`useChatStream`, `useChatSessions`, `useSpeechInput`)와 컴포넌트 하나(`ChatMessage`)를 얹습니다. 페이지는 이 조각들을 조립하고 JSX 를 그리는 역할만 남깁니다. 화면에 보이는 동작은 한 곳을 빼고 전부 그대로이며, 그 한 곳은 아래 「3번 결함」이 고쳐지는 자리입니다.

**Tech Stack:** Next.js 16.3.4 (App Router), React 19.2.4, TypeScript, vitest + @testing-library/react

**Spec:** `docs/dev-cycle/audits/AUDIT-CHAT.md` §2.2, §4.1, §5.1 그리고 `docs/dev-cycle/TODO.md` 의 `[CHAT-004]` 항목

---

## Global Constraints

- 저장소의 개발 사이클 규정이 커밋 시점을 정합니다. **각 Task 끝의 「Commit」 단계를 그대로 실행하지 마십시오.** `.claude/skills/dev-cycle/SKILL.md` 의 [3] 검증 5번과 [4] 마감 3번이 커밋을 만드는 유일한 자리입니다. Task 마다 커밋하면 사이클의 커밋 구성이 무너집니다. 아래 각 Task 의 마지막 단계는 「검증만 하고 커밋하지 않는다」로 읽으십시오.
- `frontend/src/app/chatbot/page.regression-chat-001.test.tsx` (156줄, 검사 3건)를 **한 줄도 고치지 않고** 통과시켜야 합니다.
- `page.tsx` 의 기본 내보내기는 `export default function ChatbotPage()` 이며 경로와 이름을 바꾸지 않습니다. App Router 가 이 파일을 라우트로 씁니다.
- 새 의존성을 추가하지 않습니다. 새 테스트 프레임워크나 픽스처 계층을 들이지 않습니다.
- 검증 명령 세 가지: `cd frontend && npx vitest run`, `cd frontend && npm run type-check`, `source venv/bin/activate && pytest`. `npm run test` 는 감시 모드라 끝나지 않으므로 쓰지 않습니다.
- `~/.claude/`, `~/.agents/`, `.claude/skills/`, `agents/` 아래의 파일을 읽거나 실행하지 않습니다.
- `.env` 로 시작하는 파일을 열어야 하면 변수 이름과 값의 유무만 확인하고 값 자체를 문서에 옮기지 않습니다.

---

## 배경 — 지금 무엇이 잘못되어 있는가

### 1. 파서가 렌더마다 전체 메시지를 다시 훑는다

`page.tsx:1363` 의 `messages.map` 콜백 안에서 `extractSuggestions` 를 부르고, `:1466` 에서 `preprocessMarkdown` 을 부릅니다. 두 함수는 합쳐서 정규식 치환을 스무 번 넘게 실행합니다. 스트리밍 델타가 도착할 때마다 `setMessages` 가 배열을 새로 만들고, 그러면 대화에 쌓인 **모든** 메시지가 다시 파싱됩니다. 대화가 길수록 글자 하나 도착할 때의 비용이 커집니다.

`map` 콜백 안에서는 React 훅을 부를 수 없습니다. 그래서 메모이제이션하려면 메시지 하나를 그리는 컴포넌트를 반드시 분리해야 합니다. 이것이 Task 2 의 존재 이유입니다.

### 2. 백엔드가 이미 나눠 보낸 것을 프런트가 다시 해석한다

`chatbot/response_flow_stream.py:48-67` 과 `:127-156` 이 `reasoning_chunk` 와 `answer_chunk` 를 서로 다른 이벤트로 보냅니다. `chunk` 는 `answer_chunk` 와 같은 값을 싣는 하위 호환 필드입니다. 그런데 프런트는 `extractSuggestions` 안에서 `reasonStartRegex`(`:187`), `reasonEndRegex`(`:188`), `reasoningHeaderRegex`(`:230`) 로 같은 헤더를 한 번 더 찾습니다. 헤더 표기를 바꾸면 파이썬과 타입스크립트 두 파일을 동시에 고쳐야 하고, 한쪽만 고치면 추론이 답변에 섞이거나 답변이 통째로 숨습니다.

**이 fallback 파서를 지울 수는 없습니다.** 히스토리에서 복원한 메시지와 비스트리밍 JSON 응답에는 여전히 헤더가 섞인 원문이 옵니다. 지울 것이 아니라 **적용 범위를 정확히 좁히는 것**이 이번 작업입니다.

### 3. fallback 파서의 판정 조건에 구멍이 있다

`page.tsx:173` 의 판정이 이렇습니다.

```ts
const hasStreamReasoning = typeof streamReasoning === 'string' && streamReasoning.length > 0;
```

추론이 없는 스트리밍 응답에서는 `reasoning` 이 빈 문자열이므로 `length > 0` 이 거짓이 되고, fallback 파서가 켜집니다. 그러면 모델이 답변 본문에 「[추론 과정]」이라는 문구를 쓰기만 해도 그 뒤가 통째로 추론 영역으로 빨려 들어가 사용자가 답변을 볼 수 없게 됩니다.

올바른 판정 기준은 「이 메시지가 SSE 로 받은 것인가」입니다. 세 경로를 대조하면 값이 정확히 갈립니다.

| 메시지의 출처 | `reasoning` 필드 | fallback 파싱이 필요한가 |
|---|---|---|
| SSE 스트리밍 (`page.tsx:661` 이 `reasoning: ""` 으로 초기화) | 언제나 문자열 | 필요 없음. 백엔드가 이미 나눔 |
| 히스토리 복원 (`chatbot/storage_sqlite_history.py:388` 이 `{role, parts}` 만 돌려줌) | `undefined` | 필요함 |
| 비스트리밍 JSON 응답 (`page.tsx:800`) | `undefined` | 필요함 |

그러므로 `typeof streamReasoning === 'string'` 하나면 됩니다. **길이 조건만 지우면 고쳐집니다.**

### 4. 한 파일이 여덟 가지 책임을 진다

감사가 지적한 영향은 두 가지입니다. SSE 분기 한 곳을 고치려 해도 1,721줄을 훑어야 한다는 것과, 리렌더 범위가 파일 전체가 되어 1번의 비용을 키운다는 것입니다.

---

## File Structure

### 새로 만드는 파일

| 경로 | 책임 | 대략 줄 수 |
|---|---|---|
| `frontend/src/app/chatbot/chatMessageParser.ts` | `Message` 타입과 순수 파서 넷 | 180 |
| `frontend/src/app/chatbot/chatMessageParser.test.ts` | 위 파서의 검사 | 130 |
| `frontend/src/app/chatbot/ChatMessage.tsx` | 메시지 한 건을 그리는 `React.memo` 컴포넌트 | 160 |
| `frontend/src/app/chatbot/useChatStream.ts` | `applyStreamEvent` 순수 함수와 SSE 수신 훅 | 210 |
| `frontend/src/app/chatbot/useChatStream.test.ts` | `applyStreamEvent` 의 검사 | 110 |
| `frontend/src/app/chatbot/useChatSessions.ts` | 세션 목록·현재 세션·메시지 상태와 조회 | 150 |
| `frontend/src/app/chatbot/useSpeechInput.ts` | 음성 인식 타입과 녹음 토글 | 130 |

### 고치는 파일

| 경로 | 무엇을 |
|---|---|
| `frontend/src/app/chatbot/page.tsx` | 옮긴 코드를 지우고 새 모듈을 조립. 1,721줄 → 약 1,050줄 |
| `frontend/src/app/components/chatHelpers.ts` | `getAuthHeaders` 를 받아들임 |

### 건드리지 않는 파일

`frontend/src/app/chatbot/page.regression-chat-001.test.tsx` 와 `frontend/src/app/components/chatHelpers.test.ts` 는 고치지 않습니다. 앞의 것은 이번 리팩터링이 동작을 바꾸지 않았음을 증명하는 기준선입니다.

### 이번 범위에서 제외하는 것 — 명시적으로

**모달 다섯 종과 사이드바 두 벌은 분리하지 않습니다.** 그것까지 옮기면 `page.tsx` 가 400줄대로 내려가겠지만, 항목의 체크박스가 정한 것은 위 다섯 가지이고 감사가 지적한 두 영향은 그 다섯으로 해소됩니다. 작업이 끝나도 `page.tsx` 는 1,050줄 안팎으로 남으며, 그중 대부분이 JSX 입니다. 이것을 결함으로 보지 않습니다. 남은 분리가 필요하다고 관찰되면 그때 별도 항목을 세웁니다.

---

## Task 1: 파서를 순수 모듈로 떼어내고 판정 구멍을 막는다

**Files:**
- Create: `frontend/src/app/chatbot/chatMessageParser.ts`
- Create: `frontend/src/app/chatbot/chatMessageParser.test.ts`
- Modify: `frontend/src/app/chatbot/page.tsx` (19~25, 78~100, 111~244 를 지우고 import 로 대체)

**Interfaces:**
- Consumes: 없음. 첫 Task 입니다
- Produces:
  - `export interface Message { role: 'user' | 'model'; parts: (string | { text: string })[]; timestamp?: string; isStreaming?: boolean; reasoning?: string }`
  - `export function getMessagePartText(part: Message['parts'][number] | undefined): string`
  - `export function getTurnIndicesFromMessage(messages: Message[], index: number): number[]`
  - `export function preprocessMarkdown(text: string): string`
  - `export function extractSuggestions(text: string, isStreaming?: boolean, streamReasoning?: string): { content: string; suggestions: string[]; reasoning: string }`

- [ ] **Step 1: 실패하는 검사를 쓴다**

`frontend/src/app/chatbot/chatMessageParser.test.ts` 를 새로 만듭니다. 맨 앞의 검사가 3번 결함을 겨냥합니다. `reasoning` 이 빈 문자열인 스트리밍 메시지에서 답변이 사라지면 안 됩니다.

```ts
// [CHAT-004] 챗봇 응답 파서의 회귀 검사
// 근거: docs/dev-cycle/audits/AUDIT-CHAT.md §2.2

import { describe, expect, it } from 'vitest';

import {
  extractSuggestions,
  getMessagePartText,
  getTurnIndicesFromMessage,
  preprocessMarkdown,
} from './chatMessageParser';

describe('extractSuggestions — 스트리밍 메시지의 판정', () => {
  it('추론이 비어 있는 스트리밍 응답에서도 답변을 숨기지 않는다', () => {
    // 백엔드가 reasoning_chunk 를 한 번도 보내지 않으면 reasoning 은 빈 문자열이다.
    // 그때 답변 본문에 [추론 과정] 이라는 문구가 들어 있어도 fallback 파서가
    // 켜지면 안 된다. 켜지면 그 뒤가 통째로 추론 영역으로 빨려 들어간다.
    const answer = '오늘 시장은 [추론 과정] 이라는 표현을 쓰지 않습니다. 결론은 관망입니다.';

    const result = extractSuggestions(answer, true, '');

    expect(result.content).toContain('결론은 관망입니다');
    expect(result.reasoning).toBe('');
  });

  it('추론을 실어 보낸 스트리밍 응답은 그 값을 그대로 쓴다', () => {
    const result = extractSuggestions('최종 답변입니다.', true, '먼저 수급을 봤습니다.');

    expect(result.content).toBe('최종 답변입니다.');
    expect(result.reasoning).toBe('먼저 수급을 봤습니다.');
  });
});

describe('extractSuggestions — 히스토리 메시지의 fallback 파싱', () => {
  it('헤더가 섞인 원문에서 추론과 답변을 가른다', () => {
    // 히스토리 응답에는 reasoning 필드가 없다. 그때만 헤더를 해석한다.
    const raw = '[추론 과정]\n수급을 먼저 봤습니다.\n\n[답변]\n결론은 매수입니다.';

    const result = extractSuggestions(raw, false, undefined);

    expect(result.reasoning).toContain('수급을 먼저 봤습니다');
    expect(result.content).toContain('결론은 매수입니다');
    expect(result.content).not.toContain('수급을 먼저 봤습니다');
  });

  it('[답변] 헤더가 없으면 본문을 통째로 숨기지 않는다', () => {
    const raw = '[추론 과정]\n생각만 적혀 있고 답변 헤더가 없습니다.';

    const result = extractSuggestions(raw, false, undefined);

    expect(result.reasoning).toBe('');
    expect(result.content).toContain('생각만 적혀 있고');
  });

  it('추천 질문 블록을 본문에서 떼어 목록으로 돌려준다', () => {
    const raw = '결론은 매수입니다.\n\n[추천 질문]\n1. 목표가는 얼마인가요?\n2. 손절가는요?';

    const result = extractSuggestions(raw, false, undefined);

    expect(result.content).toContain('결론은 매수입니다');
    expect(result.content).not.toContain('목표가는 얼마인가요');
    expect(result.suggestions).toEqual(['목표가는 얼마인가요?', '손절가는요?']);
  });
});

describe('preprocessMarkdown', () => {
  it('번호 목록 표시 뒤에 빈칸을 넣는다', () => {
    expect(preprocessMarkdown('1.조선주')).toBe('1. 조선주');
  });

  it('강조 표시 안쪽의 빈칸을 걷어낸다', () => {
    expect(preprocessMarkdown('** 제목 **')).toBe('**제목**');
  });

  it('짝이 맞지 않는 강조 표시를 한 줄에서 지운다', () => {
    expect(preprocessMarkdown('결론은 **매수')).toBe('결론은 매수');
  });
});

describe('getMessagePartText', () => {
  it('문자열과 객체 형태를 모두 읽는다', () => {
    expect(getMessagePartText('안녕')).toBe('안녕');
    expect(getMessagePartText({ text: '안녕' })).toBe('안녕');
    expect(getMessagePartText(undefined)).toBe('');
  });
});

describe('getTurnIndicesFromMessage', () => {
  const messages = [
    { role: 'user' as const, parts: ['질문'] },
    { role: 'model' as const, parts: ['답변'] },
  ];

  it('질문에서 부르면 질문과 답변을 함께 돌려준다', () => {
    expect(getTurnIndicesFromMessage(messages, 0)).toEqual([0, 1]);
  });

  it('답변에서 부르면 앞의 질문까지 함께 돌려준다', () => {
    expect(getTurnIndicesFromMessage(messages, 1)).toEqual([0, 1]);
  });

  it('짝이 없으면 자기 자신만 돌려준다', () => {
    expect(getTurnIndicesFromMessage([{ role: 'model' as const, parts: ['답변'] }], 0)).toEqual([0]);
  });
});
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/chatbot/chatMessageParser.test.ts`

Expected: FAIL. `Failed to resolve import "./chatMessageParser"` 가 나옵니다. 모듈이 아직 없기 때문입니다.

- [ ] **Step 3: 파서 모듈을 만든다**

`frontend/src/app/chatbot/chatMessageParser.ts` 를 새로 만듭니다. `page.tsx` 의 19~25, 78~100, 111~244 를 그대로 옮기되 **한 곳만 고칩니다.** `hasStreamReasoning` 의 길이 조건을 지웁니다.

```ts
// 챗봇 응답 텍스트를 다루는 순수 함수 모음.
// 화면 상태나 브라우저 API 에 기대지 않으므로 단위 검사로 직접 확인할 수 있다.

export interface Message {
  role: 'user' | 'model';
  parts: (string | { text: string })[];
  timestamp?: string;
  isStreaming?: boolean;
  reasoning?: string;
}

export const getTurnIndicesFromMessage = (messages: Message[], index: number): number[] => {
  const current = messages[index];
  if (!current) return [];

  const prev = messages[index - 1];
  const next = messages[index + 1];

  if (current.role === 'user' && next?.role === 'model') {
    return [index, index + 1];
  }

  if (current.role === 'model' && prev?.role === 'user') {
    return [index - 1, index];
  }

  // 비정상 히스토리 대비
  return [index];
};

export const getMessagePartText = (part: Message['parts'][number] | undefined): string => {
  if (!part) return '';
  return typeof part === 'string' ? part : part.text;
};

// Helper to fix CJK markdown issues and malformed AI output
export const preprocessMarkdown = (text: string) => {
  let processed = text;
  const removeLastUnmatchedMarker = (line: string, markerRegex: RegExp, markerLength: number): string => {
    const matches = [...line.matchAll(markerRegex)];
    if (matches.length % 2 === 1) {
      const idx = matches[matches.length - 1].index;
      if (typeof idx === 'number') {
        return line.slice(0, idx) + line.slice(idx + markerLength);
      }
    }
    return line;
  };

  // 1. Remove stray emphasis markers before ordered list starts (e.g. "****1. ")
  processed = processed.replace(/^\s*\*{3,}(?=\d+[.)]\s)/gm, '');

  // 2. Split section labels and first ordered item when they are stuck together.
  processed = processed.replace(/((?:\*\*|__)?\[[^\]\n]{1,20}\](?:\*\*|__)?)\s*(?=[1-9]\d?[.)])/g, '$1\n');

  // 3. Ensure space after ordered-list marker (e.g. "1.조선", "1.**제목**" -> "1. 조선", "1. **제목**")
  processed = processed.replace(/(?<!\d)([1-9]\d?[.)])(?=\*\*|__|[가-힣A-Za-z(])/g, '$1 ');

  // 4. Ensure emphasis opening marker is separated from previous word (opening marker only).
  // Avoid touching closing markers before punctuation (e.g. "**텍스트**:")
  processed = processed.replace(/([가-힣A-Za-z0-9])(?=(\*\*|__)\s*[가-힣A-Za-z0-9(])/g, '$1 ');

  // 5. Trim inner spaces in emphasis markers (covers both-sided or one-sided spaces).
  processed = processed.replace(/\*\*([^*\n]+)\*\*/g, (m, inner: string) => {
    const trimmed = inner.trim();
    return trimmed ? `**${trimmed}**` : m;
  });
  processed = processed.replace(/__([^_\n]+)__/g, (m, inner: string) => {
    const trimmed = inner.trim();
    return trimmed ? `__${trimmed}__` : m;
  });

  // 5-1. Remove trailing unmatched emphasis marker in a line.
  processed = processed
    .split('\n')
    .map((line) => {
      const balancedAsterisk = removeLastUnmatchedMarker(line, /(?<!\*)\*\*(?!\*)/g, 2);
      return removeLastUnmatchedMarker(balancedAsterisk, /(?<!_)__(?!_)/g, 2);
    })
    .join('\n');

  // 6. Normalize quoted emphasis wrappers: **"텍스트"** / **'텍스트'** -> **텍스트**
  processed = processed.replace(/\*\*\s*['"“”‘’]\s*([^*\n]+?)\s*['"“”‘’]\s*\*\*/g, '**$1**');
  processed = processed.replace(/__\s*['"“”‘’]\s*([^_\n]+?)\s*['"“”‘’]\s*__/g, '__$1__');

  // 7. Ensure spacing after closing emphasis marker when attached to text.
  processed = processed.replace(/(?<=\S)(\*\*|__)(?=[가-힣A-Za-z0-9])/g, '$1 ');

  // 8. Fix CJK boundary issues: "**Bold**Suffix" -> "**Bold** Suffix"
  processed = processed.replace(/\*\*([A-Za-z0-9가-힣(][^*\n]*?)\*\*([가-힣])/g, '**$1** $2');
  processed = processed.replace(/__([A-Za-z0-9가-힣(][^_\n]*?)__([가-힣])/g, '__$1__ $2');

  return processed;
};

export const extractSuggestions = (text: string, isStreaming: boolean = false, streamReasoning?: string) => {
  let processed = text;
  let suggestions: string[] = [];
  // 이 메시지가 SSE 로 온 것인지 판정한다. 스트리밍 경로는 reasoning 을 빈 문자열로
  // 초기화하므로 값이 언제나 문자열이고, 히스토리 복원과 비스트리밍 JSON 응답은
  // reasoning 자체가 없다. 길이를 조건에 넣으면 추론 없는 스트리밍 응답이 히스토리로
  // 오판정되어, 답변에 [추론 과정] 이라는 문구만 있어도 그 뒤가 통째로 숨는다.
  const hasStreamReasoning = typeof streamReasoning === 'string';
  let reasoning = hasStreamReasoning ? streamReasoning : "";

  const suggestionMatch = processed.match(/(?:\*\*|__)?\\*\[\s*추천\s*질문\s*\\*\](?:\*\*|__)?[\s\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');

    const lines = sugText.split('\n');
    suggestions = lines
      .map(l => l.replace(/^(?:\d+\.|\-|\*)\s*/, '').trim())
      .filter(l => l.length > 0 && !l.replace(/\*/g, '').includes('[추천 질문]'))
      .map(l => l.replace(/\*\*/g, '')); // 별표 제거
  }

  const reasonStartRegex = /(?:\*\*|__)?\**\[\s*추론\s*과정\s*\]\**(?:\*\*|__)?/i;
  const reasonEndRegex = /(?:---|___|\*\*\*|)\s*(?:\n)*\s*(?:\*\*|__)?\**\[\s*답변\s*\]\**(?:\*\*|__)?/i;

  if (!hasStreamReasoning) {
    // Fallback parser for legacy/history messages where reasoning and answer are mixed in one text.
    const startMatch = processed.match(reasonStartRegex);
    const endMatch = processed.match(reasonEndRegex);

    if (startMatch) {
      if (endMatch) {
        // Both start and end exist (fully generated or streaming past reasoning)
        const reasoningBlock = processed.substring(startMatch.index!, endMatch.index!);
        reasoning = reasoningBlock;
        processed = processed.substring(0, startMatch.index!) + processed.substring(endMatch.index!); // Remove the reasoning block from the visible chat
      } else if (isStreaming) {
        // Stream is active, and only start tag exists. Everything after start is reasoning.
        reasoning = processed.substring(startMatch.index!);
        processed = processed.substring(0, startMatch.index!); // The visible text is empty (or whatever was before the reasoning)
      } else {
        // Non-streaming fallback:
        // If [답변] header is missing, do not hide the whole body as reasoning-only.
        // Keep full text in answer area to prevent empty final answer.
        reasoning = "";
      }
    } else if (isStreaming) {
      // FALLBACK: Aggressively match incomplete reasoning tags during early streaming
      if (!endMatch && processed.trim().length > 0 && processed.trim().length < 50) {
        // If the stream just started and starts with typical tag characters
        if (processed.trim().startsWith('*') || processed.trim().startsWith('[')) {
          reasoning = processed;
          processed = '';
        }
      }
    }
  }

  // Strip '[답변]' markers and horizontal rules just before it
  processed = processed.replace(reasonEndRegex, '');

  // FORCE newlines before numbered lists inside dense text
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  processed = processed.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');

  const reasoningHeaderRegex = /^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|__)?\s*\n?/i;
  let cleanReasoning = preprocessMarkdown(reasoning).replace(reasoningHeaderRegex, '').trim();

  // Cleanup trailing broken markdown
  if (isStreaming) {
    cleanReasoning = cleanReasoning.replace(/[\*\_\[\]]+$/, '');
  }

  // FORCE newlines before numbered lists inside dense text (e.g., "내용 2. ")
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  cleanReasoning = cleanReasoning.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');

  return { content: processed.trim(), suggestions, reasoning: cleanReasoning };
};
```

- [ ] **Step 4: 검사가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/chatbot/chatMessageParser.test.ts`

Expected: PASS, 검사 11건.

- [ ] **Step 5: `page.tsx` 에서 옮긴 코드를 지운다**

`page.tsx` 에서 다음을 삭제합니다.

- 19~25: `interface Message { ... }`
- 78~100: `getTurnIndicesFromMessage` 와 `getMessagePartText`
- 111~244: `preprocessMarkdown` 과 `extractSuggestions`

그 자리에 import 를 넣습니다. `page.tsx:16` 의 `chatHelpers` import 바로 아래가 자연스러운 위치입니다.

```ts
import {
  extractSuggestions,
  getMessagePartText,
  getTurnIndicesFromMessage,
  preprocessMarkdown,
  type Message,
} from './chatMessageParser';
```

- [ ] **Step 6: 전체 검사를 돌린다**

Run: `cd frontend && npx vitest run && npm run type-check`

Expected: 두 명령 모두 통과. 특히 `page.regression-chat-001.test.tsx` 의 검사 3건이 통과해야 합니다. 실패하면 옮기는 과정에서 무언가를 빠뜨린 것이므로 되짚습니다.

- [ ] **Step 7: 커밋하지 않는다**

Global Constraints 를 따릅니다. 다음 Task 로 넘어갑니다.

---

## Task 2: 메시지 렌더를 메모이제이션된 컴포넌트로 떼어낸다

**Files:**
- Create: `frontend/src/app/chatbot/ChatMessage.tsx`
- Modify: `frontend/src/app/chatbot/page.tsx` (1363~1487 의 `messages.map` 콜백을 컴포넌트 호출로 대체)

**Interfaces:**
- Consumes: Task 1 의 `Message`, `extractSuggestions`, `getMessagePartText`, `preprocessMarkdown`
- Produces:
  - `export const ChatMessage: React.MemoExoticComponent<(props: ChatMessageProps) => JSX.Element>`
  - `export interface ChatMessageProps { message: Message; index: number; onDeleteTurn: (e: React.MouseEvent, index: number) => void; onDeleteMessage: (e: React.MouseEvent, index: number) => void; onSuggestionClick: (text: string) => void }`

- [ ] **Step 1: 컴포넌트를 만든다**

`frontend/src/app/chatbot/ChatMessage.tsx` 를 새로 만듭니다. `page.tsx:1363-1487` 의 JSX 를 그대로 옮기되 파싱을 `useMemo` 로 감쌉니다.

```tsx
'use client';

import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import ThinkingProcess from '../components/ThinkingProcess';
import {
  extractSuggestions,
  getMessagePartText,
  preprocessMarkdown,
  type Message,
} from './chatMessageParser';

export interface ChatMessageProps {
  message: Message;
  index: number;
  onDeleteTurn: (e: React.MouseEvent, index: number) => void;
  onDeleteMessage: (e: React.MouseEvent, index: number) => void;
  onSuggestionClick: (text: string) => void;
}

// 메시지 한 건을 그린다. memo 로 감싸는 이유가 성능 취향이 아니다. 스트리밍 델타가
// 도착할 때마다 setMessages 가 배열을 새로 만들고, memo 가 없으면 대화에 쌓인 모든
// 메시지가 정규식 스무 개짜리 파싱을 다시 돌린다. useMemo 는 map 콜백 안에서 부를 수
// 없으므로 컴포넌트로 떼어내는 것이 메모이제이션의 전제였다.
function ChatMessageInner({
  message,
  index,
  onDeleteTurn,
  onDeleteMessage,
  onSuggestionClick,
}: ChatMessageProps) {
  const rawText = getMessagePartText(message.parts[0]);

  const { content, suggestions, reasoning } = useMemo(() => {
    if (message.role !== 'model') {
      return { content: rawText, suggestions: [] as string[], reasoning: '' };
    }
    return extractSuggestions(rawText, !!message.isStreaming, message.reasoning);
  }, [message.role, message.isStreaming, message.reasoning, rawText]);

  const renderedMarkdown = useMemo(() => preprocessMarkdown(content), [content]);

  return (
    <div className="flex gap-4 group">
      <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-1 ${message.role === 'user'
        ? 'bg-gray-700 hidden'
        : 'bg-gradient-to-tr from-blue-500 to-purple-500 shadow-lg shadow-purple-500/20'
        }`}>
        {message.role === 'model' && <i className="fas fa-sparkles text-xs text-white"></i>}
      </div>

      <div className="flex-1 space-y-1 overflow-hidden">
        <div className="text-sm font-bold text-gray-400 mb-1 flex items-center gap-2">
          {message.role === 'model' && '스마트머니봇'}
          <span className="text-[10px] text-gray-500 font-normal ml-2">
            {message.timestamp ? new Date(message.timestamp).toLocaleString('ko-KR', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: true
            }) : ''}
          </span>
          {!message.isStreaming && (
            <span className="ml-1 inline-flex items-center gap-1">
              <button
                onClick={(e) => onDeleteTurn(e, index)}
                className="h-6 px-2 rounded-full text-[10px] font-bold text-gray-500 hover:text-amber-300 hover:bg-amber-500/10 transition-colors opacity-70 hover:opacity-100"
                title="이 질문과 답변 함께 삭제"
                aria-label="이 질문과 답변 함께 삭제"
              >
                질문/답변
              </button>
              <button
                onClick={(e) => onDeleteMessage(e, index)}
                className="w-6 h-6 rounded-full text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-70 hover:opacity-100"
                title="이 메시지 삭제"
                aria-label="이 메시지 삭제"
              >
                <i className="fas fa-trash-alt text-[11px]"></i>
              </button>
            </span>
          )}
        </div>
        <div className={`prose prose-sm prose-invert max-w-none leading-relaxed space-y-4 ${message.role === 'user' ? 'text-lg text-gray-100 font-medium' : 'text-gray-300'
          }`}>
          {message.role === 'model' && (
            <ThinkingProcess
              reasoning={reasoning}
              isStreaming={!!message.isStreaming}
            />
          )}
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              ul({ children }) { return <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-1">{children}</ul> },
              ol({ children }) { return <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-1">{children}</ol> },
              li({ children }) { return <li className="mb-1 leading-relaxed">{children}</li> },
              code({ node, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '')
                return match ? (
                  <div className="relative bg-[#1e1f20] rounded-lg overflow-hidden border border-white/5 my-2 shadow-inner">
                    <div className="px-4 py-1.5 bg-black/20 text-[10px] text-gray-500 font-mono border-b border-white/5 flex justify-between">
                      <span>{match[1]}</span>
                      <span className="cursor-pointer hover:text-white"><i className="far fa-copy"></i></span>
                    </div>
                    <pre className="p-4 overflow-x-auto m-0 !bg-transparent">
                      <code className={className} {...props}>{children}</code>
                    </pre>
                  </div>
                ) : (
                  <code className="bg-white/10 px-1.5 py-0.5 rounded text-blue-300 font-mono text-sm" {...props}>
                    {children}
                  </code>
                )
              },
              table({ children }) {
                return <div className="overflow-x-auto my-4 border border-white/10 rounded-lg"><table className="min-w-full divide-y divide-white/10">{children}</table></div>
              },
              thead({ children }) {
                return <thead className="bg-white/5">{children}</thead>
              },
              th({ children }) {
                return <th className="px-4 py-2 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">{children}</th>
              },
              td({ children }) {
                return <td className="px-4 py-2 text-sm text-gray-400 whitespace-nowrap border-t border-white/5">{children}</td>
              },
              a({ children, href }) {
                return <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer">{children}</a>
              },
              strong({ children }) {
                return <strong className="text-white font-bold">{children}</strong>
              }
            }}
          >
            {renderedMarkdown}
          </ReactMarkdown>

          {/* Render Extracted Suggestions */}
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4 pt-2 border-t border-white/5">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => onSuggestionClick(s)}
                  className="px-3 py-1.5 bg-[#1e1f20] hover:bg-blue-600/20 hover:text-blue-300 hover:border-blue-500/30 border border-white/10 rounded-full text-xs text-gray-300 transition-all text-left shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const ChatMessage = memo(ChatMessageInner);
```

- [ ] **Step 2: `page.tsx` 의 `messages.map` 을 갈아 끼운다**

`page.tsx:1363-1487` 의 콜백 전체를 지우고 아래로 바꿉니다.

```tsx
{messages.map((msg, idx) => (
  <ChatMessage
    key={idx}
    message={msg}
    index={idx}
    onDeleteTurn={handleDeleteTurn}
    onDeleteMessage={handleDeleteMessage}
    onSuggestionClick={handleSend}
  />
))}
```

`page.tsx` 상단에 import 를 더합니다.

```ts
import { ChatMessage } from './ChatMessage';
```

- [ ] **Step 3: memo 가 실제로 걸리는지 확인한다**

`handleDeleteTurn`, `handleDeleteMessage`, `handleSend` 는 지금 렌더마다 새로 만들어지는 함수입니다. 그러면 `memo` 의 얕은 비교가 언제나 실패해 메모이제이션이 무의미해집니다. 세 함수를 `useCallback` 으로 감싸십시오.

```ts
const handleDeleteTurn = useCallback((e: React.MouseEvent, msgIndex: number) => {
  e.stopPropagation();
  const indices = getTurnIndicesFromMessage(messages, msgIndex);
  if (indices.length === 0) return;
  setTurnDeleteIndices(indices);
  setIsTurnDeleteModalOpen(true);
}, [messages]);
```

`handleDeleteMessage` 도 같은 방식으로 감쌉니다. `handleSend` 는 의존이 많으므로 Task 3 에서 `useChatStream` 이 돌려주는 값으로 바뀝니다. **Task 3 을 마치기 전까지는 `handleSend` 만 `useCallback` 없이 두어도 됩니다.** 그때는 `memo` 가 걸리지 않지만 동작은 정상입니다.

- [ ] **Step 4: 검사를 돌린다**

Run: `cd frontend && npx vitest run && npm run type-check`

Expected: 두 명령 모두 통과. `page.regression-chat-001.test.tsx` 는 `react-markdown` 을 `({ children }) => children` 로 mock 하므로, `ChatMessage` 안에서 그것을 import 해도 같은 mock 이 걸립니다. 검사가 화면 텍스트 「안녕하세요」를 찾는 방식이라 컴포넌트 경계가 바뀌어도 통과합니다.

- [ ] **Step 5: 커밋하지 않는다**

---

## Task 3: SSE 수신을 훅으로 떼어내고 이벤트 적용을 순수 함수로 만든다

**Files:**
- Create: `frontend/src/app/chatbot/useChatStream.ts`
- Create: `frontend/src/app/chatbot/useChatStream.test.ts`
- Modify: `frontend/src/app/chatbot/page.tsx` (577~828 의 `handleStop` 과 `handleSend` 를 훅 호출로 대체)
- Modify: `frontend/src/app/components/chatHelpers.ts` (`getAuthHeaders` 를 받아들임)

**Interfaces:**
- Consumes: Task 1 의 `Message`, `getMessagePartText`
- Produces:
  - `export interface StreamEvent { error?: string; clear?: boolean; answer_clear?: boolean; reasoning_clear?: boolean; chunk?: string; answer_chunk?: string; reasoning_chunk?: string; session_id?: string; done?: boolean }`
  - `export function applyStreamEvent(message: Message, data: StreamEvent): Message`
  - `export function useChatStream(options: UseChatStreamOptions): { isLoading: boolean; handleSend: (text: string) => Promise<void>; handleStop: () => void }`
  - `chatHelpers.ts` 에 `export function getAuthHeaders(): Record<string, string>`

- [ ] **Step 1: `applyStreamEvent` 의 실패하는 검사를 쓴다**

`frontend/src/app/chatbot/useChatStream.test.ts` 를 새로 만듭니다.

```ts
// [CHAT-004] SSE 이벤트 하나를 메시지에 반영하는 규칙의 회귀 검사
// 근거: docs/dev-cycle/audits/AUDIT-CHAT.md §2.2

import { describe, expect, it } from 'vitest';

import type { Message } from './chatMessageParser';
import { applyStreamEvent } from './useChatStream';

const streamingMessage = (): Message => ({
  role: 'model',
  parts: [''],
  reasoning: '',
  isStreaming: true,
});

describe('applyStreamEvent', () => {
  it('answer_chunk 를 본문 뒤에 잇는다', () => {
    const first = applyStreamEvent(streamingMessage(), { answer_chunk: '안녕' });
    const second = applyStreamEvent(first, { answer_chunk: '하세요' });

    expect(second.parts[0]).toBe('안녕하세요');
  });

  it('answer_chunk 가 없으면 구형 chunk 필드로 물러난다', () => {
    // 기존 회귀 검사(page.regression-chat-001.test.tsx)가 이 형태로 청크를 보낸다.
    const result = applyStreamEvent(streamingMessage(), { chunk: '안녕' });

    expect(result.parts[0]).toBe('안녕');
  });

  it('reasoning_chunk 는 본문이 아니라 추론에 쌓는다', () => {
    const result = applyStreamEvent(streamingMessage(), { reasoning_chunk: '수급을 봤다' });

    expect(result.reasoning).toBe('수급을 봤다');
    expect(result.parts[0]).toBe('');
  });

  it('answer_clear 는 본문만 비우고 추론은 남긴다', () => {
    const filled: Message = { role: 'model', parts: ['본문'], reasoning: '추론', isStreaming: true };

    const result = applyStreamEvent(filled, { answer_clear: true });

    expect(result.parts[0]).toBe('');
    expect(result.reasoning).toBe('추론');
  });

  it('reasoning_clear 는 추론만 비우고 본문은 남긴다', () => {
    const filled: Message = { role: 'model', parts: ['본문'], reasoning: '추론', isStreaming: true };

    const result = applyStreamEvent(filled, { reasoning_clear: true });

    expect(result.parts[0]).toBe('본문');
    expect(result.reasoning).toBe('');
  });

  it('clear 는 둘 다 비운다', () => {
    const filled: Message = { role: 'model', parts: ['본문'], reasoning: '추론', isStreaming: true };

    const result = applyStreamEvent(filled, { clear: true });

    expect(result.parts[0]).toBe('');
    expect(result.reasoning).toBe('');
  });

  it('done 은 스트리밍 표시를 끈다', () => {
    const result = applyStreamEvent(streamingMessage(), { done: true });

    expect(result.isStreaming).toBe(false);
  });

  it('error 는 본문을 오류 문구로 바꾸고 스트리밍을 끝낸다', () => {
    const result = applyStreamEvent(streamingMessage(), { error: '한도를 넘었습니다' });

    expect(result.parts[0]).toBe('한도를 넘었습니다');
    expect(result.isStreaming).toBe(false);
  });

  it('한 이벤트에 비우기와 델타가 함께 오면 비운 뒤에 잇는다', () => {
    const filled: Message = { role: 'model', parts: ['이전 본문'], reasoning: '', isStreaming: true };

    const result = applyStreamEvent(filled, { answer_clear: true, answer_chunk: '새 본문' });

    expect(result.parts[0]).toBe('새 본문');
  });

  it('원본 메시지를 바꾸지 않는다', () => {
    const original = streamingMessage();

    applyStreamEvent(original, { answer_chunk: '안녕' });

    expect(original.parts[0]).toBe('');
  });
});
```

- [ ] **Step 2: 검사가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/chatbot/useChatStream.test.ts`

Expected: FAIL. `Failed to resolve import "./useChatStream"`.

- [ ] **Step 3: `getAuthHeaders` 를 `chatHelpers.ts` 로 옮긴다**

`page.tsx:455-474` 의 함수를 잘라 `frontend/src/app/components/chatHelpers.ts` 끝에 붙입니다. 세 곳에서 쓰이므로 공용 자리로 올립니다.

```ts
import { getBrowserSessionId } from '@/lib/session';

export function getAuthHeaders(): Record<string, string> {
  const sessionId = getBrowserSessionId();

  const headers: Record<string, string> = {
    'X-Session-Id': sessionId
  };

  // User Profile Email
  const savedProfile = localStorage.getItem('user_profile');
  if (savedProfile) {
    try {
      const p = JSON.parse(savedProfile);
      if (p.email && p.email !== 'user@example.com') {
        headers['X-User-Email'] = p.email;
      }
    } catch (e) { }
  }

  return headers;
}
```

`page.tsx:6` 의 `import { getBrowserSessionId } from '@/lib/session';` 는 페이지에서 더 쓰이지 않으면 지웁니다. `grep -n "getBrowserSessionId" frontend/src/app/chatbot/page.tsx` 로 확인하십시오.

- [ ] **Step 4: 훅 모듈을 만든다**

`frontend/src/app/chatbot/useChatStream.ts` 를 새로 만듭니다.

```ts
'use client';

import { useCallback, useRef, useState } from 'react';

import { getAuthHeaders } from '../components/chatHelpers';
import { getMessagePartText, type Message } from './chatMessageParser';

export interface StreamEvent {
  error?: string;
  clear?: boolean;
  answer_clear?: boolean;
  reasoning_clear?: boolean;
  chunk?: string;
  answer_chunk?: string;
  reasoning_chunk?: string;
  session_id?: string;
  done?: boolean;
}

// 이벤트 하나를 마지막 메시지에 반영한다. 상태를 건드리지 않는 순수 함수라 단위 검사가
// 직접 부를 수 있다. 분기 순서는 옮기기 전 page.tsx:697-767 과 같다. 한 이벤트에
// 비우기와 델타가 함께 실려 오는 경우가 있어서, 비우기를 먼저 적용해야 한다.
export function applyStreamEvent(message: Message, data: StreamEvent): Message {
  let next = message;

  if (data.error) {
    next = { ...next, parts: [data.error], isStreaming: false };
  }
  if (data.clear) {
    next = { ...next, parts: [''], reasoning: '' };
  }
  if (data.answer_clear) {
    next = { ...next, parts: [''] };
  }
  if (data.reasoning_clear) {
    next = { ...next, reasoning: '' };
  }

  const answerDelta = typeof data.answer_chunk === 'string' ? data.answer_chunk : data.chunk;
  if (typeof answerDelta === 'string' && answerDelta.length > 0) {
    next = { ...next, parts: [getMessagePartText(next.parts[0]) + answerDelta] };
  }
  if (typeof data.reasoning_chunk === 'string' && data.reasoning_chunk.length > 0) {
    next = { ...next, reasoning: (next.reasoning || '') + data.reasoning_chunk };
  }
  if (data.done) {
    next = { ...next, isStreaming: false };
  }

  return next;
}

export interface UseChatStreamOptions {
  currentSessionId: string | null;
  currentModel: string;
  persona?: string;
  attachedFiles: File[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  clearInput: () => void;
  clearAttachedFiles: () => void;
  onSessionAssigned: (sessionId: string) => void;
  onSessionsShouldRefresh: () => void;
}

export function useChatStream({
  currentSessionId,
  currentModel,
  persona,
  attachedFiles,
  setMessages,
  clearInput,
  clearAttachedFiles,
  onSessionAssigned,
  onSessionsShouldRefresh,
}: UseChatStreamOptions) {
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setMessages(prev => [...prev, { role: 'model', parts: ['🛑 답변 생성이 중단되었습니다.'] }]);
    }
  }, [setMessages]);

  const applyToLastMessage = useCallback((data: StreamEvent) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const newMsgs = [...prev];
      newMsgs[newMsgs.length - 1] = applyStreamEvent(newMsgs[newMsgs.length - 1], data);
      return newMsgs;
    });
  }, [setMessages]);

  const handleSend = useCallback(async (text: string) => {
    if ((!text.trim() && attachedFiles.length === 0) || isLoading) return;

    const displayMsg = text + (attachedFiles.length > 0 ? `\n[파일 ${attachedFiles.length}개 첨부]` : '');
    const userMsg: Message = {
      role: 'user',
      parts: [displayMsg],
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMsg]);
    clearInput();
    clearAttachedFiles();
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // 이 요청이 속한 세션. 화면에 표시 중인 세션(currentSessionId)과는 다른 값이다.
    // 응답이 흐르는 동안 사용자가 다른 세션을 열 수 있기 때문에 둘을 섞으면 안 된다.
    let streamSessionId = currentSessionId;

    try {
      const savedWatchlist = localStorage.getItem('watchlist');
      const watchlist = savedWatchlist ? JSON.parse(savedWatchlist) : [];
      const headers = getAuthHeaders();

      let res: Response;
      if (attachedFiles.length > 0) {
        const formData = new FormData();
        formData.append('message', text);
        if (currentModel) formData.append('model', currentModel);
        if (currentSessionId) formData.append('session_id', currentSessionId);
        if (watchlist.length > 0) formData.append('watchlist', JSON.stringify(watchlist));
        if (persona) formData.append('persona', persona);
        attachedFiles.forEach(file => formData.append('file', file));

        res = await fetch('/api/kr/chatbot', {
          method: 'POST',
          headers,
          body: formData,
          signal: controller.signal,
        });
      } else {
        headers['Content-Type'] = 'application/json';
        res = await fetch('/api/kr/chatbot', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: text,
            model: currentModel,
            session_id: currentSessionId,
            watchlist,
            persona,
          }),
          signal: controller.signal,
        });
      }

      const contentType = (res.headers.get('content-type') || '').toLowerCase();

      if (contentType.includes('text/event-stream') && res.body) {
        setIsLoading(false);
        setMessages(prev => [...prev, { role: 'model', parts: [''], reasoning: '', isStreaming: true }]);

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let done = false;
        let buffer = '';

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (!value) continue;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';

          for (const frame of frames) {
            if (!frame.startsWith('data: ')) continue;
            const dataStr = frame.substring(6);
            if (!dataStr.trim()) continue;

            let data: StreamEvent;
            try {
              data = JSON.parse(dataStr);
            } catch {
              // 반쪽 청크는 다음 프레임에서 이어진다
              continue;
            }

            applyToLastMessage(data);

            // 서버는 모든 청크에 session_id 를 싣는다. 새 대화에서 첫 청크가 세션을
            // 배정한 뒤에도 갱신으로 판정되지 않도록 이 스트림의 세션을 갱신해 둔다.
            const sessionChanged = Boolean(data.session_id) && data.session_id !== streamSessionId;
            if (sessionChanged) {
              streamSessionId = data.session_id!;
              onSessionAssigned(data.session_id!);
            }
            if (sessionChanged || data.done) {
              onSessionsShouldRefresh();
            }
          }
        }

        // Safety net: if stream closed without explicit done event,
        // ensure the last placeholder message does not remain in streaming state.
        setMessages(prev => {
          if (prev.length === 0) return prev;
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === 'model' && last?.isStreaming) {
            next[next.length - 1] = { ...last, isStreaming: false };
          }
          return next;
        });
      } else {
        const data = await res.json();

        if (data.response) {
          if (data.session_id && data.session_id !== streamSessionId) {
            streamSessionId = data.session_id;
            onSessionAssigned(data.session_id);
          }
          onSessionsShouldRefresh();
          setMessages(prev => [...prev, { role: 'model', parts: [data.response] }]);
        } else if (data.error) {
          setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ 오류: ${data.error}`] }]);
        } else {
          setMessages(prev => [...prev, { role: 'model', parts: ['⚠️ 응답을 받아오지 못했습니다.'] }]);
        }
      }
    } catch (error: any) {
      if (error?.name === 'AbortError') {
        return;
      }
      const errorMessage = (error && typeof error.message === 'string' && error.message.trim().length > 0)
        ? `⚠️ 오류가 발생했습니다: ${error.message}`
        : '⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
      setMessages(prev => [...prev, { role: 'model', parts: [errorMessage] }]);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
      // Reset viewport for mobile keyboard fix
      if (window.innerWidth < 1024) {
        window.scrollTo(0, 0);
        document.body.scrollTop = 0;
      }
    }
  }, [
    attachedFiles,
    isLoading,
    currentSessionId,
    currentModel,
    persona,
    setMessages,
    clearInput,
    clearAttachedFiles,
    applyToLastMessage,
    onSessionAssigned,
    onSessionsShouldRefresh,
  ]);

  return { isLoading, handleSend, handleStop };
}
```

- [ ] **Step 5: 검사가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/chatbot/useChatStream.test.ts`

Expected: PASS, 검사 10건.

- [ ] **Step 6: `page.tsx` 를 훅에 연결한다**

`page.tsx` 에서 다음을 지웁니다.

- 455~474: `getAuthHeaders` (Task 3 Step 3 에서 이미 옮겼습니다)
- 577~828: `abortControllerRef`, `handleStop`, `handleSend`
- `const [isLoading, setIsLoading] = useState(false);` (훅이 소유합니다)

그 자리에 훅 호출을 넣습니다. 위치는 상태 선언 뒤, `useEffect` 앞입니다.

```ts
const { isLoading, handleSend, handleStop } = useChatStream({
  currentSessionId,
  currentModel,
  persona: userProfile?.persona,
  attachedFiles,
  setMessages,
  clearInput: useCallback(() => {
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
    setTimeout(() => {
      isComposing.current = false;
    }, 0);
    setShowCommands(false);
  }, []),
  clearAttachedFiles: useCallback(() => setAttachedFiles([]), []),
  onSessionAssigned: useCallback((sessionId: string) => {
    isCreatingSessionRef.current = true;
    setCurrentSessionId(sessionId);
  }, []),
  onSessionsShouldRefresh: useCallback(() => {
    fetchSessions();
  }, []),
});
```

**주의:** `useCallback` 을 인자 자리에 직접 쓰면 훅 호출 순서가 조건에 걸리지 않는 한 문제가 없지만 읽기 어렵습니다. 각각을 훅 호출 앞에서 별도 `const` 로 선언하고 이름으로 넘기십시오.

`handleSend` 의 인자 기본값이 사라졌으므로(`text: string = input`), 호출부 가운데 인자 없이 부르는 자리를 찾아 `handleSend(input)` 으로 고칩니다. `grep -n "handleSend()" frontend/src/app/chatbot/page.tsx` 로 찾습니다.

- [ ] **Step 7: 전체 검사를 돌린다**

Run: `cd frontend && npx vitest run && npm run type-check`

Expected: 두 명령 모두 통과. `page.regression-chat-001.test.tsx` 의 「세션 목록을 청크마다 다시 부르지 않는다」가 특히 중요합니다. `onSessionsShouldRefresh` 를 `sessionChanged || data.done` 조건 밖에서 부르면 이 검사가 실패합니다.

- [ ] **Step 8: 커밋하지 않는다**

---

## Task 4: 세션 관리를 훅으로 떼어낸다

**Files:**
- Create: `frontend/src/app/chatbot/useChatSessions.ts`
- Modify: `frontend/src/app/chatbot/page.tsx` (`messages`·`sessions`·`currentSessionId` 상태와 `fetchSessions`·`fetchHistory`·`handleNewChat` 을 훅으로 이동)

**Interfaces:**
- Consumes: Task 1 의 `Message`, Task 3 의 `getAuthHeaders`
- Produces:
  - `export interface Session { id: string; title: string; updated_at: string; model?: string }`
  - `export function useChatSessions(): { messages: Message[]; setMessages: React.Dispatch<React.SetStateAction<Message[]>>; sessions: Session[]; currentSessionId: string | null; setCurrentSessionId: (id: string | null) => void; isHistoryLoading: boolean; fetchSessions: () => Promise<Session[]>; fetchHistory: (sessionId: string) => Promise<void>; markSessionAsCreated: () => void; startNewChat: () => void }`

- [ ] **Step 1: 훅 모듈을 만든다**

`frontend/src/app/chatbot/useChatSessions.ts` 를 새로 만듭니다. `page.tsx` 의 `fetchSessions`(476), `fetchHistory`(492), 세션 변경 `useEffect`(407~419), `handleNewChat`(830) 을 옮깁니다.

```ts
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchAPI } from '@/lib/api';

import { getAuthHeaders } from '../components/chatHelpers';
import type { Message } from './chatMessageParser';

export interface Session {
  id: string;
  title: string;
  updated_at: string;
  model?: string;
}

const LAST_SESSION_KEY = 'chatbot_last_session_id';

// 세션과 메시지를 한 훅이 소유한다. 세션을 바꾸면 메시지가 통째로 바뀌므로 둘을
// 나누면 두 상태가 어긋나는 순간이 생긴다.
export function useChatSessions() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  // 새 대화의 첫 청크가 세션을 배정했을 때, 그 배정이 세션 전환으로 오판정되어
  // 히스토리를 덮어쓰지 않도록 막는 표시다. [CHAT-001] 이 만든 장치다.
  const isCreatingSessionRef = useRef(false);

  const fetchSessions = useCallback(async (): Promise<Session[]> => {
    try {
      const data: any = await fetchAPI('/api/kr/chatbot/sessions', { headers: getAuthHeaders() });
      if (data.sessions) {
        setSessions(data.sessions);
        return data.sessions;
      }
    } catch (e) {
      console.error('Failed to fetch sessions', e);
    }
    return [];
  }, []);

  const fetchHistory = useCallback(async (sessionId: string) => {
    try {
      setIsHistoryLoading(true);
      const data: any = await fetchAPI(`/api/kr/chatbot/history?session_id=${sessionId}`, {
        headers: getAuthHeaders(),
      });
      setMessages(data.history ?? []);
    } catch (error) {
      console.error('Failed to fetch history:', error);
      setMessages([{ role: 'model', parts: ['⚠️ 대화 기록을 불러오는데 실패했습니다.'] }]);
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  const markSessionAsCreated = useCallback(() => {
    isCreatingSessionRef.current = true;
  }, []);

  const startNewChat = useCallback(() => {
    setCurrentSessionId(null);
    localStorage.removeItem(LAST_SESSION_KEY);
    setMessages([]);
  }, []);

  // Load History when Session Changes
  useEffect(() => {
    if (currentSessionId) {
      if (isCreatingSessionRef.current) {
        isCreatingSessionRef.current = false;
      } else {
        fetchHistory(currentSessionId);
      }
      localStorage.setItem(LAST_SESSION_KEY, currentSessionId);
    } else {
      setMessages([]); // New Chat
    }
  }, [currentSessionId, fetchHistory]);

  return {
    messages,
    setMessages,
    sessions,
    setSessions,
    currentSessionId,
    setCurrentSessionId,
    isHistoryLoading,
    fetchSessions,
    fetchHistory,
    markSessionAsCreated,
    startNewChat,
  };
}
```

- [ ] **Step 2: `page.tsx` 를 훅에 연결한다**

`page.tsx` 에서 다음을 지웁니다.

- `const [messages, setMessages] = useState<Message[]>([]);`
- `const [sessions, setSessions] = useState<Session[]>([]);`
- `const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);`
- `const isCreatingSessionRef = useRef(false);`
- `interface Session { ... }` (64~69)
- `fetchSessions`(476~490), `fetchHistory`(492~510)
- 세션 변경 `useEffect`(407~419)
- `handleNewChat`(830~838) 의 본문 가운데 세션·메시지 초기화 부분

`handleNewChat` 은 첨부 파일과 입력 칸까지 비우므로 페이지에 남기되 훅의 `startNewChat` 을 부르게 합니다.

```ts
const handleNewChat = useCallback(() => {
  startNewChat();
  setAttachedFiles([]);
  setInput('');
  setIsMobileSidebarOpen(false);
}, [startNewChat]);
```

훅 호출을 상태 선언 앞쪽에 넣습니다.

```ts
const {
  messages,
  setMessages,
  sessions,
  currentSessionId,
  setCurrentSessionId,
  isHistoryLoading,
  fetchSessions,
  fetchHistory,
  markSessionAsCreated,
  startNewChat,
} = useChatSessions();
```

Task 3 에서 넘긴 `onSessionAssigned` 를 훅의 `markSessionAsCreated` 를 쓰도록 고칩니다.

```ts
const onSessionAssigned = useCallback((sessionId: string) => {
  markSessionAsCreated();
  setCurrentSessionId(sessionId);
}, [markSessionAsCreated, setCurrentSessionId]);
```

`isLoading` 은 `useChatStream` 이 돌려주고 `isHistoryLoading` 은 `useChatSessions` 가 돌려줍니다. 원래는 한 상태였으므로 화면에서 둘을 합쳐 씁니다.

```ts
const isBusy = isLoading || isHistoryLoading;
```

`page.tsx` 의 로딩 표시(`:1491` 의 `{isLoading && ...}`)와 로딩 단계 `useEffect`(`:325`)에서 `isLoading` 을 `isBusy` 로 바꿉니다.

- [ ] **Step 3: 전체 검사를 돌린다**

Run: `cd frontend && npx vitest run && npm run type-check`

Expected: 두 명령 모두 통과. `page.regression-chat-001.test.tsx` 의 「스트림이 끝난 뒤 다른 세션을 열면 그 세션의 기록을 불러온다」와 「응답이 흐르는 도중에 다른 세션을 열면 그 세션에 머무른다」가 `isCreatingSessionRef` 의 동작을 붙잡습니다. 이 둘이 실패하면 `markSessionAsCreated` 를 부르는 시점이 어긋난 것입니다.

- [ ] **Step 4: 커밋하지 않는다**

---

## Task 5: 음성 입력을 훅으로 떼어낸다

**Files:**
- Create: `frontend/src/app/chatbot/useSpeechInput.ts`
- Modify: `frontend/src/app/chatbot/page.tsx` (27~62 의 타입 다섯 개, 989~1044 의 `toggleRecording`, 388~395 의 정리 `useEffect` 를 삭제)

**Interfaces:**
- Consumes: 없음
- Produces:
  - `export function useSpeechInput(options: { onTranscript: (text: string) => void; onUnsupported: () => void }): { isRecording: boolean; toggleRecording: () => void }`

- [ ] **Step 1: 훅 모듈을 만든다**

`frontend/src/app/chatbot/useSpeechInput.ts` 를 새로 만듭니다. 타입 다섯 개와 `toggleRecording` 과 정리 `useEffect` 를 옮깁니다.

```ts
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
}

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionConstructorLike = new () => SpeechRecognitionLike;

type WindowWithSpeechRecognition = Window & {
  SpeechRecognition?: SpeechRecognitionConstructorLike;
  webkitSpeechRecognition?: SpeechRecognitionConstructorLike;
};

export interface UseSpeechInputOptions {
  // 인식된 문장을 받는다. 호출자가 입력 칸에 어떻게 이어 붙일지 정한다.
  onTranscript: (text: string) => void;
  // 브라우저가 음성 인식을 지원하지 않을 때 부른다.
  onUnsupported: () => void;
}

export function useSpeechInput({ onTranscript, onUnsupported }: UseSpeechInputOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const toggleRecording = useCallback(() => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      onUnsupported();
      return;
    }

    if (isRecording) {
      setIsRecording(false);
      recognitionRef.current?.stop();
      return;
    }

    setIsRecording(true);
    const speechWindow = window as WindowWithSpeechRecognition;
    const SpeechRecognitionCtor =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setIsRecording(false);
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.lang = 'ko-KR';
    recognition.interimResults = false;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        }
      }
      if (finalTranscript) {
        onTranscript(finalTranscript);
      }
    };

    recognition.onerror = (event: unknown) => {
      console.error('Speech error', event);
      setIsRecording(false);
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognition.start();
    recognitionRef.current = recognition;
  }, [isRecording, onTranscript, onUnsupported]);

  // 화면을 떠날 때 인식을 끊는다. 끊지 않으면 마이크가 열린 채로 남는다.
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return { isRecording, toggleRecording };
}
```

- [ ] **Step 2: `page.tsx` 를 훅에 연결한다**

`page.tsx` 에서 다음을 지웁니다.

- 27~62: 음성 인식 타입 다섯 개와 `WindowWithSpeechRecognition`
- `const [isRecording, setIsRecording] = useState(false);`
- `const recognitionRef = useRef<SpeechRecognitionLike | null>(null);`
- 388~395: 음성 정리 `useEffect`
- 989~1044: `toggleRecording`

그 자리에 훅 호출을 넣습니다.

```ts
const handleTranscript = useCallback((text: string) => {
  setInput(prev => prev + (prev ? ' ' : '') + text);
}, []);

const handleSpeechUnsupported = useCallback(() => {
  setAlertModal({
    isOpen: true,
    type: 'danger',
    title: '음성 인식 미지원',
    content: '이 브라우저는 음성 인식을 지원하지 않습니다.',
  });
}, []);

const { isRecording, toggleRecording } = useSpeechInput({
  onTranscript: handleTranscript,
  onUnsupported: handleSpeechUnsupported,
});
```

- [ ] **Step 3: 전체 검사를 돌린다**

Run: `cd frontend && npx vitest run && npm run type-check`

Expected: 두 명령 모두 통과.

- [ ] **Step 4: 커밋하지 않는다**

---

## Task 6: 마무리 확인

**Files:**
- Modify: `frontend/src/app/chatbot/page.tsx` (남은 정리)

**Interfaces:**
- Consumes: Task 1~5 의 전부
- Produces: 없음

- [ ] **Step 1: 죽은 import 와 죽은 상태를 걷어낸다**

Run:

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

`noUnusedLocals` 가 켜져 있지 않을 수 있으므로 다음도 함께 확인합니다.

```bash
cd frontend && npx eslint src/app/chatbot/ --max-warnings 0
```

`getBrowserSessionId`, `ReactMarkdown`, `remarkGfm`, `ThinkingProcess` 는 `page.tsx` 에서 더 쓰이지 않을 수 있습니다. `grep -n` 으로 확인하고 쓰이지 않으면 import 를 지웁니다.

- [ ] **Step 2: 줄 수가 실제로 줄었는지 확인한다**

Run:

```bash
wc -l frontend/src/app/chatbot/*.ts frontend/src/app/chatbot/*.tsx
```

Expected: `page.tsx` 가 1,050줄 안팎. 1,300줄을 넘으면 옮기지 않은 것이 남아 있으므로 Task 1~5 를 되짚습니다.

- [ ] **Step 3: 검증 세 가지를 모두 돌린다**

Run:

```bash
cd frontend && npx vitest run
cd frontend && npm run type-check
source venv/bin/activate && pytest
```

Expected: 셋 모두 통과. vitest 는 기존 검사에 새 검사 21건이 더해집니다.

- [ ] **Step 4: 커밋하지 않는다**

사이클의 [3] 검증 5번이 커밋을 만듭니다.

---

## Self-Review

**1. 항목 체크박스 다섯 개의 대응**

| 체크박스 | Task |
|---|---|
| 마크다운 교정과 추론·추천 질문 파싱을 별도 모듈로 분리 | Task 1 |
| 프런트의 중복 헤더 파싱 범위를 히스토리 복원 경로로 한정 | Task 1 Step 3 의 `hasStreamReasoning` 수정 |
| SSE 수신, 세션 관리, 음성 입력을 각각 훅이나 컴포넌트로 분리 | Task 3, Task 4, Task 5 |
| 파서 호출을 메모이제이션해 스트리밍 중 전체 메시지 재파싱을 제거 | Task 2 |
| 분리한 파서와 SSE 처리에 vitest 테스트 추가 | Task 1 Step 1, Task 3 Step 1 |

빠진 것이 없습니다.

**2. 자리를 차지하는 문구 점검**

「적절히 처리한다」나 「TODO」에 해당하는 문구가 없습니다. 모든 코드 단계에 실제 코드가 들어 있습니다.

**3. 이름과 타입의 일관성**

- `Message` 는 Task 1 이 정의하고 Task 2·3·4 가 그대로 import 합니다
- `applyStreamEvent(message, data)` 의 이름과 인자 순서가 Task 3 의 검사와 구현에서 같습니다
- `getAuthHeaders` 는 Task 3 Step 3 이 `chatHelpers.ts` 로 옮기고 Task 3 의 훅과 Task 4 의 훅이 같은 경로에서 import 합니다
- `markSessionAsCreated` 는 Task 4 가 내보내고 Task 4 Step 2 가 Task 3 의 `onSessionAssigned` 안에서 부릅니다
- `startNewChat` 은 Task 4 가 내보내고 페이지의 `handleNewChat` 이 감쌉니다

**4. 순서 의존**

Task 2 의 `memo` 는 Task 3 이 `handleSend` 를 `useCallback` 으로 만든 뒤에야 완전히 걸립니다. 이 사실을 Task 2 Step 3 에 적어 두었습니다. Task 순서를 바꾸면 안 됩니다.

---

## 실행 방식

이 계획은 dev-cycle 의 [2] 구현 단계에서 이 세션이 직접 실행합니다. 서브에이전트로 나누지 않습니다. Task 사이의 의존이 촘촘하고 각 Task 가 같은 파일(`page.tsx`)을 이어서 고치므로, 나누면 병합 충돌을 스스로 만드는 셈이 됩니다.
