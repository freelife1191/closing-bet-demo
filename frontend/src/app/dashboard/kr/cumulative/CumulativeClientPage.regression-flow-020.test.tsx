// Regression: [FLOW-020] 「최고가」 열이 0 이하의 최대 상승률을 하이픈으로 숨기던 문제
//
// 서버는 일봉이 없을 때도 maxHigh 를 0 으로 보내므로 값만으로는 결측과 실제 0% 를 가를 수
// 없다. 일봉이 없는 갈래는 모두 days 가 0 이라, 하이픈은 그때만 쓰고 나머지는 부호를 붙여 적는다.

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

const MAX_HIGH_COLUMN = 7;

const trade = (name: string, maxHigh: number, days: number) => ({
  id: name, no: 1, date: '2026-09-01', grade: 'A', name, code: '032830',
  market: 'KOSPI', entry: 307000, outcome: 'LOSS', roi: -3, maxHigh,
  priceTrail: [], days, score: 12, themes: [],
});

beforeEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({
      kpi: {},
      trades: [
        trade('음수종목', -1.5, 3),
        trade('영종목', 0, 2),
        trade('양수종목', 2.1, 4),
        trade('자료없음종목', 0, 0),
      ],
      pagination: { total: 4, page: 1, limit: 50, totalPages: 1 },
    }),
  })));
});

describe('[FLOW-020] 최고가 열 표기', () => {
  it('일봉이 있으면 음수·0·양수를 부호와 함께 적고, 일봉이 없을 때만 하이픈을 쓴다', async () => {
    render(<CumulativeClientPage />);
    await screen.findByText('자료없음종목');

    const cells = Object.fromEntries(
      Array.from(document.querySelectorAll('tbody tr')).map((tr) => {
        const tds = tr.querySelectorAll('td');
        return [tds[3].querySelector('div')?.textContent, tds[MAX_HIGH_COLUMN].textContent];
      }),
    );

    expect(cells['음수종목']).toBe('-1.5%');
    expect(cells['영종목']).toBe('0%');
    expect(cells['양수종목']).toBe('+2.1%');
    expect(cells['자료없음종목']).toBe('-');
  });
});
