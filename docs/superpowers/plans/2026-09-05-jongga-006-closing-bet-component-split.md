# [JONGGA-006] 종가베팅 페이지의 범용 컴포넌트와 정적 모달 분리 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2,761줄인 종가베팅 페이지에서 화면 고유 로직을 담지 않은 선언을 걷어내고, 세 벌로 흩어진 `Tooltip` 을 공용 컴포넌트 하나로 모읍니다.

**Architecture:** 옮기는 자리를 의존 방향으로 정합니다. 라우트의 헬퍼에 의존하는 것은 그 라우트 디렉터리 안에 두고, 아무것에도 의존하지 않는 정적 모달만 `components/` 로 내보냅니다. `Tooltip` 은 트리 모양이 세 사본 모두 같고 CSS 클래스만 다르므로, 변형 컴포넌트를 나누지 않고 열거형 프롭 하나로 흡수합니다.

**Tech Stack:** Next.js 16.3.4 App Router, React 19.2.4, TypeScript, Tailwind CSS, vitest

**Spec:** `docs/dev-cycle/audits/AUDIT-JONGGA.md` §2.2, §4.1 및 `docs/dev-cycle/TODO.md` 의 `[JONGGA-006]` 항목

## Global Constraints

- 화면에 보이는 결과가 달라지면 안 됩니다. 이 항목은 리팩터링이며 시각 변경을 포함하지 않습니다.
- 공용 `Tooltip` 을 이미 쓰고 있는 17곳의 시각을 그대로 보존합니다.
- 지역 사본을 쓰던 52곳의 시각도 그대로 보존합니다.
- `frontend/src/app/components/` 아래의 파일이 특정 라우트 디렉터리의 모듈을 import 하지 않습니다.
- 검증 명령은 `cd frontend && npx vitest run`, `cd frontend && npm run type-check`, `cd frontend && npm run build` 셋입니다.

---

## 조사로 확정한 사실

계획의 근거이므로 구현 중에 다시 조사하지 않습니다.

### `Tooltip` 세 사본의 차이

| 항목 | `components/Tooltip.tsx` (50줄) | `closing-bet/page.tsx:34` (34줄) | `data-status/page.tsx:9` (33줄) |
|---|---|---|---|
| 폭 | `min-w-[260px] w-max max-w-[320px]` | `w-52 max-w-[220px]` 또는 `wide` 일 때 `w-64 max-w-[280px]` | 좌동 |
| 안쪽 여백 | `px-4 py-3` | `px-3 py-2` | `px-3 py-2` |
| 글자 크기 | `text-xs` | `text-[10px]` | `text-[10px]` |
| 모서리 | `rounded-xl` | `rounded-lg` | `rounded-lg` |
| 정렬 | `text-left` + `break-keep` | `text-center` | `text-center` |
| 고유 프롭 | `as?: 'span' \| 'div'` | `wide?: boolean`, `width?: string` | `wide?: boolean` |
| `content` 타입 | `React.ReactNode` | `React.ReactNode` | `string` |

### 호출 건수

| 어느 것을 쓰는가 | 파일 | 건수 |
|---|---|---|
| 공용 (큰 시각) | `dashboard/kr/page.tsx` | 12 |
| 공용 (큰 시각) | `dashboard/kr/cumulative/CumulativeClientPage.tsx` | 5 |
| 사본 (작은 시각) | `dashboard/kr/closing-bet/page.tsx` | 51 (그중 `wide` 를 넘기는 것 6) |
| 사본 (작은 시각) | `dashboard/data-status/page.tsx` | 1 (`wide` 를 넘기지 않음) |

작은 시각을 쓰는 곳이 52 이고 큰 시각을 쓰는 곳이 17 이므로, **기본값을 작은 시각으로 두고 큰 시각을 쓰는 17곳에만 프롭을 붙이는 것이 최소 변경**입니다.

### 죽은 코드 둘

- **`ScoreBar`** (`closing-bet/page.tsx:2741`, 21줄): 저장소 전체에서 `<ScoreBar` 를 부르는 자리가 한 곳도 없고 export 도 되지 않습니다. 옮기지 않고 지웁니다.
- **`Tooltip` 의 `width` 프롭** (`closing-bet/page.tsx:34`): `width=` 로 값을 넘기는 호출이 한 곳도 없습니다. 공용 컴포넌트로 옮기지 않습니다.

