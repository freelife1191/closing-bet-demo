// Regression: [JONGGA-022] — 카드와 상세 모달이 같은 이름의 지표를 다른 값으로 말하던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-022] (2026-09-03 JONGGA-015 사이클의 qa-only ISSUE-003)
//
// 상세 API 응답에는 5일 순매수가 두 벌 들어 있다. `investorTrend5Day` 는 카드가 쓰는
// KRX 확정 집계와 원 단위까지 같고, `investorTrend` 는 실시간 시세 제공처가 순매수 수량에
// 종가를 곱해 근사한 값이다. 모달이 뒤쪽을 그리는 바람에 같은 「5일 합계」가 두 자리에서
// 다른 값으로 보였다. 여기에 더해 두 자리의 반올림 규칙까지 갈려 있어서, 값이 같아도
// 카드는 내림한 32억을, 모달은 반올림한 33억을 적었다.

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';
import { formatBigNumber } from './displayHelpers';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });
const TODAY = () => `${KST_DATE.format(new Date())}T12:00:00+09:00`;

// 2026-09-03 실측값이다. 태웅(044490)의 응답에서 그대로 옮겼다.
const FOREIGN_5DAY = 2_318_082_600; // 카드의 score_details.foreign_net_buy 와 같은 값
const INSTITUTION_5DAY = 3_276_004_650; // 카드의 score_details.inst_net_buy 와 같은 값
const FOREIGN_REALTIME = 5_165_870_050; // 고치기 전 모달이 그리던 값
const INSTITUTION_REALTIME = 3_891_767_750;
const INDIVIDUAL_REALTIME = -9_322_623_150;

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
  score_details: {
    foreign_net_buy: FOREIGN_5DAY,
    inst_net_buy: INSTITUTION_5DAY,
  },
};

const DETAIL = {
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
    trading_value: 32_391_810_400, // 장중 누적이라 카드의 확정값과 다르다
  },
  yearRange: { high_52w: 41_000, low_52w: 21_000 },
  indicators: { marketCap: 1_000_000_000_000, per: 12, pbr: 1.1, eps: 3_000, bps: 33_000, dividendYield: 1.2 },
  investorTrend: {
    foreign: FOREIGN_REALTIME,
    institution: INSTITUTION_REALTIME,
    individual: INDIVIDUAL_REALTIME,
  },
  investorTrend5Day: { foreign: FOREIGN_5DAY, institution: INSTITUTION_5DAY },
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

vi.mock('@/app/components/Modal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/app/components/Modal')>();
  return { ...actual, default: () => null };
});
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

/** 카드를 그린 뒤 「상세 분석 보기」를 눌러 모달이 값을 그릴 때까지 기다린다. */
const openDetailModal = async () => {
  render(<JonggaV2Page />);
  fireEvent.click(await screen.findByText('상세 분석 보기'));
  await waitFor(() => expect(screen.getByText('투자자 동향 (오늘 기준 5영업일)')).toBeTruthy());
};

const openTooltipForLabel = async (label: string) => {
  const dialog = screen.getByRole('dialog', { name: '태웅' });
  const labelElement = within(dialog).getByText(label);
  const trigger = labelElement.querySelector<HTMLElement>('[class*="group/tooltip"]');
  expect(trigger).not.toBeNull();
  fireEvent.mouseEnter(trigger as HTMLElement);
  return screen.findByRole('tooltip');
};

