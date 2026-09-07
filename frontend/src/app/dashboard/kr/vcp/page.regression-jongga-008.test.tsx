// Regression: [JONGGA-008] — 확신도가 없는 종목의 상세 모달이 0% 게이지를 그리던 문제
//
// 백엔드가 값 없음을 0 으로 채워 보내던 자리를 None 으로 고쳤다. 화면이 예전처럼
// `?? 0` 으로 받으면 그 None 이 다시 0 이 되어 "AI 가 0% 확신한다" 는 게이지가 남는다.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const NO_CONFIDENCE_SIGNAL = {
  ticker: '034730',
  name: '알파테크',
  signal_date: '2026-05-05',
  score: 90,
  is_vcp: true,
  gemini_recommendation: {
    action: 'BUY',
    confidence: null,
    reason: '변동성 수축이 확인되어 매수 구간으로 봅니다.',
    news_sentiment: 'positive',
  },
};

const WITH_CONFIDENCE_SIGNAL = {
  ticker: '000660',
  name: '베타소재',
  signal_date: '2026-05-05',
  score: 85,
  is_vcp: true,
  gemini_recommendation: {
    action: 'HOLD',
    confidence: 62,
    reason: '수축이 이어지고 있어 관망합니다.',
    news_sentiment: 'positive',
  },
};

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({
      signals: [NO_CONFIDENCE_SIGNAL, WITH_CONFIDENCE_SIGNAL],
      total_scanned: 2,
      source: 'test',
    })),
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
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

const openDetail = async (name: string) => {
  const row = (await screen.findByRole('cell', { name: new RegExp(name) })).closest('tr');
  fireEvent.click(row as HTMLElement);
};

describe('[JONGGA-008] VCP 상세 모달의 확신도 게이지', () => {
  it('확신도가 없으면 0% 대신 미산출을 보인다', async () => {
    render(<VCPPage />);
    await openDetail('알파테크');

    expect(await screen.findByText('미산출')).toBeTruthy();
    expect(screen.queryByText('0%')).toBeNull();
  });

  it('확신도가 있으면 그 값을 그대로 보인다', async () => {
    render(<VCPPage />);
    await openDetail('베타소재');

    expect(await screen.findByText('62%')).toBeTruthy();
    expect(screen.queryByText('미산출')).toBeNull();
  });
});