### 이동처를 의존 방향으로 정한 근거

TODO 항목은 `PriceRangeBar` 와 `StatBox` 를 「컴포넌트 디렉터리로 이동」이라고 적었으나, 조사에서 다음이 드러났습니다.

- `PriceRangeBar` 는 `isPositivePrice` 를 씁니다. 이 함수는 같은 라우트 디렉터리의 `closing-bet/displayHelpers.ts:44` 에 있습니다. `components/` 로 옮기면 공용 컴포넌트가 특정 라우트의 헬퍼를 가로질러 import 하게 되어 의존 방향이 뒤집힙니다.
- 두 컴포넌트를 부르는 곳은 종가베팅 페이지뿐입니다. `PriceRangeBar` 2건, `StatBox` 3건이며 모두 같은 파일 안입니다.
- 그 라우트 디렉터리에는 `displayHelpers.ts` 라는 선례가 이미 있습니다. 표시용 헬퍼를 라우트 옆에 두는 관례가 정착되어 있습니다.

따라서 둘은 `closing-bet/displayPrimitives.tsx` 로 옮깁니다. 반면 `GradeGuideModal` 은 `Modal` 에만 의존하는 정적 마크업이고, 성격이 같은 `ClosingBetCriteriaModal` 이 이미 `components/` 에 나가 있으므로 TODO 대로 그 자리로 옮깁니다.

### 조합 프롭을 열거형으로 정한 근거

`vercel-composition-patterns` 의 `architecture-avoid-boolean-props` 와 `patterns-explicit-variants` 를 읽었습니다. 두 규칙이 겨냥하는 것은 `isThread` 나 `isEditing` 처럼 **렌더 트리의 구성 자체를 바꾸는** 불리언입니다. 그런 불리언은 조합이 지수적으로 늘고 컴포넌트 안에 조건문이 쌓입니다.

`Tooltip` 은 그 경우가 아닙니다. 세 사본의 트리는 모두 `<Component>` 안에 `{children}` 과 툴팁 `<div>` 와 화살표 `<div>` 를 두는 같은 모양이고, 다른 것은 클래스 문자열뿐입니다. 그러므로 변형 컴포넌트를 나누면 통합의 목적이 사라지고 사본이 다시 늘어납니다. 대신 두 규칙의 취지를 다음과 같이 지킵니다.

- `wide` 라는 **불리언을 없애고** 값이 셋인 `size` 열거형으로 바꿉니다. 조합이 3으로 고정되어 지수적으로 늘지 않습니다.
- 클래스 결정을 조회표 하나로 두어 컴포넌트 안에 조건문이 쌓이지 않게 합니다.

---

## File Structure

| 파일 | 책임 | 처리 |
|---|---|---|
| `frontend/src/app/components/Tooltip.tsx` | 세 시각을 모두 표현하는 유일한 툴팁 | 수정 |
| `frontend/src/app/components/Tooltip.test.tsx` | `size` 세 값과 기본값의 회귀 검사 | 신규 |
| `frontend/src/app/components/GradeGuideModal.tsx` | 종가베팅 등급 기준 정적 표 | 신규 (이동) |
| `frontend/src/app/dashboard/kr/closing-bet/displayPrimitives.tsx` | 종가베팅 화면의 표시용 프리미티브 둘 | 신규 (이동) |
| `frontend/src/app/dashboard/kr/closing-bet/page.tsx` | 페이지 본체 | 수정 (선언 넷 제거) |
| `frontend/src/app/dashboard/data-status/page.tsx` | 데이터 상태 화면 | 수정 (사본 제거) |
| `frontend/src/app/dashboard/kr/page.tsx` | 대시보드 홈 | 수정 (`size="lg"` 12곳) |
| `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx` | 누적 성과 화면 | 수정 (`size="lg"` 5곳) |

---

### Task 1: `Tooltip` 에 `size` 를 넣고 세 시각을 흡수한다

**Files:**
- Modify: `frontend/src/app/components/Tooltip.tsx`
- Test: `frontend/src/app/components/Tooltip.test.tsx`

