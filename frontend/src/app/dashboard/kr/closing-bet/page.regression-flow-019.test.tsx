// Regression: [FLOW-019] 종가베팅 화면이 D 등급을 말없이 빼던 문제
//
// 누적성과와 백테스트 요약은 과거 등급 D 를 통계에 넣는데 이 화면은 D 를 목록에서 뺀다.
// 모든 종목이 D 일 때만 빈 화면 문구가 그 사실을 말했고, 다른 등급과 섞여 있으면 몇 종목이
// 빠졌는지 어디에도 나오지 않았다.

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const signal = (code: string, name: string, grade: string) => ({
  stock_code: code,
  stock_name: name,
  market: 'KOSPI',
  sector: '기계',
  grade,
  score: { total: 12, base_score: 12, bonus_score: 0 },
  checklist: { has_news: false, volume_surge: false, supply_positive: false },
  current_price: 37_250,
  entry_price: 37_200,
  stop_price: 36_084,
  target_price: 39_060,
  change_pct: 11.5,
  trading_value: 100_000_000_000,
  signal_date: '2026-02-11',
});

const state = vi.hoisted(() => ({ signals: [] as Record<string, unknown>[] }));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return { date: '2026-02-11', total_candidates: 3, filtered_count: state.signals.length, signals: state.signals };
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

describe('[FLOW-019] D 등급 제외 안내', () => {
  it('D 가 다른 등급과 섞여 있으면 뺀 종목 수와 통계 포함 사실을 알린다', async () => {
    state.signals = [signal('044490', '태웅', 'B'), signal('000001', '디종목', 'D'), signal('000002', '디둘', 'd')];
    render(<JonggaV2Page />);
    await screen.findByRole('heading', { name: '태웅' });

    expect(screen.getByText(/D등급\(현행 기준 미달 또는 과거 등급\) 2종목은 매수 대상이 아니어서 목록에서 제외했습니다/)).toBeTruthy();
    expect(screen.queryByRole('heading', { name: '디둘' })).toBeNull();
  });

  it('전부 D 이면 이 안내 대신 빈 화면 문구가 설명한다', async () => {
    state.signals = [signal('000001', '디종목', 'D')];
    render(<JonggaV2Page />);

    expect(await screen.findByText('표시할 수 있는 종목이 없습니다.')).toBeTruthy();
    expect(screen.queryByText(/목록에서 제외했습니다/)).toBeNull();
  });

  it('D 가 없으면 안내를 띄우지 않는다', async () => {
    state.signals = [signal('044490', '태웅', 'B')];
    render(<JonggaV2Page />);
    await screen.findByRole('heading', { name: '태웅' });

    expect(screen.queryByText(/목록에서 제외했습니다/)).toBeNull();
  });
});
