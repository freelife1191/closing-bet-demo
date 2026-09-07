// Regression: [VCP-011] — AI 요약이 표·차트와 다른 수축비율과 점수를 말하던 문제
//
// 상세 패널의 점수 카드가 `score`(종합 시그널 점수 0~100)를 그리면서 이름은
// 「VCP Score」였다. AI 사유는 같은 화면에서 `vcp_score`(VCP 패턴 보조 점수 0~20)를
// 「VCP 패턴 보조 점수」라고 부르므로, 두 값이 서로 어긋난 것처럼 읽혔다.
//
// 그 아래 문장은 값과 무관하게 「기술적 압축이 양호」·「추세 지속 가능성이 높음」을
// 단정했다. 수축비율이 1.88 이어도 같은 문장이 나왔다.

import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const SIGNAL = {
  ticker: '034730',
  name: 'SK',
  market: 'KOSPI',
  signal_date: '2026-05-05',
  entry_price: 475500,
  current_price: 475500,
  return_pct: 0,
  foreign_5d: 113011707500,
  inst_5d: 32458164500,
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
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

const openDetailPanel = async () => {
  render(<VCPPage />);
  fireEvent.click(await screen.findByText('SK'));
  return (await screen.findByText('종합 시그널 점수')).closest('div')!.parentElement!;
};

describe('[VCP-011] VCP 상세의 점수 카드', () => {
  it('두 점수를 각자의 이름으로 따로 보여 준다', async () => {
    const card = await openDetailPanel();

    expect(within(card).getByText('종합 시그널 점수')).toBeTruthy();
    expect(within(card).getByText('100.0')).toBeTruthy();
    expect(within(card).getByText('VCP 패턴 보조 점수')).toBeTruthy();
    expect(within(card).getByText('17.0')).toBeTruthy();
  });

  it('값과 무관하게 낙관적 결론을 단정하지 않는다', async () => {
    const card = await openDetailPanel();

    // 수축비율 1.8811 은 압축이 풀린 상태인데 예전에는 이 문장이 그대로 나왔다.
    expect(card.textContent).not.toContain('기술적 압축이 양호');
    expect(card.textContent).not.toContain('추세 지속 가능성이 높음');
    expect(card.textContent).toContain('1.88');
  });
});
