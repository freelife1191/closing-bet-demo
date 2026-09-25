// Regression: [FE-048] — 상세 모달이 결측인 Toss 5일 순매수를 0 처럼 그리던 문제
// 근거: docs/dev-cycle/TODO.md [FE-048]
//
// [INFRA-109] 이후 Toss 파서는 다섯 날 모두 빈 수량이면 합계를 null 로, 일부만 비면 값 있는 날의
// 합계를 돌려준다. KRX 확정 집계(investorTrend5Day)가 없어 모달이 Toss 합계로 물러서면,
// 고치기 전에는 null 을 0 으로 바꿔 「-」를 그렸고 4일 합계도 5일 값처럼 보였다.

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });

const SIGNAL = {
  stock_code: '044490',
  stock_name: '태웅',
  market: 'KOSDAQ',
  grade: 'B',
  score: { total: 12, base_score: 12, bonus_score: 0 },
  checklist: { has_news: false, volume_surge: false, supply_positive: false },
  current_price: 37_250,
  entry_price: 37_200,
  change_pct: 11.5,
  trading_value: 108_475_054_850,
  signal_date: '2026-09-02',
  score_details: {},
};

const DETAIL = {
  code: '044490',
  name: '태웅',
  market: 'KOSDAQ',
  priceInfo: { current: 37_000, prevClose: 37_250, open: 37_100, high: 37_500, low: 36_800, change: -250, change_pct: -0.67, volume: 1, trading_value: 1 },
  yearRange: { high_52w: 41_000, low_52w: 21_000 },
  indicators: { marketCap: 1, per: 12, pbr: 1.1, eps: 3_000, bps: 33_000, dividendYield: 1.2 },
  investorTrend: { foreign: null, institution: null, foreignDays: 0, institutionDays: 0, individual: null },
  financials: { revenue: 0, operatingProfit: 0, netIncome: 0 },
  safety: { debtRatio: 0, currentRatio: 0 },
};

const state = vi.hoisted(() => ({ detail: {} as Record<string, unknown> }));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date()),
        total_candidates: 1,
        filtered_count: 1,
        signals: [SIGNAL],
        updated_at: `${KST_DATE.format(new Date())}T12:00:00+09:00`,
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

vi.mock('@/app/components/Modal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/app/components/Modal')>();
  return { ...actual, default: () => null };
});
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

/** 모달을 열어 외국인·기관 칸의 글자를 돌려준다. */
const openAndReadRows = async () => {
  render(<JonggaV2Page />);
  fireEvent.click(await screen.findByText('상세 분석 보기'));
  await waitFor(() => expect(screen.getByText('투자자 동향 (오늘 기준 5영업일)')).toBeTruthy());
  const dialog = within(screen.getByRole('dialog', { name: '태웅' }));
  return {
    foreign: dialog.getByText('외국인').parentElement?.textContent ?? '',
    institution: dialog.getByText('기관').parentElement?.textContent ?? '',
  };
};

describe('[FE-048] 상세 모달의 Toss 5일 순매수 결측과 부분 합계', () => {
  beforeEach(() => {
    state.detail = { ...DETAIL };
    vi.stubGlobal('fetch', vi.fn(async () => ({ json: async () => state.detail })));
  });

  it('확정 집계가 없고 Toss 합계가 null 이면 0 이 아니라 자료 없음을 그린다', async () => {
    const rows = await openAndReadRows();

    expect(rows.foreign).toContain('자료 없음');
    expect(rows.institution).toContain('자료 없음');
  });

  it('Toss 합계가 5일을 채우지 못하면 실제 합산 일수를 붙이고, 다 채우면 붙이지 않는다', async () => {
    state.detail = { ...DETAIL, investorTrend: { ...DETAIL.investorTrend, foreign: 1_400_000_000, foreignDays: 4, institution: -300_000_000, institutionDays: 5 } };
    const rows = await openAndReadRows();

    expect(rows.foreign).toContain('+14억');
    expect(rows.foreign).toContain('(4일)');
    expect(rows.institution).toContain('-3억');
    expect(rows.institution).not.toContain('일)');
  });

  it('확정 집계가 있으면 Toss 일수를 붙이지 않는다', async () => {
    state.detail = {
      ...DETAIL,
      investorTrend: { ...DETAIL.investorTrend, foreign: 1_400_000_000, foreignDays: 4 },
      investorTrend5Day: { foreign: 2_300_000_000, institution: 0 },
    };
    const rows = await openAndReadRows();

    expect(rows.foreign).toContain('+23억');
    expect(rows.foreign).not.toContain('일)');
    expect(rows.institution).not.toContain('자료 없음');
  });

  it('옛 Toss 원시 응답에서도 결측을 0 으로 바꾸지 않는다', async () => {
    state.detail = { code: '044490', name: '태웅', market: 'KOSDAQ', price: { current: 100 }, investor_trend: { foreign: null } };
    const rows = await openAndReadRows();

    expect(rows.foreign).toContain('자료 없음');
    expect(rows.institution).toContain('자료 없음');
  });
});
