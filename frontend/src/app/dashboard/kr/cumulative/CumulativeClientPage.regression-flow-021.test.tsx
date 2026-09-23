// Regression: [FLOW-021] 필터·페이지 재조회마다 화면 전체가 로딩 스피너로 바뀌던 문제
//
// 전체 화면 스피너는 첫 응답 전에만 쓴다. 재조회 중에는 KPI·필터를 그대로 두고 표 영역만
// 바쁨 상태로 둔다. 필터가 켜진 채 0건이면 기간이 아니라 필터 때문이라고 적는다.

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

const COUNTS = {
  total: 1,
  outcome: { WIN: 1, LOSS: 0, OPEN: 0 },
  grade: { S: 0, A: 1, B: 0, D: 0 },
};

const response = (trades: unknown[]) => ({
  ok: true,
  json: async () => ({
    kpi: { totalSignals: 1 },
    counts: COUNTS,
    trades,
    pagination: { total: trades.length, page: 1, limit: 50, totalPages: 1 },
  }),
});

const firstTrade = {
  id: '가종목', no: 1, date: '2026-09-01', grade: 'A', name: '가종목', code: '005930',
  market: 'KOSPI', entry: 70000, outcome: 'WIN', roi: 5, maxHigh: 6,
  priceTrail: [], days: 2, score: 12, themes: [],
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-021] 재조회 중 화면 유지와 필터 0건 문구', () => {
  it('필터 재조회 중에도 필터 버튼과 표가 남고, 필터 0건이면 필터 문구를 쓴다', async () => {
    let release: (value: unknown) => void = () => {};
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response([firstTrade]))
      .mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    vi.stubGlobal('fetch', fetchMock);

    render(<CumulativeClientPage />);
    await screen.findByText('가종목');

    fireEvent.click(screen.getAllByRole('button', { name: /^D/ })[0]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('데이터 불러오는 중...')).toBeNull();
    expect(screen.getAllByRole('button', { name: /^D/ })[0]).toBeTruthy();
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();

    release(response([]));
    expect(await screen.findByText('선택한 필터에 해당하는 거래가 없습니다.')).toBeTruthy();
    expect(document.querySelector('[aria-busy="true"]')).toBeNull();
  });
});
