import { describe, expect, it } from 'vitest';

import { calculateSMA, findChartDateGaps } from './chartUtils';

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


describe('[VCP-014] 응답의 긴 날짜 간격', () => {
  it('달력상 7일을 넘는 간격의 양 끝 날짜와 일수를 그대로 반환한다', () => {
    expect(findChartDateGaps([{ date: '2026-03-06' }, { date: '2026-04-30' }, { date: '2026-05-04' }])).toEqual([{ from: '2026-03-06', to: '2026-04-30', days: 55 }]);
  });
  it('주말과 7일 간격은 길어진 구간으로 표시하지 않는다', () => {
    expect(findChartDateGaps([{date:'2026-05-01'}, {date:'2026-05-04'}, {date:'2026-05-11'}])).toEqual([]);
  });
  it('빈 자료·단일 자료에는 간격이 없고 잘못된 날짜로 간격을 만들지 않는다', () => {
    expect(findChartDateGaps([])).toEqual([]);
    expect(findChartDateGaps([{date:'2026-05-01'}])).toEqual([]);
    expect(findChartDateGaps([{date:'2026-02-30'},{date:'../../ignore'},{date:'2026-05-01'}])).toEqual([]);
  });
  it('여러 간격을 보존하고 입력을 정렬하거나 변경하지 않는다', () => {
    const rows=[{date:'2026-01-01'}, {date:'2026-01-09'}, {date:'2026-02-01'}];
    expect(findChartDateGaps(rows)).toEqual([{from:'2026-01-01',to:'2026-01-09',days:8},{from:'2026-01-09',to:'2026-02-01',days:23}]);
    expect(rows.map(r=>r.date)).toEqual(['2026-01-01','2026-01-09','2026-02-01']);
  });
});