**Interfaces:**
- Produces: `Tooltip` 의 프롭에 `size?: 'sm' | 'md' | 'lg'` 가 더해지며 기본값은 `'sm'` 입니다. 기존 프롭 `children` `content` `className` `position` `align` `as` 는 그대로입니다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```tsx
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import Tooltip from './Tooltip';

// [JONGGA-006] 툴팁이 세 벌로 흩어져 있던 동안 시각이 서로 달랐다. 하나로 모으면서
// 그 차이를 size 로 흡수했으므로, 세 값이 실제로 다른 상자를 만드는지 여기서 고정한다.
function 툴팁상자(size?: 'sm' | 'md' | 'lg') {
  const { container } = render(
    <Tooltip content="설명" {...(size ? { size } : {})}>
      <i />
    </Tooltip>,
  );
  return container.querySelector('.absolute')!.className;
}

describe('Tooltip 의 size', () => {
  it('기본값은 작은 시각이다', () => {
    // 호출 69곳 가운데 52곳이 작은 시각을 쓴다. 기본값이 그쪽이라야 프롭을 붙일 곳이 적다.
    expect(툴팁상자()).toContain('w-52');
    expect(툴팁상자()).toContain('text-[10px]');
  });

  it('md 는 폭만 넓히고 나머지는 sm 과 같다', () => {
    expect(툴팁상자('md')).toContain('w-64');
    expect(툴팁상자('md')).toContain('text-[10px]');
  });

  it('lg 는 종전 공용 시각을 그대로 낸다', () => {
    const cls = 툴팁상자('lg');
    expect(cls).toContain('min-w-[260px]');
    expect(cls).toContain('text-xs');
    expect(cls).toContain('text-left');
  });
});
```

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

```bash
cd frontend && npx vitest run src/app/components/Tooltip.test.tsx
```

기대: `size` 프롭이 아직 없으므로 타입이 맞지 않고 `w-52` 도 나오지 않아 실패합니다.

- [ ] **Step 3: `size` 를 구현한다**

`TooltipProps` 에 `size?: 'sm' | 'md' | 'lg'` 를 더하고 기본값을 `'sm'` 으로 둡니다. 클래스는 조회표 하나로 정합니다.

```tsx
const SIZE_CLASSES = {
  sm: 'w-52 max-w-[220px] px-3 py-2 text-[10px] rounded-lg text-center',
  md: 'w-64 max-w-[280px] px-3 py-2 text-[10px] rounded-lg text-center',
  lg: 'min-w-[260px] w-max max-w-[320px] px-4 py-3 text-xs rounded-xl text-left break-keep',
} as const;
```

툴팁 `<div>` 의 클래스에서 폭과 여백과 글자 크기와 모서리와 정렬에 해당하는 부분을 지우고 `${SIZE_CLASSES[size]}` 로 대신합니다. 나머지(`bg-gray-900/95`, `text-gray-200`, `font-medium`, `opacity-0 group-hover/tooltip:opacity-100`, `transition-opacity`, `pointer-events-none`, `z-[100]`, `border border-white/10`, `shadow-xl`, `backdrop-blur-sm`, `leading-relaxed`, `whitespace-normal`)는 세 시각이 공유하므로 그대로 둡니다.

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

```bash
cd frontend && npx vitest run src/app/components/Tooltip.test.tsx
```

기대: 3건 통과.

---

### Task 2: 공용 `Tooltip` 을 이미 쓰던 17곳의 시각을 보존한다

**Files:**
- Modify: `frontend/src/app/dashboard/kr/page.tsx` (12곳)
- Modify: `frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx` (5곳)

**Interfaces:**
- Consumes: Task 1 이 만든 `size` 프롭.

Task 1 에서 기본값이 `'sm'` 으로 바뀌었으므로, 손대지 않으면 이 두 화면의 툴팁이 작아집니다. 이 항목은 시각을 바꾸지 않는 리팩터링이므로 17곳 전부에 `size="lg"` 를 붙입니다.

- [ ] **Step 1: 두 파일의 모든 `<Tooltip` 에 `size="lg"` 를 붙인다**

`dashboard/kr/page.tsx` 는 747, 782, 802, 807, 810, 813, 852, 876, 922, 1000, 1075, 1150 행입니다. `cumulative/CumulativeClientPage.tsx` 는 388, 395, 588, 701, 798 행입니다.

- [ ] **Step 2: 빠뜨린 곳이 없는지 센다**

