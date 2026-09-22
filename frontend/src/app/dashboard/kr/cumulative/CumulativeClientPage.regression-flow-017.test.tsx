// Regression: [FLOW-017] 결과·등급 필터가 현재 페이지 50건 안에서만 걸리던 문제
//
// 서버가 잘라 보낸 한 페이지를 화면이 다시 걸러서, 「성공」을 눌러도 전체 성공 건이 아니라
// 그 페이지 안의 성공만 보였고 페이지 수도 그대로였다. 이제 필터는 요청 파라미터로 서버에
// 걸리고, 버튼 건수는 서버가 전체 목록에서 센 counts 를 읽는다. 순번은 서버가 필터 전
// 전체 목록 기준으로 매긴 no 를 그대로 쓴다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

const trade = (no: number, name: string, outcome: string, grade: string) => ({
  id: name, no, date: '2026-09-01', grade, name, code: '005930',
  market: 'KOSPI', entry: 70000, outcome, roi: 1, maxHigh: 0,
  priceTrail: [], days: 2, score: 12, themes: [],
});

// 현재 페이지에는 성공 1건만 있지만 전체 목록에는 86건이 있다.
const COUNTS = {
  total: 234,
  outcome: { WIN: 86, LOSS: 130, OPEN: 18 },
  grade: { S: 20, A: 90, B: 117, D: 7 },
};

function stubFetch() {
  const fetchMock = vi.fn(async (input: string) => {
    const winOnly = input.includes('outcome=WIN');
    return {
      ok: true,
      json: async () => ({
        kpi: {},
        counts: COUNTS,
        trades: winOnly
          ? [trade(179, '성공종목', 'WIN', 'A')]
          : [trade(184, '가종목', 'LOSS', 'B'), trade(179, '성공종목', 'WIN', 'A')],
        pagination: winOnly
          ? { total: 86, page: 1, limit: 50, totalPages: 2 }
          : { total: 234, page: 2, limit: 50, totalPages: 5 },
      }),
    };
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function rowNumbers(): string[] {
  return Array.from(document.querySelectorAll('tbody tr')).map(
    (tr) => tr.querySelector('td')?.textContent ?? '',
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-017] 누적성과 필터는 전체 기간에 걸린다', () => {
  it('버튼 건수는 현재 페이지가 아니라 서버가 센 전체 목록 건수다', async () => {
    stubFetch();
    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: '성공 (86)' })).toBeTruthy());
    expect(screen.getAllByRole('button', { name: '전체 (234)' })).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'D (7)' })).toBeTruthy();
    expect(screen.queryByText('현재 페이지 내')).toBeNull();
  });

  it('필터를 누르면 1페이지부터 서버에 다시 묻고 서버가 매긴 번호를 그린다', async () => {
    const fetchMock = stubFetch();
    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByText('가종목')).toBeTruthy());
    expect(rowNumbers()).toEqual(['184', '179']);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/kr/closing-bet/cumulative?page=2&limit=50'));

    fireEvent.click(screen.getByRole('button', { name: '성공 (86)' }));

    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/kr/closing-bet/cumulative?page=1&limit=50&outcome=WIN'));
    await waitFor(() => expect(screen.queryByText('가종목')).toBeNull());
    expect(rowNumbers()).toEqual(['179']);
  });

  it('등급 필터도 요청 파라미터로 보내고 두 필터를 함께 싣는다', async () => {
    const fetchMock = stubFetch();
    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'D (7)' })).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'D (7)' }));

    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/kr/closing-bet/cumulative?page=1&limit=50&grade=D'));

    fireEvent.click(screen.getByRole('button', { name: '성공 (86)' }));
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/kr/closing-bet/cumulative?page=1&limit=50&outcome=WIN&grade=D'));

    // 「전체」로 되돌리면 그 파라미터가 빠진다.
    fireEvent.click(screen.getAllByRole('button', { name: '전체 (234)' })[1]);
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/kr/closing-bet/cumulative?page=1&limit=50&outcome=WIN'));
  });
});
