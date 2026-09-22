// Regression: [FLOW-016] 누적성과 표의 순번이 페이지마다 처음부터 다시 매겨지던 문제
//
// 순번을 `trades.length - idx` 로 매겨서, 서버가 잘라 보낸 현재 페이지 배열만 셌다.
// 1페이지와 2페이지가 모두 50번부터 시작해 서로 다른 거래에 같은 번호가 붙었다.
// 순번은 서버의 pagination(total·page·limit)으로 전체 목록 기준으로 매기고,
// 결과·등급 필터가 켜져도 행이 숨을 뿐 각 거래의 번호는 그대로 남아야 한다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

const trade = (id: string, name: string, outcome: string) => ({
  id, date: '2026-09-01', grade: 'A', name, code: '005930',
  market: 'KOSPI', entry: 70000, outcome, roi: 1, maxHigh: 0,
  priceTrail: [], days: 2, score: 12, themes: [],
});

const PAGE_TRADES = [
  trade('a', '가종목', 'LOSS'),
  trade('b', '나종목', 'WIN'),
  trade('c', '다종목', 'LOSS'),
];

function mockResponse(pagination: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({ trades: PAGE_TRADES, kpi: {}, pagination }),
    })),
  );
}

// 표 본문의 각 행에서 첫 칸(#)을 읽는다.
function rowNumbers(): string[] {
  return Array.from(document.querySelectorAll('tbody tr')).map(
    (tr) => tr.querySelector('td')?.textContent ?? '',
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-016] 누적성과 표의 순번', () => {
  it('서버가 알려준 전체 건수와 페이지로 번호를 매긴다', async () => {
    // 전체 234건 중 2페이지(51~100번째)이므로 첫 행은 234 - 50 = 184 다.
    mockResponse({ total: 234, page: 2, limit: 50, totalPages: 5 });

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('가종목')).not.toBeNull());
    expect(rowNumbers()).toEqual(['184', '183', '182']);
  });

  it('필터가 켜져도 남은 행의 번호를 바꾸지 않는다', async () => {
    mockResponse({ total: 234, page: 2, limit: 50, totalPages: 5 });

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('가종목')).not.toBeNull());
    fireEvent.click(screen.getByRole('button', { name: /^성공/ }));

    await waitFor(() => expect(screen.queryByText('가종목')).toBeNull());
    expect(rowNumbers()).toEqual(['183']);
  });

  it('pagination 이 없으면 현재 배열 기준으로 매긴다', async () => {
    mockResponse(undefined);

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('가종목')).not.toBeNull());
    expect(rowNumbers()).toEqual(['3', '2', '1']);
  });
});