```bash
grep -c 'size="lg"' frontend/src/app/dashboard/kr/page.tsx frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx
```

기대: 각각 12 와 5.

- [ ] **Step 3: 타입 검사를 돌린다**

```bash
cd frontend && npm run type-check
```

기대: 통과.

---

### Task 3: 데이터 상태 화면의 사본을 없앤다

**Files:**
- Modify: `frontend/src/app/dashboard/data-status/page.tsx`

이 화면의 사본은 9~41행이고 호출은 693행 한 곳뿐이며 `wide` 를 넘기지 않습니다. 그러므로 공용 컴포넌트의 기본값(`sm`)이 그대로 맞습니다. 호출부는 손대지 않습니다.

- [ ] **Step 1: 사본을 지우고 import 를 넣는다**

9~41행의 `function Tooltip(...)` 전체를 지우고, 상단 import 목록에 다음을 더합니다.

```tsx
import Tooltip from '@/app/components/Tooltip';
```

- [ ] **Step 2: 검증한다**

```bash
cd frontend && npm run type-check
```

기대: 통과. 사본의 `content` 는 `string` 이었고 공용은 `React.ReactNode` 이므로 넓어지는 방향이라 기존 호출이 그대로 맞습니다.

---

### Task 4: 종가베팅 페이지의 사본을 없애고 `wide` 를 `size` 로 바꾼다

**Files:**
- Modify: `frontend/src/app/dashboard/kr/closing-bet/page.tsx`

- [ ] **Step 1: 지역 `Tooltip` 정의를 지우고 import 를 넣는다**

33~66행(주석 한 줄 포함)을 지우고 상단에 `import Tooltip from '@/app/components/Tooltip';` 을 더합니다.

- [ ] **Step 2: `wide` 를 넘기는 6곳을 `size="md"` 로 바꾼다**

1456, 1476, 1898, 1908, 2197, 2456 행입니다. 나머지 45곳은 기본값이 맞으므로 손대지 않습니다.

- [ ] **Step 3: `wide` 가 남지 않았는지 확인한다**

```bash
grep -n '<Tooltip[^>]*wide' frontend/src/app/dashboard/kr/closing-bet/page.tsx
```

기대: 출력 없음. `tracking-wider` 같은 다른 낱말은 이 패턴에 걸리지 않습니다.

- [ ] **Step 4: 검증한다**

```bash
cd frontend && npm run type-check
```

---

### Task 5: 죽은 `ScoreBar` 를 지운다

**Files:**
- Modify: `frontend/src/app/dashboard/kr/closing-bet/page.tsx`

- [ ] **Step 1: 사용처가 없음을 다시 확인한다**

```bash
grep -rn 'ScoreBar' frontend/src
```

기대: 정의 한 줄만 나옵니다. 다른 줄이 나오면 이 태스크를 중단하고 그 자리를 먼저 봅니다.

- [ ] **Step 2: 2740~2761행의 `function ScoreBar(...)` 를 통째로 지운다**

- [ ] **Step 3: 검증한다**

```bash
cd frontend && npm run type-check && npx vitest run
```

---

### Task 6: `PriceRangeBar` 와 `StatBox` 를 형제 파일로 옮긴다

**Files:**
- Create: `frontend/src/app/dashboard/kr/closing-bet/displayPrimitives.tsx`
- Modify: `frontend/src/app/dashboard/kr/closing-bet/page.tsx`

**Interfaces:**
- Produces: `export function PriceRangeBar({ low, high, current, label })` 와 `export function StatBox({ label, value, highlight, customValue, tooltip })`. 시그니처는 지금과 같습니다.

- [ ] **Step 1: 새 파일을 만든다**

```tsx
'use client';

import React from 'react';

import Tooltip from '@/app/components/Tooltip';
import { isPositivePrice } from './displayHelpers';

// [JONGGA-006] 종가베팅 화면의 표시용 프리미티브. 화면 고유 로직을 담지 않으므로
// 페이지 본체에서 떼어냈다. 다만 isPositivePrice 가 같은 디렉터리의 헬퍼이므로
// components/ 가 아니라 이 자리에 둔다. 공용 디렉터리에 두면 공용 컴포넌트가
// 특정 라우트의 모듈을 가로질러 가져오게 되어 의존 방향이 뒤집힌다.
```

