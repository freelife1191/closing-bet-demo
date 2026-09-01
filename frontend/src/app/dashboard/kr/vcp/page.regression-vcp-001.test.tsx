// Regression: [VCP-001] — AI 분석에 실패한 종목이 노란색 "관망" 배지로 표시되던 문제
// 근거: docs/dev-cycle/audits/AUDIT-VCP.md §1.1

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

// 재분석이 실패하면 백엔드가 action 에 "N/A" 를, reason 에 "분석 실패" 를 남긴다.
const FAILED_SIGNAL = {
  ticker: '005930',
  name: '알파테크',
  signal_date: '2026-09-01',
  score: 88,
  is_vcp: true,
  gemini_recommendation: {
    action: 'N/A',
    confidence: 0,
    reason: '분석 실패',
    news_sentiment: 'positive',
  },
};

const HOLD_SIGNAL = {
  ticker: '000660',
  name: '베타소재',
  signal_date: '2026-09-01',
  score: 85,
  is_vcp: true,
  gemini_recommendation: {
    action: 'HOLD',
    confidence: 62,
    reason: '변동성 수축이 지속되어 관망합니다.',
    news_sentiment: 'positive',
  },
};

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({
      signals: [FAILED_SIGNAL, HOLD_SIGNAL],
      total_scanned: 2,
      source: 'test',
    })),
    getSignalDates: vi.fn(async () => []),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus: vi.fn(async () => ({ is_running: false })),
  },
  fetchAPI: vi.fn(async () => ({})),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('./StockChart', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ConfirmationModal', () => ({ default: () => null }));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

describe('VCPPage - AI 배지', () => {
  it('AI 분석에 실패한 종목에는 관망 배지를 달지 않는다', async () => {
    render(<VCPPage />);

    const failedRow = (await screen.findByText('알파테크')).closest('tr');
    expect(failedRow).not.toBeNull();
    expect(within(failedRow as HTMLElement).queryByText(/관망/)).toBeNull();
  });

  it('HOLD 의견이 나온 종목에는 관망 배지를 그대로 단다', async () => {
    render(<VCPPage />);

    const holdRow = (await screen.findByText('베타소재')).closest('tr');
    expect(holdRow).not.toBeNull();
    expect(within(holdRow as HTMLElement).queryByText(/관망/)).not.toBeNull();
  });
});
