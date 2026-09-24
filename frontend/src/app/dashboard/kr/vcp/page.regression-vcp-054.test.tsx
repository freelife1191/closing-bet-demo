// Regression: [VCP-054] — 수급 결측을 「순매수 0」처럼 그리던 문제
//
// [VCP-050] 뒤로 signals_log.csv 는 수급 결측을 빈 칸으로 남기고 API 는 null 로 보낸다.
// 표는 `> 0` 이 아니면 빨간 글씨로 그려서 결측도 매도처럼 보였고, 상세 문구는 `-원` 이 됐다.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const SIGNAL = {
  ticker: '034730',
  name: 'SK',
  market: 'KOSPI' as const,
  signal_date: '2026-05-05',
  entry_price: 475500,
  current_price: 475500,
  return_pct: 0,
  foreign_5d: null,
  inst_5d: 0,
  score: 100,
  vcp_score: 17,
  contraction_ratio: 1.8811,
};

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({ signals: [SIGNAL], total_scanned: 1, source: 'test' })),
    getSignalDates: vi.fn(async () => []),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus: vi.fn(async () => ({ is_running: false })),
    getStockChart: vi.fn(async () => ({ ticker: '034730', data: [] })),
  },
  fetchAPI: vi.fn(async () => ({})),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('./StockChart', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ConfirmationModal', () => ({ default: () => null }));
vi.mock('@/app/components/Modal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/app/components/Modal')>();
  return { ...actual, default: () => null };
});
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

describe('[VCP-054] VCP 수급 결측 표기', () => {
  it('표는 결측을 회색 -로, 실제 0 은 0 으로 그린다', async () => {
    render(<VCPPage />);
    const cells = (await screen.findByText('SK')).closest('tr')!.querySelectorAll('td');
    const foreign = Array.from(cells).find((td) => td.textContent === '-')!;
    const inst = Array.from(cells).find((td) => td.textContent === '0')!;

    expect(foreign.className).toContain('text-gray-500');
    expect(foreign.className).not.toContain('text-red-400');
    expect(foreign.querySelector('i')).toBeNull();
    expect(inst).toBeTruthy();
  });

  it('상세 문구는 결측에 원을 붙이지 않는다', async () => {
    render(<VCPPage />);
    fireEvent.click(await screen.findByText('SK'));
    const card = (await screen.findByText('종합 시그널 점수')).closest('div')!.parentElement!;

    expect(card.textContent).toContain('외국인 5일 순매수 - · 기관 5일 순매수 0원');
  });
});
