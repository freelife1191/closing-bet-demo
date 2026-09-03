# [FLOW-010] 등급별 성과 카드의 집계 원천 교체 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 누적 성과 화면의 S·A·B 등급 카드가 현재 페이지 50행이 아니라 전체 기간을 집계하도록 원천을 백엔드 `kpi.roiByGrade` 로 옮긴다.

**Architecture:** 프론트엔드가 `trades` 배열로 등급 통계를 다시 계산하는 `calculateGradeStats` 를 걷어내고, 이미 전체 기간을 집계하고 있는 백엔드 `aggregate_cumulative_kpis` 의 `roiByGrade` 를 그대로 읽는다. 다만 현재 응답에는 건수와 평균 수익률만 있고 승률과 성공·실패 건수가 없으므로, 백엔드에서 등급별 `wins` 와 `losses` 와 `winRate` 를 함께 집계해 보낸다. 응답 payload 구조가 달라지므로 누적 성과 캐시의 스키마 버전을 함께 올린다.

**Tech Stack:** Python 3.11 (pytest), Next.js 16.3.4 / React 19.2.4 (vitest, @testing-library/react)

**Spec:** `docs/dev-cycle/TODO.md` 의 `[FLOW-010]` 항목과 `.gstack/qa-reports/qa-report-localhost-3500-2026-09-03.md` 의 ISSUE-001

## Global Constraints

- 티어는 **T3** 이다. 줄 수가 아니라 위험 경로 접촉이 사유이며, 닿는 파일은
  `services/kr_market_cumulative_cache.py` 하나다
  (`.claude/skills/dev-cycle/references/tier-rules.md` §2 「저장소 스키마」).
- 등급별 승률의 분모는 전체 KPI 와 같은 규칙을 쓴다. 즉 `wins / (wins + losses)` 이며
  `OPEN` 은 분모에서 뺀다. 소수 첫째 자리에서 반올림한다.
- 등급별 평균 수익률의 분모는 `OPEN` 을 포함한 전체 건수다. 기존 `avgRoi` 의 계산 규칙을
  그대로 두고 새 필드만 더한다.
- 화면의 수치 표기는 소수 첫째 자리다. 백엔드가 `avgRoi` 를 소수 둘째 자리로 주므로
  화면에서 기존 `roundToOne` 헬퍼를 거쳐 그린다.
- `roiByGrade` 를 담는 payload 는 `services/kr_market_cumulative_cache.py` 가 캐시하므로
  `_CUMULATIVE_CACHE_SCHEMA_VERSION` 을 `3` 에서 `4` 로 올린다. 올리지 않으면 옛 규칙으로
  저장된 항목이 새 필드 없이 적중해 화면이 승률 0% 를 그린다.

---

### Task 1: 백엔드가 등급별 승패와 승률을 함께 집계한다

**Files:**
- Modify: `services/kr_market_backtest_kpi_helpers.py:28-32,58-60,67-76`
- Modify: `services/kr_market_cumulative_cache.py:53`
- Test: `tests/services/test_kr_market_backtest_service.py:579-600`

**Interfaces:**
- Produces: `aggregate_cumulative_kpis(...)["roiByGrade"][grade]` 가
  `{"count": int, "avgRoi": float, "totalRoi": float, "wins": int, "losses": int, "winRate": float}`
  여섯 키를 담는다. Task 2 의 화면이 이 여섯 키를 그대로 읽는다.

- [ ] **Step 1: 실패하는 테스트로 바꾼다**

`tests/services/test_kr_market_backtest_service.py` 의
`test_aggregate_cumulative_kpis_computes_every_reported_metric` 에서 등급 세 줄을 바꾼다.
`OPEN` 이 승률의 분모에서 빠지고 평균 수익률의 분모에는 들어가는 것을 한 등급에서 함께
고정하기 위해 S 등급에 `OPEN` 한 건을 더한다.