그 아래에 `page.tsx` 의 349~407행(`PriceRangeBar`)과 1983~1999행(`StatBox`)을 옮겨 붙이고 각각 `export` 를 붙입니다. 본문은 한 글자도 바꾸지 않습니다.

- [ ] **Step 2: `page.tsx` 에서 두 정의를 지우고 import 를 넣는다**

```tsx
import { PriceRangeBar, StatBox } from './displayPrimitives';
```

- [ ] **Step 3: 검증한다**

```bash
cd frontend && npm run type-check && npx vitest run
```

기대: 통과. 이 페이지의 회귀 테스트가 여덟 개 있으므로 이동이 렌더 결과를 바꿨다면 여기서 드러납니다.

---

### Task 7: `GradeGuideModal` 을 컴포넌트 디렉터리로 옮긴다

**Files:**
- Create: `frontend/src/app/components/GradeGuideModal.tsx`
- Modify: `frontend/src/app/dashboard/kr/closing-bet/page.tsx`

**Interfaces:**
- Produces: `export default function GradeGuideModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void })`.

- [ ] **Step 1: 새 파일을 만든다**

형식은 같은 디렉터리의 `ClosingBetCriteriaModal.tsx` 를 그대로 따릅니다. 맨 위에 `'use client';` 와 `import React from 'react';` 와 `import Modal from './Modal';` 을 두고, `page.tsx` 의 2564~2738행 본문을 옮깁니다. `Modal` 의 import 경로가 `@/app/components/Modal` 에서 `./Modal` 로 바뀌는 것 외에는 본문을 바꾸지 않습니다.

- [ ] **Step 2: `page.tsx` 에서 정의를 지우고 import 를 넣는다**

```tsx
import GradeGuideModal from '@/app/components/GradeGuideModal';
```

호출부(1656행)는 손대지 않습니다.

- [ ] **Step 3: 검증한다**

```bash
cd frontend && npm run type-check && npx vitest run
```

---

### Task 8: 전체 검증과 규모 확인

- [ ] **Step 1: 세 명령을 모두 돌린다**

```bash
cd frontend && npx vitest run && npm run type-check && npm run build
```

- [ ] **Step 2: 페이지가 실제로 줄었는지 확인한다**

```bash
wc -l frontend/src/app/dashboard/kr/closing-bet/page.tsx
```

기대: 2,761줄에서 2,450줄 안팎으로 줄어듭니다.

- [ ] **Step 3: 티어를 재판정한다**

```bash
git diff --stat
```

추가와 삭제의 합계가 300줄을 넘으면 T3 을 유지합니다.

---

## Self-Review

**1. 근거 문서 대응**: AUDIT-JONGGA §2.2(Tooltip 삼중 정의)는 Task 1·3·4 가, §4.1 의 1번(범용 프리미티브)은 Task 5·6 이, 5번(정적 참조 문서)은 Task 7 이 각각 처리합니다. §4.1 의 2·3·4·6번(`TradingViewChart`, `ChartModal`, `StockDetailModal`, `DataStatusBox`, 페이지 본체)은 이 항목의 범위 밖이며 TODO 항목도 요구하지 않습니다.

**2. TODO 체크박스 대응**: 여섯 개 가운데 다섯째(`npm run build` 등)와 여섯째(`/qa-only`)는 dev-cycle 의 [3] 검증이 맡습니다. 나머지 넷은 Task 1·3·4(첫째와 둘째), Task 6(셋째), Task 7(넷째)이 처리합니다.

**3. TODO 와 갈리는 곳**: 셋째 체크박스는 `PriceRangeBar` 와 `StatBox` 와 `ScoreBar` 를 「컴포넌트 디렉터리로 이동」이라 적었으나, 조사 결과 `ScoreBar` 는 죽은 코드여서 지우고(Task 5) 나머지 둘은 의존 방향 때문에 라우트 디렉터리 안에 둡니다(Task 6). 근거는 위의 「이동처를 의존 방향으로 정한 근거」에 있으며 마감 보고에 함께 적습니다.

**4. 타입 일관성**: `size` 는 Task 1 에서 `'sm' | 'md' | 'lg'` 로 정의되고 Task 2·4 가 그 값을 그대로 씁니다. `PriceRangeBar` 와 `StatBox` 와 `GradeGuideModal` 의 시그니처는 이동 전후가 같습니다.
