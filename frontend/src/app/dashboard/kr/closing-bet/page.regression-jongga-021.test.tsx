// Regression: [JONGGA-021] — 「크게 보기」 차트가 그 카드의 종목이 아니라 다른 종목을
// 그리던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-021] (2026-09-03 JONGGA-015 사이클의 qa-only ISSUE-002)
//
// TradingView 임베드 위젯은 무료 등급이 KRX 시세를 제공하지 않아, 앱이 정확한 심볼
// (KRX:044490)을 넘겨도 기본 심볼(애플)로 조용히 바꿔 그렸다. iframe 이 교차 출처라서
// 앱이 그 대체를 감지할 방법도 없었다. 종목코드로 주소를 조립하는 이미지로 바꿔,
// 다른 종목이 섞이지 않고 실패는 화면에 드러나게 했다.

import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page, { stockChartUrl } from './page';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });
const TODAY = () => `${KST_DATE.format(new Date())}T12:00:00+09:00`;

const SIGNAL = {
  stock_code: '044490',
  stock_name: '태웅',
  market: 'KOSDAQ',
  sector: '기계',
  grade: 'B',
  score: { total: 12, base_score: 12, bonus_score: 0 },
  checklist: { has_news: false, volume_surge: false, supply_positive: false },
  current_price: 37_250,
  entry_price: 37_200,
  stop_price: 36_084,
  target_price: 39_060,
  change_pct: 11.5,
  trading_value: 100_000_000_000,
  signal_date: '2026-09-02',
};

const state = vi.hoisted(() => ({ signal: {} as Record<string, unknown> }));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date()),
        total_candidates: 1,
        filtered_count: 1,
        signals: [state.signal],
        updated_at: TODAY(),
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

// 카드의 미니차트를 눌러 「크게 보기」 모달을 연다. 모달 안의 차트 이미지를 돌려준다.
async function openChart() {
  render(<JonggaV2Page />);
  await screen.findByText('₩37,250');

  const miniCharts = document.querySelectorAll('[data-testid="mini-chart"]');
  expect(miniCharts.length).toBe(1);
  fireEvent.click(miniCharts[0]);

  return document.querySelector('img[alt*="태웅"]') as HTMLImageElement | null;
}

describe('[JONGGA-021] 「크게 보기」 차트의 종목', () => {
  beforeEach(() => {
    state.signal = { ...SIGNAL };
  });

  it('주소를 종목코드로 조립하므로 다른 종목이 섞일 수 없다', () => {
    expect(stockChartUrl('044490', 'day')).toContain('/044490.png');
    expect(stockChartUrl('138040', 'week')).toContain('/138040.png');
    expect(stockChartUrl('0007C0', 'month')).toContain('/0007C0.png');
  });

  it('차트 이미지가 그 카드의 종목코드를 가리킨다', async () => {
    const img = await openChart();

    expect(img).toBeTruthy();
    expect(img!.getAttribute('src')).toBe(stockChartUrl('044490', 'day'));
    expect(img!.getAttribute('alt')).toContain('044490');
  });

  it('기간 버튼을 누르면 그 기간의 주소로 바뀐다', async () => {
    await openChart();

    fireEvent.click(screen.getByText('주봉'));
    const img = document.querySelector('img[alt*="태웅"]') as HTMLImageElement;
    expect(img.getAttribute('src')).toBe(stockChartUrl('044490', 'week'));
  });

  it('차트를 못 불러오면 그 사실을 알리고 다른 차트로 대체하지 않는다', async () => {
    const img = await openChart();
    fireEvent.error(img as Element);

    expect(screen.getByText(/차트를 불러오지 못했습니다/)).toBeTruthy();
    expect(document.querySelector('img[alt*="태웅"]')).toBeNull();
  });

  it('TradingView 스크립트를 더 이상 문서에 붙이지 않는다', async () => {
    await openChart();

    const scripts = Array.from(document.querySelectorAll('script'));
    expect(scripts.some((s) => (s.src || '').includes('tradingview'))).toBe(false);
    expect(document.querySelector('iframe')).toBeNull();
  });
});