```python
    trades = [
        {"outcome": "WIN", "roi": 9.0, "days": 2, "grade": "S"},
        {"outcome": "OPEN", "roi": 3.0, "days": 1, "grade": "S"},
        {"outcome": "WIN", "roi": 9.0, "days": 4, "grade": "A"},
        {"outcome": "LOSS", "roi": -5.0, "days": 1, "grade": "B"},
    ]

    kpi = aggregate_cumulative_kpis(trades, pd.DataFrame(), datetime(2026, 2, 21))

    assert kpi["totalSignals"] == 4
    assert (kpi["wins"], kpi["losses"], kpi["open"]) == (2, 1, 1)
    assert kpi["winRate"] == 66.7
    assert kpi["avgRoi"] == 4.0
    assert kpi["totalRoi"] == 16.0
    assert kpi["avgDays"] == 2.0
    assert kpi["profitFactor"] == 4.2
    assert kpi["priceDate"] == "2026-02-21"
    # S 등급: 승률의 분모는 종료된 1건이고, 평균 수익률의 분모는 OPEN 을 포함한 2건이다.
    assert kpi["roiByGrade"]["S"] == {
        "count": 2, "avgRoi": 6.0, "totalRoi": 12.0,
        "wins": 1, "losses": 0, "winRate": 100.0,
    }
    assert kpi["roiByGrade"]["A"] == {
        "count": 1, "avgRoi": 9.0, "totalRoi": 9.0,
        "wins": 1, "losses": 0, "winRate": 100.0,
    }
    assert kpi["roiByGrade"]["B"] == {
        "count": 1, "avgRoi": -5.0, "totalRoi": -5.0,
        "wins": 0, "losses": 1, "winRate": 0.0,
    }
```

같은 파일에 등급 통계가 페이지가 아니라 전체를 본다는 것을 고정하는 검사를 하나 더한다.

```python
def test_aggregate_cumulative_kpis_counts_every_trade_for_grade_stats():
    """등급 통계는 화면이 몇 건을 그리든 넘겨받은 전부를 센다.

    화면이 페이지당 50행만 그리던 시절에는 등급 카드가 그 50행으로 다시 계산되어,
    페이지를 넘기면 같은 등급의 승률과 부호가 통째로 바뀌었다.
    """
    trades = [
        {"outcome": "WIN", "roi": 1.0, "days": 1, "grade": "S"} for _ in range(60)
    ] + [
        {"outcome": "LOSS", "roi": -1.0, "days": 1, "grade": "S"} for _ in range(40)
    ]

    kpi = aggregate_cumulative_kpis(trades, pd.DataFrame(), datetime(2026, 2, 21))

    assert kpi["roiByGrade"]["S"]["count"] == 100
    assert kpi["roiByGrade"]["S"]["wins"] == 60
    assert kpi["roiByGrade"]["S"]["losses"] == 40
    assert kpi["roiByGrade"]["S"]["winRate"] == 60.0
```

- [ ] **Step 2: 실패를 확인한다**

Run: `venv/bin/pytest tests/services/test_kr_market_backtest_service.py -k aggregate_cumulative_kpis -v`
Expected: FAIL. 등급 딕셔너리에 `wins` 와 `losses` 와 `winRate` 가 없어 비교가 어긋난다.

- [ ] **Step 3: 집계기에 승패를 더한다**

`services/kr_market_backtest_kpi_helpers.py` 의 누적기 초기값에 두 칸을 더한다.

```python
    grade_acc: dict[str, dict[str, float]] = {
        "S": {"count": 0, "total_roi": 0.0, "wins": 0, "losses": 0},
        "A": {"count": 0, "total_roi": 0.0, "wins": 0, "losses": 0},
        "B": {"count": 0, "total_roi": 0.0, "wins": 0, "losses": 0},
    }
```

루프의 등급 분기에서 결과를 함께 센다.

```python
        if grade in grade_acc:
            grade_acc[grade]["count"] += 1
            grade_acc[grade]["total_roi"] += roi
            if outcome == "WIN":
                grade_acc[grade]["wins"] += 1
            elif outcome == "LOSS":
                grade_acc[grade]["losses"] += 1
```

응답을 만드는 자리에서 승률을 계산해 넣는다. 분모는 전체 KPI 의 `win_rate` 와 같은
규칙을 쓴다.

```python
    roi_by_grade: dict[str, dict[str, Any]] = {}
    for grade in ["S", "A", "B"]:
        grade_count = int(grade_acc[grade]["count"])
        grade_total_roi = float(grade_acc[grade]["total_roi"])
        grade_avg_roi = round(grade_total_roi / grade_count, 2) if grade_count > 0 else 0.0
        grade_wins = int(grade_acc[grade]["wins"])
        grade_losses = int(grade_acc[grade]["losses"])
        grade_closed = grade_wins + grade_losses
        grade_win_rate = (
            round((grade_wins / grade_closed) * 100, 1) if grade_closed > 0 else 0.0
        )
        roi_by_grade[grade] = {
            "count": grade_count,
            "avgRoi": grade_avg_roi,
            "totalRoi": round(grade_total_roi, 1),
            "wins": grade_wins,
            "losses": grade_losses,
            "winRate": grade_win_rate,
        }
```

- [ ] **Step 4: 캐시 스키마 버전을 올린다**

