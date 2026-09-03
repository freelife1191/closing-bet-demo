# [JONGGA-015] 종가 카드의 가격 어휘 바로잡기 — 실행 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 종가베팅 카드가 「현재가」라는 이름으로 보여주던 값이 실제로는 최근 거래일의
종가임을 화면에서 드러내고, 매수가·목표가·손절가가 어느 값에서 파생되는지 함께 밝힌다.

**Architecture:** 값을 바꾸지 않고 이름과 부가 표기만 바꾼다. 카드의 `signal.current_price`
는 그대로 두고 라벨을 「종가」로, 툴팁을 실제 출처에 맞게 고친다. 「전략 포인트」의 세 가격에
기준 날짜와 매수가 대비 비율을 덧붙여 파생 관계를 읽을 수 있게 한다. 상세 모달의 「현재」는
실시간 시세이므로 「실시간」으로 바꿔 카드와의 대비를 뚜렷하게 만든다.

**Tech Stack:** Next.js 16.3.4 App Router, React 19.2.4, TypeScript, vitest + @testing-library/react

**Spec:** `docs/dev-cycle/TODO.md` 의 `[JONGGA-015]` 항목

## Global Constraints

- 값을 바꾸지 않는다. `signal.current_price`, `signal.entry_price`, `signal.target_price`,
  `signal.stop_price` 가 화면에 그려지는 숫자는 이번 변경 전후로 같아야 한다.
- 실시간 시세를 새로 부르지 않는다. 카드 수만큼 외부 API 호출이 늘어난다.
- 건드리는 파일은 `frontend/src/app/dashboard/kr/closing-bet/page.tsx` 하나와 신규 테스트
  파일 하나뿐이다. 백엔드를 건드리지 않는다.
- 테스트는 기존 `page.regression-jongga-010.test.tsx` 의 형식을 따른다. 새 프레임워크나
  픽스처 계층을 들이지 않는다.

---

## 배경 — 조사로 확정한 사실

카드의 「현재가」는 `signal.current_price` 이고, 그 값은
`services/kr_market_data_cache_prices.py:130` 의 `load_latest_vcp_price_map` 이 만든다.
독스트링이 "daily_prices.csv에서 ticker별 최신 종가 맵을 로드한다" 라고 밝힌다. 실시간
시세를 부르는 자리가 아니다.

상세 모달의 「현재」는 다르다. `page.tsx:528` 이 `/api/kr/stock-detail/<code>` 를 부르고,
그 라우트가 `fetch_stock_price`(Toss → 네이버 → yfinance) 체인으로 실시간 시세를 얻는다.

실제 자료(`data/jongga_v2_latest.json`, 태웅)에서 값의 관계를 확정했다.

| 항목 | 값 | 파생 관계 |
|---|---|---|
| `entry_price` | 37,200 | 신호 발생 시점(`signal_date` 2026-09-02) 종가 |
| `target_price` | 39,060 | = `entry_price` × 1.05 |
| `stop_price` | 36,084 | = `entry_price` × 0.97 |
| `current_price` | 37,250 | `daily_prices.csv` 의 최신 종가. 위 셋과 무관 |

카드는 「현재가 ₩37,250」과 「매수가 ₩37,200」을 나란히 놓으면서 어느 쪽이 기준인지 밝히지
않는다. 목표가와 손절가는 앞의 값이 아니라 뒤의 값에서 나온다.

## File Structure

| 파일 | 책임 |
|---|---|
| `frontend/src/app/dashboard/kr/closing-bet/page.tsx` | `Signal` 인터페이스에 `signal_date` 추가, `SignalCard` 의 가격 라벨과 툴팁, 「전략 포인트」의 파생 근거 표기, `PriceRangeBar` 의 「현재」 라벨 |
| `frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-015.test.tsx` | 위 네 가지가 화면에 실제로 나오는지 고정 |

---

### Task 1: 카드의 가격 어휘와 파생 근거

**Files:**
- Modify: `frontend/src/app/dashboard/kr/closing-bet/page.tsx`
  - `Signal` 인터페이스 (95번째 줄 근처): `signal_date?: string;` 추가
  - `SignalCard` 본문 (1975번째 줄 근처): 파생 비율 헬퍼 추가
  - 「현재가」 블록 (2033-2042번째 줄): 라벨과 툴팁 교체
  - 「전략 포인트」 블록 (2273-2318번째 줄): 세 가격에 부가 표기
  - `PriceRangeBar` (316번째 줄): 「현재」 → 「실시간」
- Test: `frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-015.test.tsx`

**Interfaces:**
- Consumes: `Signal` 타입의 `current_price`, `entry_price`, `buy_price`, `target_price`,
  `stop_price`, `signal_date`
