import { describe, expect, it } from 'vitest';

import type { AIRecommendation } from '@/lib/api';

import { decideSecondaryAI, isValidAIRecommendation } from './aiHelpers';

describe('decideSecondaryAI', () => {
  it('returns perplexity when both hasPerplexity and hasGpt are true (perplexity wins)', () => {
    expect(decideSecondaryAI(true, true)).toBe('perplexity');
  });

  it('returns perplexity when only hasPerplexity is true', () => {
    expect(decideSecondaryAI(true, false)).toBe('perplexity');
  });

  it('returns gpt when only hasGpt is true', () => {
    expect(decideSecondaryAI(false, true)).toBe('gpt');
  });

  it('returns gpt (safe default) when both flags are false', () => {
    expect(decideSecondaryAI(false, false)).toBe('gpt');
  });

  it.each([
    { hasPerplexity: true,  hasGpt: true,  expected: 'perplexity' },
    { hasPerplexity: true,  hasGpt: false, expected: 'perplexity' },
    { hasPerplexity: false, hasGpt: true,  expected: 'gpt' },
    { hasPerplexity: false, hasGpt: false, expected: 'gpt' },
  ])(
    'table-driven: hasPerplexity=$hasPerplexity hasGpt=$hasGpt → $expected',
    ({ hasPerplexity, hasGpt, expected }) => {
      expect(decideSecondaryAI(hasPerplexity, hasGpt)).toBe(expected);
    },
  );
});

describe('isValidAIRecommendation', () => {
  const rec = (action: string, reason: string) =>
    ({ action, confidence: 0, reason }) as unknown as AIRecommendation;

  it.each([
    { label: '정상 판정', value: rec('BUY', '수급이 개선되었습니다.'), expected: true },
    { label: '소문자에 공백이 붙은 action', value: rec(' hold ', '추가 확인이 필요합니다.'), expected: true },
    { label: '재분석 실패 기록', value: rec('N/A', '분석 실패'), expected: false },
    { label: 'action 만 살아 있는 실패 기록', value: rec('HOLD', '분석 실패'), expected: false },
    { label: '영문 실패 문구', value: rec('HOLD', 'No analysis available.'), expected: false },
    { label: '사유가 비어 있는 기록', value: rec('BUY', '   '), expected: false },
    { label: 'null', value: null, expected: false },
    { label: 'undefined', value: undefined, expected: false },
  ])('$label → $expected', ({ value, expected }) => {
    expect(isValidAIRecommendation(value)).toBe(expected);
  });

  it('keeps a provider tab closed when the cache holds nothing but failures', () => {
    // 원시 캐시(aiData.signals)에는 응답 조립 경로가 걸러 낸 실패 기록이 남아 있다.
    // 존재만 보고 판정하면 탭이 열리고, 사용자는 모든 행이 '-' 인 빈 열을 만난다.
    const cached = [
      { perplexity_recommendation: rec('N/A', '분석 실패') },
      { perplexity_recommendation: rec('HOLD', '분석 대기중') },
    ];
    const hasPerplexity = cached.some(s => isValidAIRecommendation(s.perplexity_recommendation));

    expect(hasPerplexity).toBe(false);
    expect(decideSecondaryAI(hasPerplexity, false)).toBe('gpt');
  });
});
