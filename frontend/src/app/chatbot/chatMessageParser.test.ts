// Regression: [CHAT-004] — 챗봇 응답 파서의 판정 분기
// 근거: docs/dev-cycle/audits/AUDIT-CHAT.md §2.2

import { describe, expect, it } from 'vitest';

import {
  extractSuggestions,
  getMessagePartText,
  getTurnIndicesFromMessage,
  preprocessMarkdown,
  type Message,
} from './chatMessageParser';

describe('extractSuggestions - 스트리밍 메시지의 판정', () => {
  it('추론이 비어 있는 스트리밍 응답에서도 답변을 숨기지 않는다', () => {
    // 백엔드가 reasoning_chunk 를 한 번도 보내지 않으면 reasoning 은 빈 문자열이다.
    // 그때 답변 본문에 [추론 과정] 이라는 문구가 들어 있어도 fallback 파서가 켜지면
    // 안 된다. 켜지면 그 뒤가 통째로 추론 영역으로 빨려 들어간다.
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

describe('extractSuggestions - 히스토리 메시지의 fallback 파싱', () => {
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

  it('추천 질문은 순서대로 세 개만 남기고 각 줄을 120 code point로 자른다', () => {
    const long = `${'😀'.repeat(121)} 끝`;
    const raw = `본문\n[추천 질문]\n1. 첫 질문\n2. ${long}\n3. 셋째 질문\n4. 넷째 질문`;

    const result = extractSuggestions(raw);

    expect(result.suggestions).toHaveLength(3);
    expect(result.suggestions).toEqual(['첫 질문', Array.from(long).slice(0, 120).join(''), '셋째 질문']);
  });
});

describe('extractSuggestions - 번호 목록 줄바꿈', () => {
  it('markdown 제목 줄은 보존하고 조밀한 본문 번호 목록만 나눈다', () => {
    const result = extractSuggestions('### 1. 시장 환경\n본문 2. 다음 항목');

    expect(result.content).toContain('### 1. 시장 환경');
    expect(result.content).toContain('본문\n\n2. 다음 항목');
  });

  it('추론 영역에도 같은 제목 보존 규칙을 적용한다', () => {
    const result = extractSuggestions('[추론 과정]\n### 1. 근거\n내용 2. 다음\n[답변]\n결론');

    expect(result.reasoning).toContain('### 1. 근거');
    expect(result.reasoning).toContain('내용\n\n2. 다음');
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
  const messages: Message[] = [
    { role: 'user', parts: ['질문'] },
    { role: 'model', parts: ['답변'] },
  ];

  it('질문에서 부르면 질문과 답변을 함께 돌려준다', () => {
    expect(getTurnIndicesFromMessage(messages, 0)).toEqual([0, 1]);
  });

  it('답변에서 부르면 앞의 질문까지 함께 돌려준다', () => {
    expect(getTurnIndicesFromMessage(messages, 1)).toEqual([0, 1]);
  });

  it('짝이 없으면 자기 자신만 돌려준다', () => {
    expect(getTurnIndicesFromMessage([{ role: 'model', parts: ['답변'] }], 0)).toEqual([0]);
  });
});
