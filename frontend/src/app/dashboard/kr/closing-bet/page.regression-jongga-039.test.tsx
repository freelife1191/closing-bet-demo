// Regression: [JONGGA-039] — 「최신」 배너가 표시 중인 사실을 감추던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-039] (2026-09-22)
//
// 배너는 굵은 제목 「오늘 종가베팅 데이터가 아직 없습니다.」 아래 stale_warning 을 우선 보여,
// 백엔드가 함께 보내는 message(「가장 최근 저장분을 그대로 보여주고 있습니다」)가 어디에도
// 나오지 않았다. 목록이 있어도 두 줄 모두 「없다」 고 읽힌다.

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

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
  signal_date: '2026-09-21',
};

const state = vi.hoisted(() => ({ signals: [] as Record<string, unknown>[] }));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: '2026-09-21',
        total_candidates: 1,
        filtered_count: state.signals.length,
        signals: state.signals,
        updated_at: '2026-09-21T17:10:00+09:00',
        status: 'stale',
        is_stale: true,
        latest_available_date: '2026-09-21',
        stale_warning: '오늘(2026-09-22) 기준 종가베팅 데이터가 없습니다. 최신 저장 데이터는 2026-09-21입니다.',
        message:
          '오늘 분석이 아직 없어서 가장 최근 저장분을 그대로 보여주고 있습니다. [업데이트] 버튼을 눌러 오늘 분석을 실행해주세요.',
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

describe('[JONGGA-039] 「최신」 배너', () => {
  it('저장분을 보이는 동안에는 제목이 표시 중인 날짜를 말하고 message 줄을 함께 보인다', async () => {
    state.signals = [SIGNAL];
    render(<JonggaV2Page />);
    await screen.findByRole('heading', { name: '태웅' });

    expect(screen.getByText('오늘 분석은 아직 없습니다. 최신 저장분(2026-09-21)을 표시합니다.')).toBeTruthy();
    expect(screen.getByText(/가장 최근 저장분을 그대로 보여주고 있습니다/)).toBeTruthy();
    expect(screen.queryByText('오늘 종가베팅 데이터가 아직 없습니다.')).toBeNull();
  });

  it('보일 저장분이 없으면 종전 제목과 stale_warning 을 유지한다', async () => {
    state.signals = [];
    render(<JonggaV2Page />);

    expect(await screen.findByText('오늘 종가베팅 데이터가 아직 없습니다.')).toBeTruthy();
    expect(screen.getByText(/최신 저장 데이터는 2026-09-21입니다/)).toBeTruthy();
  });
});
