// Regression: [JONGGA-019] — 시세를 못 받은 종목의 상세 모달이 값 없음을 값처럼 그리던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-019] (2026-09-03 JONGGA-015 사이클의 /code-review)
//
// 백엔드는 시세를 못 받았을 때 값을 비우는 대신 0 으로 채운다. 세 갈래가 모두 그렇게 한다.
// 2026-09-03 실측: 없는 종목코드로 /api/kr/stock-detail 을 부르면 priceInfo 의 아홉 값과
// yearRange 의 두 값이 모두 0 으로 온다. 고치기 전 화면은 그 0 을 그대로 그려 「₩0」과
// 「L: ₩0 / H: ₩0」을 정상 시세처럼 적고 손잡이를 범위 한가운데에 놓았다.
//
// 키가 아예 빠진 응답도 화면까지 닿을 수 있다. 캐시를 읽는 쪽이 code 가 문자열인지만
// 검사하고 통과시키기 때문이다. 그때는 toLocaleString 이 터져 모달이 통째로 사라졌다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';
import { isPositivePrice } from './displayHelpers';

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
  trading_value: 108_475_054_850,
  signal_date: '2026-09-02',
  score_details: { foreign_net_buy: 2_318_082_600, inst_net_buy: 3_276_004_650 },
};

const HEALTHY_DETAIL = {
  code: '044490',
  name: '태웅',
  market: 'KOSDAQ',
  priceInfo: {
    current: 37_000,
    prevClose: 37_250,
    open: 37_100,
    high: 37_500,
    low: 36_800,
    change: -250,
    change_pct: -0.67,
    volume: 875_000,
    trading_value: 32_391_810_400,
  },
  yearRange: { high_52w: 41_000, low_52w: 21_000 },
  indicators: { marketCap: 1_000_000_000_000, per: 12, pbr: 1.1, eps: 3_000, bps: 33_000, dividendYield: 1.2 },
  investorTrend: { foreign: 5_165_870_050, institution: 3_891_767_750, individual: -9_322_623_150 },
  investorTrend5Day: { foreign: 2_318_082_600, institution: 3_276_004_650 },
  financials: { revenue: 0, operatingProfit: 0, netIncome: 0 },
  safety: { debtRatio: 0, currentRatio: 0 },
};

// 2026-09-03 실측한 응답 그대로다. curl http://localhost:5501/api/kr/stock-detail/999999
const ALL_ZERO_DETAIL = {
  ...HEALTHY_DETAIL,
  priceInfo: {
    current: 0, prevClose: 0, open: 0, high: 0, low: 0,
    change: 0, change_pct: 0, volume: 0, trading_value: 0,
  },
  yearRange: { high_52w: 0, low_52w: 0 },
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
        updated_at: TODAY(),
        status: 'ok',
      };
    }
    if (path === '/api/kr/jongga-v2/status') return { is_running: false };
    return {};
  }),
}));

vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false, isLoading: false }) }));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

/** 카드를 그린 뒤 「상세 분석 보기」를 눌러 모달의 본문이 나올 때까지 기다린다. */
const openDetailModal = async () => {
  render(<JonggaV2Page />);
  fireEvent.click(await screen.findByText('상세 분석 보기'));
  await waitFor(() => expect(screen.getByText('시세 정보 (실시간)')).toBeTruthy());
};

describe('[JONGGA-019] 시세를 못 받은 종목의 상세 모달', () => {
  beforeEach(() => {
    state.detail = { ...HEALTHY_DETAIL };
    vi.stubGlobal('fetch', vi.fn(async () => ({ json: async () => state.detail })));
  });

  it('시세가 모두 0 이면 두 범위 모두 값 없음을 적는다', async () => {
    state.detail = ALL_ZERO_DETAIL;
    await openDetailModal();

    // 1일 범위와 52주 범위 두 자리 모두에 나온다.
    expect(screen.getAllByText('시세를 불러오지 못했습니다')).toHaveLength(2);
    // 0 을 시세처럼 적던 문자열은 사라졌다.
    expect(document.body.textContent).not.toContain('₩0');
    expect(document.body.textContent).not.toContain('L: ₩0');
  });

  it('시세 키가 빠진 응답에도 모달이 그려진다', async () => {
    // mapTossDataToDetail 은 priceInfo 키가 있으면 응답을 그대로 통과시킨다. 그 갈래는
    // 다른 갈래가 쓰는 「|| 0」 기본값 처리를 거치지 않으므로, 빠진 키가 undefined 인 채로
    // 화면까지 닿는다. 캐시를 읽는 쪽도 code 가 문자열인지만 검사하므로 이런 응답이
    // 실제로 만들어질 수 있다. 고치기 전에는 여기서 toLocaleString 이 터져 모달이
    // 통째로 사라졌다. 그래서 priceInfo 는 남기고 그 안의 시세 키만 비운다. 셋을 모두
    // 지우면 폴백 매핑 갈래로 빠져 0 이 채워지므로 이 경로를 재현하지 못한다.
    state.detail = { ...HEALTHY_DETAIL, priceInfo: { prevClose: 37_250 }, yearRange: undefined };
    await openDetailModal();

    expect(screen.getAllByText('시세를 불러오지 못했습니다')).toHaveLength(2);
    // 모달의 다른 절은 그대로 그려진다. 시세 한 자리가 비어도 나머지는 읽을 수 있어야 한다.
    expect(screen.getByText('투자 지표')).toBeTruthy();
  });

  it('시세를 받은 종목은 종전대로 막대를 그린다', async () => {
    await openDetailModal();

    expect(screen.queryByText('시세를 불러오지 못했습니다')).toBeNull();
    // 1일 범위와 52주 범위가 같은 현재가를 쓰므로 두 번 나온다.
    expect(screen.getAllByText('₩37,000')).toHaveLength(2);
    expect(screen.getByText('L: ₩36,800')).toBeTruthy();
    expect(screen.getByText('H: ₩41,000')).toBeTruthy();
  });
});

describe('[JONGGA-019] isPositivePrice', () => {
  it('시세로 그릴 수 있는 값만 통과시킨다', () => {
    // NaN 은 없는 값에 곱셈을 한 결과다. 고치기 전 1일 범위의 폴백이 그랬다.
    for (const v of [0, -100, NaN, Infinity, undefined, null]) expect(isPositivePrice(v)).toBe(false);
    for (const v of [100, 37_000]) expect(isPositivePrice(v)).toBe(true);
  });
});
