// Regression: [JONGGA-010] — 오늘 자료가 아닌 리포트에서 일괄 매수만 막히고 카드의
// `모의 매수` 버튼은 살아 있던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-010] (2026-09-02 JONGGA-009 마감 qa-only ISSUE-001)
//
// `[JONGGA-009]` 이후 Latest Report 가 오늘 자료가 없으면 가장 최근 저장분을 그대로
// 싣는다. 그 화면에서 카드별 매수 버튼이 열려 있으면, 일괄 매수가 막으려던 결과에
// 종목 수만큼 반복해서 도달한다.

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });

/** 오프셋을 명시해 로컬 타임존과 무관하게 KST 기준 그 날짜의 정오가 되게 한다. */
const kstNoon = (msOffset: number) =>
  `${KST_DATE.format(new Date(Date.now() + msOffset))}T12:00:00+09:00`;

const TODAY = () => kstNoon(0);
const YESTERDAY = () => kstNoon(-24 * 60 * 60 * 1000);

const state = vi.hoisted(() => ({ updatedAt: '' }));

const SIGNAL = {
  stock_code: '096770',
  stock_name: '알파에너지',
  market: 'KOSPI',
  sector: '석유와가스',
  grade: 'A',
  score: {
    news: 2, volume: 3, chart: 3, candle: 2,
    consolidation: 2, timing: 2, supply: 2,
    llm_reason: '', total: 16,
  },
  checklist: {
    has_news: true, news_sources: [], is_new_high: true,
    is_breakout: true, supply_positive: true, volume_surge: true,
  },
  current_price: 134_400,
  entry_price: 134_400,
  stop_price: 127_680,
  target_price: 146_500,
  change_pct: 6.2,
  trading_value: 100_000_000_000,
};

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date(state.updatedAt)),
        total_candidates: 1,
        filtered_count: 1,
        signals: [SIGNAL],
        updated_at: state.updatedAt,
        status: 'ok',
      };
    }
    if (path === '/api/kr/jongga-v2/status') return { is_running: false };
    return {};
  }),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

const STALE_REASON = '현재 최신 리포트가 오늘 데이터가 아닙니다.';
const OPEN_REASON = '모의 계좌로 매수 주문을 실행합니다.';

const findCardBuyButton = async () =>
  (await screen.findByRole('button', { name: /모의 매수/ })) as HTMLButtonElement;

const findBulkBuyButton = () =>
  screen.getByRole('button', { name: /종가베팅 전체 10주 매수/ }) as HTMLButtonElement;

describe('[JONGGA-010] 종가베팅 카드의 매수 가드', () => {
  beforeEach(() => {
    state.updatedAt = TODAY();
  });

  it('오늘 저장분이면 카드의 매수 버튼을 누를 수 있다', async () => {
    render(<JonggaV2Page />);

    const button = await findCardBuyButton();
    expect(button.disabled).toBe(false);
    expect(button.getAttribute('title')).toBe(OPEN_REASON);
  });

  it('오늘 자료가 아닌 저장분이면 카드의 매수 버튼도 함께 막힌다', async () => {
    state.updatedAt = YESTERDAY();
    render(<JonggaV2Page />);

    const button = await findCardBuyButton();
    await waitFor(() => {
      expect(button.disabled).toBe(true);
    });
    expect(button.getAttribute('title')).toBe(STALE_REASON);
  });

  it('카드 버튼과 일괄 매수 버튼이 같은 사유 문구를 쓴다', async () => {
    state.updatedAt = YESTERDAY();
    render(<JonggaV2Page />);

    const cardButton = await findCardBuyButton();
    await waitFor(() => {
      expect(cardButton.disabled).toBe(true);
    });

    const bulkButton = findBulkBuyButton();
    expect(bulkButton.disabled).toBe(true);
    expect(bulkButton.getAttribute('title')).toBe(STALE_REASON);
    expect(cardButton.getAttribute('title')).toBe(bulkButton.getAttribute('title'));
  });
});
