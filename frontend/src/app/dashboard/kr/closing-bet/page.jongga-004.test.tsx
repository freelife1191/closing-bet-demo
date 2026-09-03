// [JONGGA-004] 회귀 검사. AI 분석을 받지 않은 종목의 카드에 등급으로 계산한 확신도가
// 표시되면 안 된다. 옛 코드는 `score.total * 8 + (S면 10)` 이라는 식으로 확신도를 만들어
// 냈고, 총점 상한이 19점이라 12점만 넘으면 항상 100% 가 찍혔다. 실제 데이터에서도
// 2026-02-26 자 35건이 AI 결과 없이 전부 `BUY 100%` 로 그려졌다.
//
// 세 가지 상태를 각각 확인한다.
//   1. ai_evaluation 이 있는 종목  -> action 배지와 확신도 막대를 그대로 표시
//   2. llm_reason 만 있는 종목     -> "AI 분석 대기" 배지와 "미산출"
//   3. 둘 다 없는 종목             -> "AI 분석 대기" 배지와 "미산출"
//
// 2번은 [JONGGA-016] 이 뒤집었다. 옛 코드는 사유 텍스트에서 매매 추천을 추정했으나
// 그 추정이 2026-02-11 자료 아홉 건 가운데 일곱 건을 틀려서 걷어냈다.

import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

type Signal = Record<string, unknown>;

function makeSignal(overrides: Signal): Signal {
  return {
    stock_code: '000000',
    stock_name: '기본종목',
    market: 'KOSPI',
    sector: '반도체',
    grade: 'S',
    // 총점 16점은 옛 계산식이라면 확신도 100% 를 만들어 내는 값이다.
    score: {
      news: 2, volume: 3, chart: 3, candle: 2,
      consolidation: 2, timing: 2, supply: 2,
      llm_reason: '', total: 16,
    },
    checklist: {
      has_news: true, news_sources: [], is_new_high: true,
      is_breakout: true, supply_positive: true, volume_surge: true,
    },
    current_price: 10000,
    entry_price: 10000,
    stop_price: 9500,
    target_price: 10900,
    change_pct: 7.5,
    trading_value: 100_000_000_000,
    ...overrides,
  };
}

const SIGNALS = [
  makeSignal({
    stock_code: '111111',
    stock_name: 'AI분석완료',
    ai_evaluation: { action: 'BUY', confidence: 85, model: 'gemini-3.7-flash', reason: '수급이 좋다' },
  }),
  makeSignal({
    stock_code: '222222',
    stock_name: '사유만존재',
    score: {
      news: 2, volume: 3, chart: 3, candle: 2,
      consolidation: 2, timing: 2, supply: 2,
      llm_reason: 'VCP 점수 30점으로 보통 수준이나 매수 우위가 관찰된다.', total: 16,
    },
  }),
  makeSignal({
    stock_code: '333333',
    stock_name: 'AI미분석',
  }),
  // 재분석 경로(engine/llm_analyzer_parsers.py:102)는 LLM 응답의 confidence 를 형 변환
  // 없이 넘기므로 문자열이 올라올 수 있다. 숫자로 읽히면 버리지 않는다.
  makeSignal({
    stock_code: '444444',
    stock_name: '문자열확신도',
    ai_evaluation: { action: 'BUY', confidence: '80' as unknown as number, model: 'gemini-3.7-flash' },
  }),
  // 상한만 조이면 음수가 그대로 통과해 막대 너비가 음수가 된다.
  makeSignal({
    stock_code: '555555',
    stock_name: '음수확신도',
    ai_evaluation: { action: 'HOLD', confidence: -5, model: 'gemini-3.7-flash' },
  }),
];

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: '2026-09-02',
        total_candidates: SIGNALS.length,
        filtered_count: SIGNALS.length,
        signals: SIGNALS,
        updated_at: '2026-09-02T15:40:00',
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

/** 종목명이 들어 있는 카드 요소를 찾는다. 카드 하나가 종목 하나에 대응한다. */
async function findCard(stockName: string): Promise<HTMLElement> {
  const nameNode = await screen.findByText(stockName);
  const card = nameNode.closest('div.rounded-2xl.border');
  if (!card) throw new Error(`${stockName} 카드를 찾지 못했습니다`);
  return card as HTMLElement;
}

describe('[JONGGA-004] SignalCard 의 AI 평가 표시', () => {
  it('AI 분석 결과가 없으면 확신도를 지어내지 않고 대기 상태로 표시한다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('AI미분석');

    expect(within(card).queryByText('AI 분석 대기')).not.toBeNull();
    expect(within(card).queryByText('미산출')).not.toBeNull();

    // 옛 계산식의 산출물. 총점 16점 + S등급이면 138 이 나와 100% 로 잘렸다.
    expect(within(card).queryByText('100%')).toBeNull();
    expect(within(card).queryByText('BUY')).toBeNull();
  });

  // [JONGGA-016] 이 검사는 뒤집혔다. 사유 텍스트로 매매 추천을 추정하던 폴백을 걷어냈다.
  it('사유 텍스트만 있으면 매매 추천을 지어내지 않는다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('사유만존재');

    expect(within(card).queryByText('AI 분석 대기')).not.toBeNull();
    expect(within(card).queryByText('미산출')).not.toBeNull();
    // 이 사유에는 「매수 우위」가 들어 있어 옛 추정 폴백이 BUY 를 그렸다.
    expect(within(card).queryByText('BUY')).toBeNull();
    // 확신도 데이터가 없는 상태를 0% 막대로 그리면 "AI 가 0% 신뢰한다" 로 읽힌다.
    expect(within(card).queryByText('0%')).toBeNull();
    // 분석하지 않은 카드에 분석 주체를 적지 않는다. 옛 코드는 사유가 있다는 이유만으로
    // 기본 라벨을 배지에 달아, 같은 카드가 대기 상태와 모델 이름을 함께 말했다.
    expect(within(card).queryByText('Gemini 3.7 Flash')).toBeNull();
  });

  it('AI 확신도가 있으면 그 값을 그대로 표시한다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('AI분석완료');

    await waitFor(() => {
      expect(within(card).queryByText('85%')).not.toBeNull();
    });
    expect(within(card).queryByText('BUY')).not.toBeNull();
    expect(within(card).queryByText('미산출')).toBeNull();
    expect(within(card).queryByText('AI 분석 대기')).toBeNull();
  });

  it('확신도가 문자열로 올라와도 숫자로 읽어 표시한다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('문자열확신도');

    expect(within(card).queryByText('80%')).not.toBeNull();
    expect(within(card).queryByText('미산출')).toBeNull();
  });

  it('확신도가 음수면 0% 로 조여 막대 너비가 음수가 되지 않게 한다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('음수확신도');

    expect(within(card).queryByText('0%')).not.toBeNull();
    expect(within(card).queryByText('-5%')).toBeNull();
  });
});
