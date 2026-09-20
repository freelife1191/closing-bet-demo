// Regression: [JONGGA-023] — 화면 필터 상태를 엔진 집계와 원본 리포트 상태로 오인하던 문제

import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });
const TODAY = () => `${KST_DATE.format(new Date())}T12:00:00+09:00`;

const SIGNAL = {
  stock_code: '044490',
  stock_name: '테마종목',
  market: 'KOSDAQ',
  sector: '기계',
  grade: 'B',
  score: { news: 2, volume: 3, chart: 2, candle: 1, consolidation: 1, timing: 1, supply: 2, llm_reason: '', total: 12 },
  checklist: { has_news: false, news_sources: [], is_new_high: false, is_breakout: false, supply_positive: true, volume_surge: true },
  current_price: 37_250,
  entry_price: 37_200,
  stop_price: 36_084,
  target_price: 39_060,
  change_pct: 11.5,
  volume_ratio: 3,
  trading_value: 100_000_000_000,
  themes: ['원전'],
  signal_date: KST_DATE.format(new Date()),
};

const state = vi.hoisted(() => ({ signals: [] as Array<Record<string, unknown>> }));

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date()),
        total_candidates: 7,
        filtered_count: 3,
        signals: state.signals,
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

beforeEach(() => {
  state.signals = [{ ...SIGNAL }];
});

async function renderReport() {
  render(<JonggaV2Page />);
  await screen.findByText('테마종목');
}

async function openCardTooltip(label: string) {
  const card = screen.getByRole('heading', { name: '테마종목' }).closest('div.rounded-2xl.border') as HTMLElement;
  const labelNode = within(card).getByText(label);
  const trigger = labelNode.querySelector<HTMLElement>('[class*="group/tooltip"]');
  expect(trigger).not.toBeNull();
  fireEvent.mouseEnter(trigger as HTMLElement);
  return screen.findByRole('tooltip');
}

describe('[JONGGA-023] 빈 상태와 화면 집계', () => {
  it('필터 결과가 0이면 원자료 없음과 구분해 한국어로 안내하고 전체 테마를 보존한다', async () => {
    await renderReport();

    fireEvent.change(screen.getByRole('combobox', { name: '거래대금' }), { target: { value: '1000000000000' } });

    expect(await screen.findByRole('heading', { name: '선택한 필터에 맞는 종목이 없습니다.' })).toBeTruthy();
    expect(screen.getByText('필터를 초기화하거나 조건을 낮춰 다시 확인해 주세요.')).toBeTruthy();
    expect(screen.getByTitle('원전: 1개 종목')).toBeTruthy();
    expect(screen.getByText('엔진 단계')).toBeTruthy();
    expect(screen.getByText('표시 0 / 리포트 전체 1')).toBeTruthy();
  });

  it('리포트 원자료가 비어 있으면 분석 결과가 없다고 안내한다', async () => {
    state.signals = [];
    render(<JonggaV2Page />);

    expect(await screen.findByRole('heading', { name: '분석된 종목이 없습니다.' })).toBeTruthy();
    expect(screen.getByText('데이터가 갱신된 뒤 종목이 표시됩니다.')).toBeTruthy();
  });

  it('D등급 원자료만 있으면 갱신 실패가 아니라 표시 제외 이유와 날짜 확인을 안내한다', async () => {
    state.signals = [{ ...SIGNAL, grade: 'D', stock_name: '제외종목' }];
    render(<JonggaV2Page />);

    expect(await screen.findByRole('heading', { name: '표시할 수 있는 종목이 없습니다.' })).toBeTruthy();
    expect(screen.getByText('D등급 종목은 안전 기준에 따라 화면에서 제외됩니다. 다른 날짜의 리포트를 확인해 주세요.')).toBeTruthy();
    expect(screen.queryByText('데이터가 갱신된 뒤 종목이 표시됩니다.')).toBeNull();
  });

  it('D등급 원자료만 있을 때 필터를 바꿔도 필터 결과 0으로 오인하지 않는다', async () => {
    state.signals = [{ ...SIGNAL, grade: 'D', stock_name: '제외종목' }];
    render(<JonggaV2Page />);
    await screen.findByText('표시할 수 있는 종목이 없습니다.');

    fireEvent.change(screen.getByRole('combobox', { name: '거래대금' }), { target: { value: '1000000000000' } });

    expect(screen.getByRole('heading', { name: '표시할 수 있는 종목이 없습니다.' })).toBeTruthy();
    expect(screen.getByText('D등급 종목은 안전 기준에 따라 화면에서 제외됩니다. 다른 날짜의 리포트를 확인해 주세요.')).toBeTruthy();
    expect(screen.queryByText('선택한 필터에 맞는 종목이 없습니다.')).toBeNull();
  });
});

describe('[JONGGA-023] 카드 지표의 기준 시점', () => {
  for (const label of ['상승률', '거래량 배수', '종가', '거래대금']) {
    it(`${label} 설명을 신호가 나온 거래일 기준으로 말한다`, async () => {
      await renderReport();

      const tooltip = await openCardTooltip(label);
      expect(within(tooltip).getByText(/신호가 나온 거래일/)).toBeTruthy();
    });
  }
});
