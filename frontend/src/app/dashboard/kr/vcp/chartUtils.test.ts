import { describe, expect, it } from 'vitest';

import { calculateSMA } from './chartUtils';

describe('calculateSMA', () => {
  it('데이터 길이가 기간보다 짧아도 가용 구간 평균으로 값을 반환한다', () => {
    const data = [
      { date: '2026-01-01', close: 10 },
      { date: '2026-01-02', close: 20 },
      { date: '2026-01-03', close: 30 },
      { date: '2026-01-04', close: 40 },
    ];

    const sma = calculateSMA(data, 60);

    expect(sma).toHaveLength(4);
    expect(sma[0]).toEqual({ time: '2026-01-01', value: 10 });
    expect(sma[1]).toEqual({ time: '2026-01-02', value: 15 });
    expect(sma[3]).toEqual({ time: '2026-01-04', value: 25 });
  });

  it('기간 이상 구간부터는 지정한 기간 이동평균으로 계산한다', () => {
    const data = [
      { date: '2026-01-01', close: 10 },
      { date: '2026-01-02', close: 20 },
      { date: '2026-01-03', close: 30 },
      { date: '2026-01-04', close: 40 },
      { date: '2026-01-05', close: 50 },
    ];

    const sma = calculateSMA(data, 3);

    expect(sma[2]).toEqual({ time: '2026-01-03', value: 20 });
    expect(sma[4]).toEqual({ time: '2026-01-05', value: 40 });
  });
});
