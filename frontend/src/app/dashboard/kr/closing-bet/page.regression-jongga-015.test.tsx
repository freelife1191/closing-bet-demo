// Regression: [JONGGA-015] — 카드가 「현재가」라는 이름으로 최근 거래일의 종가를 보여주고,
// 매수·목표·손절가가 어느 값에서 파생되는지 밝히지 않던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-015] (2026-09-03 JONGGA-005 사이클의 qa-only ISSUE-001)
//
// 카드의 `current_price` 는 daily_prices.csv 의 최신 종가이고, 상세 모달의 「현재」는
// 실시간 시세다. 두 값은 원래 다른 것을 가리키는데 이름이 같은 것처럼 붙어 있었다.
// 목표가와 손절가는 그 「현재가」가 아니라 매수가에서 파생된다.

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });
const TODAY = () => `${KST_DATE.format(new Date())}T12:00:00+09:00`;

// 실제 자료(data/jongga_v2_latest.json)의 태웅과 같은 값 관계를 쓴다.
// entry 37,200 → target 39,060(+5%) / stop 36,084(-3%), current 는 그와 무관한 37,250.
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

describe('[JONGGA-015] 종가베팅 카드의 가격 어휘', () => {
  beforeEach(() => {
    state.signal = { ...SIGNAL };
  });

  it('가격 자리를 「현재가」가 아니라 「종가」라고 부른다', async () => {
    render(<JonggaV2Page />);

    // 지표 라벨은 값과 같은 블록에 놓인다. 값에서 거슬러 올라가 라벨을 짚는다.
    const priceValue = await screen.findByText('₩37,250');
    const metricBlock = priceValue.closest('.text-center');
    expect(metricBlock?.textContent).toContain('종가');
    expect(metricBlock?.textContent).not.toContain('현재가');
  });

  it('화면 어디에도 「현재가」라는 말이 남아 있지 않다', async () => {
    render(<JonggaV2Page />);

    // 툴팁 문구까지 포함해 확인한다. 「상승률」 툴팁도 같은 말을 쓰고 있었다.
    await screen.findByText('₩37,250');
    expect(document.body.textContent).not.toContain('현재가');
  });

  it('종가 값 자체는 달라지지 않는다', async () => {
    render(<JonggaV2Page />);

    expect(await screen.findByText('₩37,250')).toBeTruthy();
  });

  it('매수가 옆에 어느 날 종가인지 적는다', async () => {
    render(<JonggaV2Page />);

    expect(await screen.findByText('(2026-09-02 종가)')).toBeTruthy();
  });

  it('목표가와 손절가 옆에 매수가 대비 비율을 적는다', async () => {
    render(<JonggaV2Page />);

    expect(await screen.findByText('(매수가 +5.0%)')).toBeTruthy();
    expect(screen.getByText('(매수가 -3.0%)')).toBeTruthy();
  });

  it('매수가가 없으면 비율 자리를 비운다', async () => {
    state.signal = { ...SIGNAL, buy_price: 0, entry_price: 0 };
    render(<JonggaV2Page />);

    await screen.findByText('₩37,250');
    expect(document.body.textContent).not.toContain('매수가 +');
    expect(document.body.textContent).not.toContain('매수가 -');
    expect(document.body.textContent).not.toContain('NaN');
    expect(document.body.textContent).not.toContain('Infinity');
  });

  it('목표가가 없으면 그 자리에만 비율을 그리지 않는다', async () => {
    state.signal = { ...SIGNAL, target_price: 0 };
    render(<JonggaV2Page />);

    await screen.findByText('₩37,250');
    expect(document.body.textContent).not.toContain('매수가 +');
    expect(screen.getByText('(매수가 -3.0%)')).toBeTruthy();
  });
});