describe('[JONGGA-022] 카드와 상세 모달의 지표 어휘', () => {
  beforeEach(() => {
    state.detail = { ...DETAIL };
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ json: async () => state.detail })),
    );
  });

  it('모달의 외국인 5일 순매수가 카드와 같은 값을 그린다', async () => {
    await openDetailModal();

    // 카드와 모달이 같은 문자열이어야 한다. 부호만 모달에 붙는다.
    expect(screen.getByText('23억')).toBeTruthy();
    expect(screen.getByText('+23억')).toBeTruthy();
    // 고치기 전 모달이 그리던 실시간 근사값은 더 이상 나오지 않는다.
    expect(document.body.textContent).not.toContain('52억');
  });

  it('모달의 기관 5일 순매수가 카드와 같은 값을 그린다', async () => {
    await openDetailModal();

    expect(screen.getByText('33억')).toBeTruthy();
    expect(screen.getByText('+33억')).toBeTruthy();
    expect(document.body.textContent).not.toContain('39억');
  });

  it('확정 집계가 응답에 없으면 실시간 집계로 물러선다', async () => {
    // 백엔드는 확정 집계를 못 구하면 키를 아예 넣지 않는다. 그 상황을 그대로 만든다.
    const withoutConfirmed: Partial<typeof DETAIL> = { ...DETAIL };
    delete withoutConfirmed.investorTrend5Day;
    state.detail = withoutConfirmed;
    await openDetailModal();

    // 자리를 비우는 대신 있는 값을 그린다. 값이 없어 모달이 통째로 비는 것이 더 나쁘다.
    expect(screen.getByText('+52억')).toBeTruthy();
    expect(screen.getByText('+39억')).toBeTruthy();
  });

  it('개인 순매수는 실시간 집계를 그대로 쓴다', async () => {
    await openDetailModal();

    // 확정 집계에 개인 열이 없어 이 값만 출처가 다르다. 툴팁이 그 사실을 밝힌다.
    expect(screen.getByText('-93억')).toBeTruthy();
    const tooltip = await openTooltipForLabel('개인');
    expect(within(tooltip).getByText(/이 값만 실시간 시세 제공처가 집계하므로/)).toBeTruthy();
  });

  it('모달의 시세 절이 실시간임을 제목에 밝힌다', async () => {
    await openDetailModal();

    expect(screen.getByText('시세 정보 (실시간)')).toBeTruthy();
  });

  it('모달의 거래대금이 카드의 확정값과 다른 이유를 밝힌다', async () => {
    await openDetailModal();

    // 장중 누적 324억과 카드의 확정 1,085억이 함께 있어도 사용자가 이유를 알 수 있다.
    expect(screen.getByText('324억')).toBeTruthy();
    const tooltip = await openTooltipForLabel('거래대금 (Val)');
    expect(within(tooltip).getByText(/신호가 나온 거래일에 확정된 하루치/)).toBeTruthy();
  });

  // Regression: ISSUE-001 — 모달 수급이 어느 날짜에서든 「카드와 같은 값」이라고 단언했다
  // Found by /qa on 2026-09-03
  // Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-03-jongga-022-scenarios.md
  //
  // 상세 API 는 종목코드만 받고 날짜를 받지 않아 늘 오늘 기준의 5일 집계를 돌려준다.
  // 카드는 신호가 나온 거래일 기준이므로 지난 날짜를 고르면 두 값이 어긋나고,
  // 2026-02-11 현대제철은 카드 109억(순매수) 대 모달 -113억(순매도)으로 부호까지 반대다.
  // 값을 맞출 수 없으니 이름과 문구로 시점을 구분한다.
  // 절 제목은 openDetailModal 이 모달을 기다릴 때 이미 확인한다. 툴팁은 마우스를
  // 올려야 보이지만 제목은 늘 보이므로, 시점을 밝히는 자리를 제목에도 두었다.
  it('카드와 같은 값이라고 단언하지 않는다', async () => {
    await openDetailModal();
    const tooltip = await openTooltipForLabel('외국인');

    // 지난 날짜에서 거짓이 되는 단언이라 지웠다.
    expect(tooltip.textContent).not.toContain('카드의 「외인 (5일)」과 같은 값입니다');
    expect(tooltip.textContent).not.toContain('카드의 「기관 (5일)」과 같은 값입니다');
    // 대신 두 값이 갈리는 조건을 밝힌다.
    expect(within(tooltip).getByText(/지난 날짜를 골랐다면 두 값이 다릅니다/)).toBeTruthy();
  });
});

describe('[JONGGA-022] formatBigNumber', () => {
  it('카드와 모달이 같은 금액을 같은 문자열로 적는다', () => {
    // 고치기 전에는 카드가 내림해 32억, 모달이 반올림해 33억을 적었다.
    expect(formatBigNumber(INSTITUTION_5DAY)).toBe('33억');
    expect(formatBigNumber(FOREIGN_5DAY)).toBe('23억');
  });

  it('값이 없거나 0이면 자리를 비운다', () => {
    expect(formatBigNumber(undefined)).toBe('-');
    expect(formatBigNumber(null)).toBe('-');
    expect(formatBigNumber(0)).toBe('-');
  });

  it('음수는 부호를 앞에 붙인다', () => {
    expect(formatBigNumber(-INSTITUTION_5DAY)).toBe('-33억');
  });

  it('조 단위는 소수 한 자리로 적는다', () => {
    expect(formatBigNumber(1_250_000_000_000)).toBe('1.3조');
  });
});
