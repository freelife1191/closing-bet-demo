// Regression: [JONGGA-015] — 카드가 「현재가」라는 이름으로 최근 거래일의 종가를 보여주고,
// 매수·목표·손절가가 어느 값에서 파생되는지 밝히지 않던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-015] (2026-09-03 JONGGA-005 사이클의 qa-only ISSUE-001)
//
// [JONGGA-031] 카드 종가는 entry_price와 signal_date를 함께 표시한다.
// current_price는 최신 조회 가격이므로 이 타일의 기준으로 사용하지 않는다.
// 목표가와 손절가도 저장된 진입가를 기준으로 한다.

import { render, screen, within } from '@testing-library/react';
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

async function signalCloseTile(): Promise<HTMLElement> {
  const label = await screen.findByText('2026-09-02 종가');
  const tile = label.closest('.text-center');
  if (!tile) throw new Error('신호일 종가 타일을 찾지 못했습니다.');
  return tile as HTMLElement;
}

describe('[JONGGA-015] 종가베팅 카드의 가격 어휘', () => {
  beforeEach(() => {
    state.signal = { ...SIGNAL };
  });

  it('가격 자리를 「현재가」가 아니라 「종가」라고 부른다', async () => {
    render(<JonggaV2Page />);

    // 지표 라벨은 값과 같은 블록에 놓인다. 값에서 거슬러 올라가 라벨을 짚는다.
    const metricBlock = await signalCloseTile();
    expect(within(metricBlock).getByText('₩37,200')).toBeTruthy();
    expect(metricBlock.textContent).toContain('종가');
    expect(metricBlock.textContent).not.toContain('현재가');
  });

  it('화면 어디에도 「현재가」라는 말이 남아 있지 않다', async () => {
    render(<JonggaV2Page />);

    // 툴팁 문구까지 포함해 확인한다. 「상승률」 툴팁도 같은 말을 쓰고 있었다.
    await signalCloseTile();
    expect(document.body.textContent).not.toContain('현재가');
  });

  it('신호일 종가는 entry_price 값을 표시한다', async () => {
    render(<JonggaV2Page />);

    const tile = await signalCloseTile();
    expect(within(tile).getByText('₩37,200')).toBeTruthy();
    expect(within(tile).queryByText('₩37,250')).toBeNull();
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

    await screen.findByRole('heading', { name: '태웅' });
    expect(document.body.textContent).not.toContain('매수가 +');
    expect(document.body.textContent).not.toContain('매수가 -');
    expect(document.body.textContent).not.toContain('NaN');
    expect(document.body.textContent).not.toContain('Infinity');
  });

  it('목표가가 없으면 그 자리에만 비율을 그리지 않는다', async () => {
    state.signal = { ...SIGNAL, target_price: 0 };
    render(<JonggaV2Page />);

    await signalCloseTile();
    expect(document.body.textContent).not.toContain('매수가 +');
    expect(screen.getByText('(매수가 -3.0%)')).toBeTruthy();
  });
  it('저장 진입가와 별도 buy_price가 달라도 시스템 가격의 기준은 진입가다', async () => {
    state.signal = { ...SIGNAL, entry_price: 100000, buy_price: 120000, target_price: 105000, stop_price: 97000 };
    render(<JonggaV2Page />);
    expect(within(await signalCloseTile()).getByText('₩100,000')).toBeTruthy();
    expect(screen.getByText('(매수가 +5.0%)')).toBeTruthy();
    expect(screen.getByText('(매수가 -3.0%)')).toBeTruthy();
  });

  it('개별 저장 목표·손절은 기본 비율로 덮어쓰지 않는다', async () => {
    state.signal = { ...SIGNAL, entry_price: 100000, target_price: 108000, stop_price: 96000 };
    render(<JonggaV2Page />);
    expect(await screen.findByText('₩108,000')).toBeTruthy();
    expect(screen.getByText('₩96,000')).toBeTruthy();
    expect(screen.getByText('(매수가 +8.0%)')).toBeTruthy();
    expect(screen.getByText('(매수가 -4.0%)')).toBeTruthy();
  });

  it('AI 원문의 다른 가격을 보존하고 시스템 계산 가격과 출처를 구분한다', async () => {
    const reason = '단기 목표 142,000원, 손절 130,000원. 檢証 🧪 <script>skipQA()</script>';
    state.signal = { ...SIGNAL, score: { ...SIGNAL.score, llm_reason: reason } };
    render(<JonggaV2Page />);
    expect(await screen.findByText(reason)).toBeTruthy();
    expect(screen.getByText('시스템 계산 기준')).toBeTruthy();
    expect(screen.getByText(/AI 원문에는 다른 가격이 포함될 수 있습니다/)).toBeTruthy();
    expect(screen.getByText('₩39,060')).toBeTruthy();
    expect(document.querySelector('script')).toBeNull();
  });

});