- Produces: 화면 문구 네 가지. 「종가」 라벨, 매수가 옆의 `(YYYY-MM-DD 종가)`,
  목표가·손절가 옆의 `(매수가 +N.N%)` / `(매수가 -N.N%)`, 모달의 「실시간」 라벨

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```tsx
// Regression: [JONGGA-015] — 카드가 「현재가」라는 이름으로 최근 거래일 종가를 보여주고,
// 매수·목표·손절가가 어느 값에서 파생되는지 밝히지 않던 문제
// 근거: docs/dev-cycle/TODO.md [JONGGA-015]

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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

vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

describe('[JONGGA-015] 종가베팅 카드의 가격 어휘', () => {
  it('가격 자리를 「현재가」가 아니라 「종가」라고 부른다', async () => {
    render(<JonggaV2Page />);

    expect(await screen.findByText('종가')).toBeTruthy();
    expect(screen.queryByText('현재가')).toBeNull();
  });

  it('종가 값 자체는 달라지지 않는다', async () => {
    render(<JonggaV2Page />);

    expect(await screen.findByText('₩37,250')).toBeTruthy();
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
});
```

- [ ] **Step 2: 테스트가 실패하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/app/dashboard/kr/closing-bet/page.regression-jongga-015.test.tsx`
Expected: FAIL. 「종가」를 찾지 못하고 「현재가」가 존재한다.

- [ ] **Step 3: `Signal` 인터페이스에 `signal_date` 를 추가한다**

`themes?: string[];` 줄 바로 앞에 넣는다.

```tsx
  signal_date?: string;
```

- [ ] **Step 4: `SignalCard` 안에 파생 비율 헬퍼를 만든다**

`const confidencePct = ...` 계산 다음, `return (` 앞에 넣는다.

```tsx
  // [JONGGA-015] 목표가와 손절가는 매수가에서 파생되고, 바로 위 「종가」와는 무관하다.
  // 두 값이 한 카드에 나란히 놓이므로 어느 쪽이 기준인지 화면에 적어 둔다.
  const basePrice = Math.round(signal.buy_price || signal.entry_price || 0);
  const pctFromBase = (price?: number): string | null => {
    if (!(basePrice > 0) || !price) return null;
    const pct = ((price - basePrice) / basePrice) * 100;
    return `(매수가 ${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%)`;
  };
```

- [ ] **Step 5: 「현재가」 라벨과 툴팁을 바꾼다**

```tsx
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                종가
                <Tooltip content="가장 최근 거래일의 종가입니다. 장중에 갱신되지 않으므로 실시간 시세와 다를 수 있습니다. 실시간 시세는 「상세 분석 보기」에서 확인하세요.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
```

- [ ] **Step 6: 「전략 포인트」의 세 가격에 파생 근거를 붙인다**

매수가:

```tsx
                    : <span className="text-emerald-400 font-mono">₩{basePrice.toLocaleString()}</span>
                    {signal.signal_date && (
                      <span className="text-gray-500 text-[10px] ml-1">({signal.signal_date} 종가)</span>
                    )}
```

목표가:

```tsx
                    : <span className="text-amber-400 font-mono">₩{Math.round(signal.target_price || 0).toLocaleString()}</span>
                    {pctFromBase(signal.target_price) && (
                      <span className="text-gray-500 text-[10px] ml-1">{pctFromBase(signal.target_price)}</span>
                    )}
```

손절가:

```tsx
                    : <span className="text-rose-400 font-mono">₩{Math.round(signal.stop_price || 0).toLocaleString()}</span>
                    {pctFromBase(signal.stop_price) && (
                      <span className="text-gray-500 text-[10px] ml-1">{pctFromBase(signal.stop_price)}</span>
                    )}
```

- [ ] **Step 7: `PriceRangeBar` 의 「현재」를 「실시간」으로 바꾼다**

```tsx
          <span className="text-[10px] text-gray-500 mr-2">실시간</span>
```

카드가 「종가」를 말하고 모달이 「실시간」을 말하면 두 값이 다른 것을 가리킨다는 사실이
이름만으로 드러난다.

- [ ] **Step 8: 테스트가 통과하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/app/dashboard/kr/closing-bet/page.regression-jongga-015.test.tsx`
Expected: PASS 4건

- [ ] **Step 9: 타입 검사와 전체 테스트를 돌린다**

Run: `cd frontend && npm run type-check && npx vitest run`
Expected: 타입 오류 0, 기존 테스트 전부 통과

---

## Self-Review

**1. Spec coverage** — `TODO.md` 의 체크박스 넷을 대조한다.

| 체크박스 | 대응 |
|---|---|
| 「현재가」가 어느 시점의 값이어야 하는지 정함 | 배경 절에서 확정. 실시간 갱신이 아니라 이름 정정 |
| 카드와 상세 모달이 같은 어휘를 쓰도록 정리 | Step 5(카드 「종가」)와 Step 7(모달 「실시간」) |
| 매수·목표·손절가가 어느 값에서 파생되는지 화면에 드러냄 | Step 4, Step 6 |
| 두 자리의 값이 어긋나지 않는 것을 검사로 고정 | Step 1 의 테스트 네 건 |

**2. Placeholder scan** — 모든 Step 이 실제 코드를 담고 있다. TBD 없음.

**3. Type consistency** — `pctFromBase` 는 `(price?: number) => string | null` 하나로
목표가와 손절가에 함께 쓰인다. `basePrice` 는 `number`. `signal_date` 는 `string | undefined`.
