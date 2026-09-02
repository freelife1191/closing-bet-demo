// Regression: [FLOW-004] 손실이 없는 구간에서 손익비 자리에 총이익이 그대로 나오던 문제
//
// 백엔드가 gross_loss 가 0 일 때 분자인 총이익을 그대로 돌려주었다. ROI +9% 짜리
// 다섯 건이면 손익비가 45.0 으로 표시되고, 그 값이 화면의 2.0 기준에 걸려 언제나
// "탁월한 손익비" 로 평가되었다. 이제 백엔드가 null 을 보내고 화면은 값을 비워 둔다.

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

const BASE_KPI = {
  totalSignals: 5,
  wins: 5,
  losses: 0,
  open: 0,
  winRate: 100,
  avgRoi: 9,
  totalRoi: 45,
  avgDays: 1.2,
  priceDate: '2026-05-22',
  roiByGrade: {},
};

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

function mockCumulativeResponse(profitFactor: number | null) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        trades: [],
        kpi: { ...BASE_KPI, profitFactor },
        pagination: { total: 0, page: 1, limit: 20, totalPages: 0 },
      }),
    })),
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-004] 손익비 표시', () => {
  it('손익비가 없으면 값 자리를 비워 둔다', async () => {
    mockCumulativeResponse(null);

    render(<CumulativeClientPage />);

    // 데이터 기준일이 그려지면 KPI 가 화면에 반영된 뒤다.
    await waitFor(() => expect(screen.queryByText('2026-05-22')).not.toBeNull());
    // 총이익 45 가 손익비 자리에 새어 나오지 않아야 한다.
    expect(screen.queryByText('45')).toBeNull();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('손익비가 있으면 그 값을 그대로 보여준다', async () => {
    mockCumulativeResponse(1.22);

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('1.22')).not.toBeNull());
  });
});
