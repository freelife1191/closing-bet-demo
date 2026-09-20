import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const api = vi.hoisted(() => ({ fetchAPI: vi.fn() }));

const SIGNAL = {
  stock_code: '000660',
  stock_name: 'SK하이닉스',
  market: 'KOSPI',
  sector: '반도체',
  grade: 'A',
  score: {
    news: 3, volume: 3, chart: 2, candle: 1, consolidation: 1, timing: 0, supply: 2,
    total: 15,
    llm_reason: '오래된 BUY 본문은 카드 본문에 보이면 안 됩니다.',
    ai_evaluation: { action: 'BUY', confidence: 91, reason: '오래된 BUY 판정입니다.' },
  },
  score_details: {
    ai_evaluation: { action: 'SELL', confidence: 88, reason: '오래된 SELL 판정입니다.' },
    rise_pct: 3.4,
  },
  ai_evaluation: { action: 'HOLD', confidence: 0, reason: '새 HOLD 판정 사유입니다.' },
  checklist: { has_news: true, news_sources: [], is_new_high: false, is_breakout: true, supply_positive: true, volume_surge: true },
  current_price: 184_500,
  entry_price: 176_000,
  stop_price: 170_720,
  target_price: 184_800,
  change_pct: 3.4,
  trading_value: 1_260_000_000_000,
  signal_date: '2026-09-18',
};

vi.mock('@/lib/api', () => ({ fetchAPI: api.fetchAPI }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false, isLoading: false }) }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

async function renderPage(): Promise<HTMLElement> {
  render(<JonggaV2Page />);
  const name = await screen.findByText('SK하이닉스');
  const card = name.closest('div.rounded-2xl.border');
  if (!card) throw new Error('종목 카드를 찾지 못했습니다.');
  return card as HTMLElement;
}

beforeEach(() => {
  api.fetchAPI.mockReset();
  api.fetchAPI.mockImplementation(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: '2026-09-18', total_candidates: 1, filtered_count: 1,
        signals: [SIGNAL], updated_at: '2026-09-18T15:40:00+09:00', status: 'ok',
      };
    }
    if (path === '/api/kr/jongga-v2/status') return { is_running: false };
    return {};
  });
});

describe('[JONGGA-024/028] 카드의 실제 차트와 AI 원천', () => {
  it('최신 HOLD 판정의 사유를 카드 배지와 본문에서 함께 쓴다', async () => {
    const card = await renderPage();

    expect(within(card).getByText('HOLD')).toBeTruthy();
    expect(within(card).getByText('0%')).toBeTruthy();
    expect(within(card).getByText('새 HOLD 판정 사유입니다.')).toBeTruthy();
    expect(within(card).queryByText('오래된 BUY 본문은 카드 본문에 보이면 안 됩니다.')).toBeNull();
  });

  it('종가 타일은 최신 current_price가 아니라 신호일 entry_price와 날짜를 함께 표시한다', async () => {
    const card = await renderPage();

    const signalClose = within(card).getByText('2026-09-18 종가').closest('.text-center') as HTMLElement;
    expect(within(signalClose).getByText('₩176,000')).toBeTruthy();
    expect(within(signalClose).queryByText('₩184,500')).toBeNull();
  });

  it('고정 미니 선 대신 실제 700px 차트를 가로 스크롤로 열고 실패해도 외부 링크를 남긴다', async () => {
    await renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'SK하이닉스 차트 크게 보기' }));
    const dialog = await screen.findByRole('dialog', { name: 'SK하이닉스' });
    const chart = within(dialog).getByRole('img', { name: 'SK하이닉스 000660 일봉 차트' });
    const scrollArea = chart.parentElement as HTMLElement;

    expect(chart.classList.contains('min-w-[700px]')).toBe(true);
    expect(scrollArea.classList.contains('overflow-x-auto')).toBe(true);
    expect(scrollArea.getAttribute('tabindex')).toBe('0');
    expect(scrollArea.getAttribute('aria-describedby')).toBeTruthy();
    expect(dialog.querySelector('polyline')).toBeNull();

    fireEvent.error(chart);
    expect(within(dialog).getByText(/차트를 불러오지 못했습니다/)).toBeTruthy();
    expect(within(dialog).getByRole('link', { name: '네이버 금융' }).getAttribute('href')).toContain('000660');
    expect(within(dialog).getByRole('link', { name: '토스 증권' }).getAttribute('href')).toContain('000660');
  });
});