`services/kr_market_cumulative_cache.py:53` 의 상수를 올린다. 이 파일은 위험 경로에 있고,
이 한 줄이 이번 항목의 티어를 T3 으로 만든다.

```python
_CUMULATIVE_CACHE_SCHEMA_VERSION = 4
```

- [ ] **Step 5: 통과를 확인한다**

Run: `venv/bin/pytest tests/services/test_kr_market_backtest_service.py -v`
Expected: PASS

---

### Task 2: 화면이 등급 카드를 전체 기간 값으로 그린다

**Files:**
- Modify: `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx:25-29,902-907,974-1000`
- Test: `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-flow-010.test.tsx` (신규)

**Interfaces:**
- Consumes: Task 1 이 만든 `kpi.roiByGrade[grade]` 의 여섯 키
  (`count`, `avgRoi`, `totalRoi`, `wins`, `losses`, `winRate`).

- [ ] **Step 1: 실패하는 회귀 테스트를 쓴다**

`CumulativeClientPage.regression-flow-010.test.tsx` 를 새로 만든다. 형식은 같은 디렉터리의
`CumulativeClientPage.regression-flow-004.test.tsx` 를 따른다. 표에 그려지는 `trades` 와
`kpi.roiByGrade` 를 일부러 어긋나게 두어, 화면이 어느 쪽을 읽는지 갈라낸다.

```tsx
// Regression: [FLOW-010] 등급 카드가 전체 기간이 아니라 현재 페이지만 집계하던 문제
//
// 등급 카드가 표에 그려진 50행으로 다시 계산되어, 페이지를 넘기면 같은 등급의 건수와
// 승률과 평균 수익률이 통째로 바뀌었다. S 등급은 1페이지에서 -3%, 2페이지에서 +4.3%
// 로 부호까지 뒤집혔고, 그 부호에 근거한 전략 조언 문구까지 함께 달라졌다.

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

// 전체 기간의 S 등급은 16건이고 평균 수익률이 양수다.
const ROI_BY_GRADE = {
  S: { count: 16, avgRoi: 0.25, totalRoi: 4.0, wins: 6, losses: 10, winRate: 37.5 },
  A: { count: 26, avgRoi: 1.57, totalRoi: 40.8, wins: 8, losses: 18, winRate: 30.8 },
  B: { count: 131, avgRoi: 0.21, totalRoi: 27.0, wins: 46, losses: 85, winRate: 35.1 },
};

// 이 페이지에 그려지는 S 등급은 2건뿐이고 둘 다 손실이다. 화면이 이쪽을 읽으면
// 건수 2 와 승률 0% 가 나온다.
const PAGE_TRADES = [
  { ticker: '005930', name: '삼성전자', grade: 'S', outcome: 'LOSS', roi: -3, days: 2, score: 12, themes: [] },
  { ticker: '000660', name: 'SK하이닉스', grade: 'S', outcome: 'LOSS', roi: -3, days: 2, score: 12, themes: [] },
];

function mockCumulativeResponse() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        trades: PAGE_TRADES,
        kpi: {
          totalSignals: 173,
          wins: 60,
          losses: 113,
          open: 0,
          winRate: 34.7,
          avgRoi: 0.4,
          totalRoi: 71.8,
          avgDays: 3.1,
          priceDate: '2026-09-02',
          profitFactor: 1.09,
          roiByGrade: ROI_BY_GRADE,
        },
        pagination: { total: 173, page: 1, limit: 50, totalPages: 4 },
      }),
    })),
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-010] 등급 카드의 집계 원천', () => {
  it('현재 페이지가 아니라 전체 기간 건수를 보여준다', async () => {
    mockCumulativeResponse();

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('2026-09-02')).not.toBeNull());
    // 전체 기간 값
    expect(screen.getAllByText('16건').length).toBeGreaterThan(0);
    expect(screen.getAllByText('26건').length).toBeGreaterThan(0);
    expect(screen.getAllByText('131건').length).toBeGreaterThan(0);
    // 현재 페이지의 S 등급 2건이 카드에 새어 나오지 않아야 한다.
    expect(screen.queryByText('2건')).toBeNull();
  });

  it('현재 페이지가 전패여도 전체 기간 승률을 보여준다', async () => {
    mockCumulativeResponse();

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('2026-09-02')).not.toBeNull());
    expect(screen.getAllByText('37.5%').length).toBeGreaterThan(0);
    // 페이지의 두 건으로 다시 계산하면 0% 가 나온다.
    expect(screen.queryByText('0%')).toBeNull();
  });

  it('현재 페이지가 손실이어도 전체 기간의 양수 평균 수익률을 보여준다', async () => {
    mockCumulativeResponse();

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('2026-09-02')).not.toBeNull());
    // 소수 첫째 자리 표기이므로 0.25 는 +0.3% 로 그려진다.
    expect(screen.getAllByText('+0.3%').length).toBeGreaterThan(0);
    // 페이지의 두 건으로 다시 계산하면 -3% 가 나온다.
    expect(screen.queryByText('-3%')).toBeNull();
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd frontend && npx vitest run src/app/dashboard/kr/cumulative/CumulativeClientPage.regression-flow-010.test.tsx`
Expected: FAIL. 카드가 `2건` 과 `0%` 와 `-3%` 를 그린다.

