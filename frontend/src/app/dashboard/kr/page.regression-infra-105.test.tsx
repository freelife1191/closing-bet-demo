// Regression: [INFRA-105] — 섹터 ETF 등락률을 조회하지 못하면 Flask 가 change_pct 를 null 로 보낸다.
// 종전에는 0.0 으로 채워 0.00% 로 보였고, null 을 그대로 받으면 toFixed 에서 화면이 깨진다.

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import KRDashboardPage from './page';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async () => ({
    vcp: { status: 'GOOD', count: 12, win_rate: 55, avg_return: 3.1 },
    closing_bet: { status: 'GOOD', count: 8, win_rate: 62, avg_return: 2.4, candidates: [] },
  })),
  krAPI: {
    getMarketGate: vi.fn(async () => ({
      status: 'GREEN',
      score: 70,
      message: '',
      sectors: [
        { name: '반도체', change_pct: -3.21, signal: 'Bearish' },
        { name: '은행', change_pct: null, signal: 'Neutral' },
      ],
    })),
    getSignals: vi.fn(async () => ({ signals: [], count: 0 })),
    getDataStatus: vi.fn(async () => ({ data: {} })),
    updateMarketGate: vi.fn(),
  },
}));

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ interval: 30 }) })));
});

describe('[INFRA-105] 섹터 등락률 결측 표시', () => {
  it('결측 섹터는 0.00% 대신 — 로 보이고 조회된 섹터는 등락률을 유지한다', async () => {
    render(<KRDashboardPage />);

    const missing = await screen.findByText('은행');
    expect(missing.parentElement).toHaveTextContent('—');
    expect(missing.parentElement).not.toHaveTextContent('%');
    // Neutral 신호라도 보합(노란) 색을 입히지 않는다
    expect(missing.parentElement?.className).toContain('bg-gray-500/10');
    expect(missing.parentElement?.className).not.toContain('yellow');
    expect(screen.getByText('반도체').parentElement).toHaveTextContent('-3.21%');
  });
});
