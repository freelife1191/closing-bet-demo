// Regression: [JONGGA-016] — 자료가 「관망」이라고 적은 종목이 화면에서 「매수」로 보이던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-016] (2026-09-03 JONGGA-005 사이클의 /qa NEW-001)
//
// AI 판정은 응답의 두 자리에 담긴다. 2026-09-03 같은 최신 자료는 최상위 ai_evaluation 과
// score.ai_evaluation 에 같은 객체를 넣지만, 2026-02-11 자료는 score 에만 넣고 최상위를
// null 로 둔다. 화면이 최상위만 읽었기 때문에 지난 날짜의 판정과 확신도가 통째로 사라졌고,
// 그 빈자리를 llm_reason 텍스트 추정이 메웠다. 사유에 「상승」이나 「매수」가 들어 있으면
// BUY 로 읽는 방식이라 부정 맥락에서도 BUY 가 나왔고, 2026-02-11 아홉 종목 가운데 일곱
// 종목이 틀렸다. 매도를 권한 대우건설까지 매수로 뒤집혔다.
//
// 아래 자료는 2026-02-11 응답에서 그대로 옮긴 값이다.

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';

type Signal = Record<string, unknown>;

function makeSignal(overrides: Signal): Signal {
  return {
    stock_code: '000000',
    stock_name: '기본종목',
    market: 'KOSPI',
    sector: '반도체',
    grade: 'B',
    score: { news: 2, volume: 3, chart: 3, candle: 2, consolidation: 2, timing: 2, supply: 2, llm_reason: '', total: 12 },
    checklist: {
      has_news: true, news_sources: [], is_new_high: false,
      is_breakout: false, supply_positive: true, volume_surge: true,
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

// 아크릴의 사유. 「상승」과 「매수」가 모두 들어 있지만 둘 다 부정 맥락이다.
const ACRYL_REASON =
  'AI 교육솔루션 대규모 공급 계약 체결이라는 강력한 호재로 26% 이상 급등했으며, 외인/기관 동반 ' +
  '순매수세가 긍정적입니다. 그러나 VCP 점수가 0점이고 수축 비율이 1.0으로, 변동성 수축 패턴의 ' +
  '기술적 완성도가 매우 낮아 VCP 관점의 매수 근거가 없습니다. 이미 큰 폭으로 상승하여 단기 추격 ' +
  '매수는 위험하므로, 신규 진입보다는 보유자의 관망이 바람직합니다.';

const DAEWOO_REASON =
  '대우건설은 성수4지구 시공사 선정 무효화 및 조합과의 분쟁이라는 명확한 악재를 안고 있어 투자 ' +
  '심리에 부정적인 영향을 미칠 것으로 예상된다. 악재가 해소될 때까지는 관망하거나 비중 축소를 ' +
  '고려해야 한다.';

const SIGNALS = [
  // 지난 자료의 형태. 최상위는 null 이고 판정은 score 안에만 있다. 두 자리가 모두 채워진
  // 최신 자료는 page.jongga-004.test.tsx 의 「AI 확신도가 있으면 그 값을 그대로 표시한다」가
  // 이미 검사하므로 여기에 두지 않는다.
  makeSignal({
    stock_code: '0007C0',
    stock_name: '아크릴',
    ai_evaluation: null,
    score: {
      news: 2, volume: 3, chart: 0, candle: 2, consolidation: 0, timing: 2, supply: 2,
      llm_reason: ACRYL_REASON, total: 11,
      ai_evaluation: { action: 'HOLD', confidence: 60, model: 'gemini-2.5-flash', reason: ACRYL_REASON },
    },
  }),
  makeSignal({
    stock_code: '047040',
    stock_name: '대우건설',
    ai_evaluation: null,
    score: {
      news: 2, volume: 3, chart: 3, candle: 2, consolidation: 2, timing: 2, supply: 2,
      llm_reason: DAEWOO_REASON, total: 16,
      ai_evaluation: { action: 'SELL', confidence: 70, model: 'gemini-2.5-flash', reason: DAEWOO_REASON },
    },
  }),
];

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: '2026-02-11',
        total_candidates: SIGNALS.length,
        filtered_count: SIGNALS.length,
        signals: SIGNALS,
        updated_at: '2026-02-11T17:00:00',
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

describe('[JONGGA-016] 카드의 매매 추천 원천', () => {
  it('최상위가 비어 있어도 score 안의 판정과 확신도를 그대로 그린다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('아크릴');

    expect(within(card).queryByText('HOLD')).not.toBeNull();
    // 사유에 「상승」과 「매수」가 들어 있어 옛 추정 폴백이 BUY 를 그렸다.
    expect(within(card).queryByText('BUY')).toBeNull();
    expect(within(card).queryByText('AI 분석 대기')).toBeNull();
    expect(within(card).queryByText('60%')).not.toBeNull();
    expect(within(card).queryByText('미산출')).toBeNull();

    const confidenceLabel = within(card).getByText('확신도');
    expect(confidenceLabel.classList.contains('whitespace-nowrap')).toBe(true);
    expect(confidenceLabel.closest('.flex.items-center.justify-between')?.classList.contains('flex-wrap')).toBe(true);
  });

  it('매도 판정이 매수로 뒤집히지 않는다', async () => {
    render(<JonggaV2Page />);
    const card = await findCard('대우건설');

    expect(within(card).queryByText('SELL')).not.toBeNull();
    expect(within(card).queryByText('BUY')).toBeNull();
    expect(within(card).queryByText('70%')).not.toBeNull();
  });
});
