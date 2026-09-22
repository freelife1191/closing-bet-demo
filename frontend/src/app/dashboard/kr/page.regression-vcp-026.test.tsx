// Regression: [VCP-026] — 홈 「오늘의 시그널」 칸이 최신 저장분을 셀 때는 기준일을 밝힌다.
// 같은 /api/kr/signals 를 쓰므로 오늘 스캔 전에는 어제 건수가 내려온다.

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KRDashboardPage from './page';

const { mockGetSignals } = vi.hoisted(() => ({
  mockGetSignals: vi.fn(),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async () => ({
    vcp: { status: 'GOOD', count: 12, win_rate: 55, avg_return: 3.1 },
    closing_bet: { status: 'GOOD', count: 8, win_rate: 62, avg_return: 2.4, candidates: [] },
  })),
  krAPI: {
    getMarketGate: vi.fn(async () => ({ status: 'GREEN', score: 70, message: '' })),
    getSignals: (...args: unknown[]) => mockGetSignals(...args),
    getDataStatus: vi.fn(async () => ({ data: {} })),
    updateMarketGate: vi.fn(),
  },
}));

const SIGNAL = {
  ticker: '005930',
  name: '삼성전자',
  market: 'KOSPI',
  signal_date: '2026-09-21',
  entry_price: 70000,
  current_price: 71000,
  return_pct: 1.4,
  foreign_5d: 1000,
  inst_5d: 2000,
  score: 85,
  contraction_ratio: 0.42,
};

beforeEach(() => {
  mockGetSignals.mockReset();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ interval: 30 }) })));
});

describe('[VCP-026] 홈 오늘의 시그널 기준일', () => {
  it('최신 저장분을 셀 때 기준일 문구를 보인다', async () => {
    mockGetSignals.mockResolvedValue({
      signals: [SIGNAL],
      stale_warning: '오늘(2026-09-22) 기준 VCP 시그널이 없어 최신 저장분(2026-09-21)을 표시합니다.',
    });
    render(<KRDashboardPage />);

    expect(await screen.findByText('최신 저장분(2026-09-21) 기준')).toBeInTheDocument();
    expect(screen.queryByText('VCP + 외국인 순매수')).toBeNull();
  });

  it('오늘 자 시그널이면 종전 문구를 유지한다', async () => {
    mockGetSignals.mockResolvedValue({ signals: [{ ...SIGNAL, signal_date: '2026-09-22' }] });
    render(<KRDashboardPage />);

    expect(await screen.findByText('VCP + 외국인 순매수')).toBeInTheDocument();
    expect(screen.queryByText(/최신 저장분/)).toBeNull();
  });
});
