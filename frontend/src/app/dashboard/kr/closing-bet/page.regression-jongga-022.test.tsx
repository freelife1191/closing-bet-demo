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
import { formatMarketAmount } from '../formatMarketAmount';

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

const state = vi.hoisted(() => ({ detail: {} as Record<string, unknown>, bonus: 0 }));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date()),
        total_candidates: 1,
        filtered_count: 1,
        signals: [{ ...SIGNAL, score_details: { ...SIGNAL.score_details, bonus_score: state.bonus } }],
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
    state.bonus = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ json: async () => state.detail })),
    );
  });

  it('재무 값의 부호를 보존하고 각 기간과 EPS 미확인을 표시한다', async () => {
    state.detail = { ...DETAIL, indicators: { ...DETAIL.indicators, per: -1147.6, eps: -266 },
      financials: { revenue: 100, operatingProfit: 80, netIncome: 2_600_000_000,
        revenuePeriod: '2026Q1', operatingProfitPeriod: '2025', netIncomePeriod: '2026Q1' } };
    await openDetailModal();
    const dialog = screen.getByRole('dialog', { name: '태웅' });
    expect(within(dialog).getByText('-266')).toBeTruthy();
    expect(within(dialog).getByText('26억')).toBeTruthy();
    expect(within(dialog).getAllByText('기준: 2026Q1')).toHaveLength(2);
    expect(within(dialog).getByText('기준: 2025')).toBeTruthy();
    expect(within(dialog).getByText('EPS 기준 기간 미확인')).toBeTruthy();
    expect((await openTooltipForLabel('PER')).textContent).toContain('음수 PER');
  });

  it('원시 Toss 응답도 기간을 보존하며 객체와 긴 기간 값은 미확인으로 표시한다', async () => {
    state.detail = { code: '044490', name: '태웅', market: 'KOSDAQ',
      price: { current: 100 }, indicators: { eps: -10 },
      financials: { revenue: 100, operating_profit: 80, net_income: -20,
        revenue_period: '2026Q2', operating_profit_period: {}, net_income_period: 'x'.repeat(1000) } };
    await openDetailModal();
    const dialog = screen.getByRole('dialog', { name: '태웅' });
    expect(within(dialog).getByText('기준: 2026Q2')).toBeTruthy();
    expect(within(dialog).getAllByText('기준 기간 미확인')).toHaveLength(2);
    expect(within(dialog).getByText('-20')).toBeTruthy();
  });

  it('구형 응답의 재무 기간을 연간으로 추정하지 않는다', async () => {
    await openDetailModal();
    expect(screen.getAllByText('기준 기간 미확인')).toHaveLength(3);
    expect((await openTooltipForLabel('재무 정보')).textContent).not.toContain('최근 연간');
  });

  it.each([8, 9])('과거 가산점 %s를 잘라내지 않고 현재 상한과 구분한다', async (bonus) => {
    state.bonus = bonus;
    render(<JonggaV2Page />);
    expect(await screen.findByText(`+${bonus}점 (과거 저장값)`)).toBeTruthy();
    expect(screen.queryByText(`+${bonus}/7`)).toBeNull();
    expect(screen.getByText('현재 가산점 상한은 7점입니다. 총점은 저장 당시 값을 유지합니다.')).toBeTruthy();
  });

  it('현행 가산점 7은 기존 상한으로 표시한다', async () => {
    state.bonus = 7;
    render(<JonggaV2Page />);
    expect(await screen.findByText('+7/7')).toBeTruthy();
    expect(screen.queryByText(/과거 저장값/)).toBeNull();
  });

  it.each([
    [null, '자료 없음'], [0, '0'], [100_000_000, '+1억'], [-100_000_000, '-1억'],
  ])('개인 수급 %s의 실제 값과 자료 없음을 구분한다', async (individual, expected) => {
    state.detail = { ...DETAIL, investorTrend: { ...DETAIL.investorTrend, individual } };
    await openDetailModal();
    const row = within(screen.getByRole('dialog', { name: '태웅' })).getByText('개인').parentElement;
    expect(row).not.toBeNull();
    expect(row?.textContent).toContain(expected);
  });

  it('같은 페이지에서 닫고 다시 열면 자료 없음과 복구 응답을 그린다', async () => {
    await openDetailModal();
    for (const [individual, expected] of [[undefined, '자료 없음'], [-100_000_000, '-1억']] as const) {
      fireEvent.click(within(screen.getByRole('dialog', { name: '태웅' })).getByRole('button', { name: '닫기' }));
      state.detail = { ...DETAIL, investorTrend: { ...DETAIL.investorTrend, individual } };
      fireEvent.click(screen.getByText('상세 분석 보기'));
      await waitFor(() => {
        const dialog = screen.getByRole('dialog', { name: '태웅' });
        expect(within(dialog).getByText('개인').parentElement?.textContent).toContain(expected);
        expect(within(dialog).getByText('+33억')).toBeTruthy();
      });
    }
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

  it('5일 확정 집계가 없으면 외국인·기관은 -를 유지하고 개인 실제0은 0을 표시한다', async () => {
    state.detail = {
      ...DETAIL,
      investorTrend5Day: undefined,
      investorTrend: { institution: 0, individual: 0 },
    };
    await openDetailModal();

    const section = screen.getByText('투자자 동향 (오늘 기준 5영업일)').closest('div[class~="bg-white/5"]') as HTMLElement;
    expect(within(section).getAllByText('-')).toHaveLength(2);
    expect(within(section).getByText('개인').parentElement?.textContent).toContain('0');
    expect(section.textContent).not.toContain('+-');
    expect(section.textContent).not.toContain('+0');
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

describe('[JONGGA-022] formatMarketAmount', () => {
  it('카드와 모달이 같은 금액을 같은 문자열로 적는다', () => {
    // 고치기 전에는 카드가 내림해 32억, 모달이 반올림해 33억을 적었다.
    expect(formatMarketAmount(INSTITUTION_5DAY, '-')).toBe('33억');
    expect(formatMarketAmount(FOREIGN_5DAY, '-')).toBe('23억');
  });

  it('값이 없거나 0이면 자리를 비운다', () => {
    expect(formatMarketAmount(undefined, '-')).toBe('-');
    expect(formatMarketAmount(null, '-')).toBe('-');
    expect(formatMarketAmount(0, '-')).toBe('-');
  });

  it('음수는 부호를 앞에 붙인다', () => {
    expect(formatMarketAmount(-INSTITUTION_5DAY, '-')).toBe('-33억');
  });

  it('조 단위는 소수 한 자리로 적는다', () => {
    expect(formatMarketAmount(1_250_000_000_000, '-')).toBe('1조 2500억');
  });
});
