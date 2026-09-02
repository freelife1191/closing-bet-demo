// Regression: [FE-013] — 과거 날짜에서 일괄 매수만 막히고 행별 매수 버튼은 살아 있던 문제
// 근거: docs/dev-cycle/TODO.md [FE-013] (2026-09-02 VCP-007 마감 qa-only)

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const SIGNAL = {
  ticker: '034730',
  name: '알파테크',
  signal_date: '2026-05-05',
  score: 90,
  is_vcp: true,
  entry_price: 475_500,
  current_price: 586_000,
};

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({ signals: [SIGNAL], total_scanned: 1, source: 'test' })),
    getSignalDates: vi.fn(async () => ['2026-05-05']),
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

const LATEST_REASON = '모의 계좌로 매수 주문을 실행합니다.';
const HISTORY_REASON = '최신(오늘) VCP 시그널 탭에서만 매수를 실행할 수 있습니다.';

const findRowBuyButton = async (title: string) => {
  const row = (await screen.findByText('알파테크')).closest('tr') as HTMLElement;
  return within(row).getByTitle(title) as HTMLButtonElement;
};

const selectHistoryDate = async () => {
  fireEvent.click(screen.getByRole('button', { name: '과거' }));
  fireEvent.click(await screen.findByRole('button', { name: '2026-05-05' }));
};

describe('VCPPage - 과거 날짜 매수 가드', () => {
  it('최신 탭에서는 행별 매수 버튼을 누를 수 있다', async () => {
    render(<VCPPage />);

    expect((await findRowBuyButton(LATEST_REASON)).disabled).toBe(false);
  });

  it('과거 날짜를 고르면 행별 매수 버튼도 함께 막히고 같은 사유를 알린다', async () => {
    render(<VCPPage />);
    await findRowBuyButton(LATEST_REASON);

    await selectHistoryDate();

    await waitFor(async () => {
      expect((await findRowBuyButton(HISTORY_REASON)).disabled).toBe(true);
    });
  });

  it('과거 날짜에서 일괄 매수 버튼도 행별 버튼과 같은 사유로 막힌다', async () => {
    render(<VCPPage />);
    await findRowBuyButton(LATEST_REASON);

    await selectHistoryDate();

    await waitFor(() => {
      const bulkButton = screen.getByRole('button', { name: /VCP 전체 10주 매수/ }) as HTMLButtonElement;
      expect(bulkButton.disabled).toBe(true);
      expect(bulkButton.getAttribute('title')).toBe(HISTORY_REASON);
    });
  });
});