- [ ] **Step 3: 타입에 세 필드를 더한다**

`CumulativeClientPage.tsx:25-29` 의 인터페이스를 넓힌다.

```tsx
interface GradeRoiData {
  count: number;
  avgRoi: number;
  totalRoi: number;
  wins: number;
  losses: number;
  winRate: number;
}
```

`createEmptyRoiByGrade` 의 기본값도 같은 모양으로 맞춘다. 응답에 필드가 빠져 있어도
화면이 `undefined` 를 그리지 않게 하는 방어선이다.

```tsx
  const createEmptyRoiByGrade = () => {
    const empty = { count: 0, avgRoi: 0, totalRoi: 0, wins: 0, losses: 0, winRate: 0 };
    return { S: { ...empty }, A: { ...empty }, B: { ...empty } };
  };
```

- [ ] **Step 4: 재계산 함수를 지우고 KPI 를 읽는다**

`calculateGradeStats` 와 `sStats`·`aStats`·`bStats` 세 줄을 지운다. 화면의 표기가 소수
첫째 자리이므로 평균 수익률만 기존 `roundToOne` 을 거친다.

```tsx
  // 등급 카드는 전체 기간을 집계한 kpi.roiByGrade 를 읽는다. 표에 그려지는 trades 는
  // 현재 페이지분이므로 그것으로 다시 계산하면 페이지마다 값이 달라진다.
  const gradeCards = [
    { grade: 'S', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20', tooltipKey: 'gradeS' as const },
    { grade: 'A', color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20', tooltipKey: 'gradeA' as const },
    { grade: 'B', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20', tooltipKey: 'gradeB' as const },
  ].map((card) => {
    const stats = kpi.roiByGrade[card.grade as 'S' | 'A' | 'B'];
    return {
      ...card,
      count: stats.count,
      winRate: stats.winRate,
      avgRoi: roundToOne(stats.avgRoi),
      wins: stats.wins,
      losses: stats.losses,
    };
  });
```

- [ ] **Step 5: 통과를 확인한다**

Run: `cd frontend && npx vitest run src/app/dashboard/kr/cumulative/ && npx tsc --noEmit`
Expected: 새 회귀 검사 세 건과 기존 두 파일 모두 PASS, 타입 오류 0

---

### Task 3: 전체 검증과 마감

**Files:**
- Modify: `docs/dev-cycle/TODO.md` (항목 제거)
- Modify: `docs/dev-cycle/archive/daily/2026-09-03.md`, `docs/dev-cycle/archive/2026-09.md`

- [ ] **Step 1: 티어에 배정된 리뷰를 순서대로 돌린다**

`/ponytail-review` → `/code-review` → `/review` 순서다. 순서를 바꾸지 않는다.

- [ ] **Step 2: 전체 검증을 돌린다**

```bash
venv/bin/pytest
cd frontend && npm run test && npm run type-check
```
Expected: pytest 전부 통과, vitest 전부 통과, tsc 오류 0

- [ ] **Step 3: 서버를 재기동하고 브라우저로 값을 대조한다**

파이썬을 바꿨으므로 gunicorn 워커를 다시 띄운다. 그다음 `next-dev-loop` 으로
`http://localhost:3500/dashboard/kr/cumulative` 를 열어 1페이지와 2페이지의 등급 카드가
같은 값을 유지하는지 본다. 기대값은 S `16건 / 37.5%`, A `26건`, B `131건` 이며 페이지를
넘겨도 바뀌지 않아야 한다.

- [ ] **Step 4: `/qa-only` 를 돌린다**

압축 지점이므로 부르기 직전에 턴을 끝낸다.

```
/qa-only http://localhost:3500/dashboard/kr/cumulative --quick
```

- [ ] **Step 5: 커밋 두 개로 마감한다**

첫 커밋은 구현과 `TODO.md` 항목 제거, 둘째 커밋은 아카이브 기록이다.
