import { describe, expect, it } from 'vitest';

import { formatMarketAmount } from './formatMarketAmount';

describe('[JONGGA-026] 한국 시장 금액 포맷', () => {
  it('조 단위에서 억 단위 차이를 보존한다', () => {
    expect(formatMarketAmount(1_240_000_000_000)).toBe('1조 2400억');
    expect(formatMarketAmount(1_260_000_000_000)).toBe('1조 2600억');
  });

  it('억 단위는 가장 가까운 정수로 반올림한다', () => {
    expect(formatMarketAmount(3_276_004_650)).toBe('33억');
    expect(formatMarketAmount(3_224_000_000)).toBe('32억');
  });

  it('음수도 절댓값과 같은 경계로 대칭 포맷한다', () => {
    expect(formatMarketAmount(-1_240_000_000_000)).toBe('-1조 2400억');
    expect(formatMarketAmount(-3_276_004_650)).toBe('-33억');
  });

  it('기본 0 표기와 종가베팅의 값 없음 표기를 모두 보존한다', () => {
    expect(formatMarketAmount(0)).toBe('0');
    expect(formatMarketAmount(0, '-')).toBe('-');
    expect(formatMarketAmount(undefined)).toBe('-');
    expect(formatMarketAmount(null)).toBe('-');
    expect(formatMarketAmount(Number.NaN)).toBe('-');
    expect(formatMarketAmount(Number.POSITIVE_INFINITY)).toBe('-');
  });
});
