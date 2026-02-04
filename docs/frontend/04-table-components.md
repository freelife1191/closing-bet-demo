# 테이블 컴포넌트 반응형 패턴

이 문서는 테이블 컴포넌트의 반응형 디자인 패턴을 다룹니다.

## 1. 기본 반응형 테이블

### 전체 패턴

```tsx
<div className="rounded-2xl bg-[#1c1c1e] border border-white/10 overflow-hidden">
  {/* Scrollable Container for Mobile */}
  <div className="overflow-x-auto">
    <table className="w-full text-left border-collapse min-w-[1000px]">
      {/* Header */}
      <thead className="bg-black/20">
        <tr className="text-[10px] text-gray-500 border-b border-white/5 uppercase tracking-wider">
          <th className="px-4 py-3 font-semibold">Column 1</th>
          <th className="px-4 py-3 font-semibold">Column 2</th>
          <th className="px-4 py-3 font-semibold text-right">Column 3</th>
        </tr>
      </thead>

      {/* Body */}
      <tbody className="divide-y divide-white/5 text-sm">
        {data.map((row) => (
          <tr key={row.id} className="hover:bg-white/5 transition-colors">
            <td className="px-4 py-3">{row.value1}</td>
            <td className="px-4 py-3">{row.value2}</td>
            <td className="px-4 py-3 text-right">{row.value3}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
</div>
```

### 핵심 클래스

| 클래스 | 설명 |
|--------|------|
| `overflow-x-auto` | 모바일에서 가로 스크롤 활성화 |
| `min-w-[1000px]` | 최소 너비 설정 (스크롤 발생 지점) |
| `text-left` / `text-right` | 텍스트 정렬 |
| `hover:bg-white/5` | 행 호버 효과 |

## 2. VCP 시그널 테이블 (복합 패턴)

```tsx
<div className="rounded-2xl bg-[#1c1c1e] border border-white/10 overflow-hidden">
  <div className="overflow-x-auto">
    <table className="w-full text-left border-collapse min-w-[1000px]">
      <thead className="bg-black/20">
        <tr className="text-[10px] text-gray-500 border-b border-white/5 uppercase tracking-wider">
          {/* Stock Name Column */}
          <th className="px-4 py-3 font-semibold min-w-[120px]">Stock</th>

          {/* Date Column */}
          <th className="px-4 py-3 font-semibold whitespace-nowrap">Date</th>

          {/* Numeric Column with Tooltip */}
          <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
            <Tooltip text="외국인 5일 연속 순매수 금액">
              외국인 5D
            </Tooltip>
          </th>

          {/* Center Column (Icon/Action) */}
          <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
            Action
          </th>
        </tr>
      </thead>

      <tbody className="divide-y divide-white/5 text-sm">
        {signals.map((signal) => (
          <tr
            key={signal.ticker}
            onClick={() => handleRowClick(signal)}
            className="hover:bg-white/5 transition-colors cursor-pointer group"
          >
            {/* Multi-line Cell */}
            <td className="px-4 py-3">
              <div className="flex flex-col whitespace-nowrap">
                <span className="font-bold text-white group-hover:text-blue-400 transition-colors">
                  {signal.name}
                </span>
                <span className="text-[10px] text-gray-500">{signal.ticker}</span>
              </div>
            </td>

            {/* Date Cell */}
            <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
              {signal.date}
            </td>

            {/* Numeric Cell with Icon */}
            <td className={`px-4 py-3 text-right font-mono text-xs ${
              signal.value > 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              <div className="flex items-center justify-end gap-1">
                {signal.value > 0 && <i className="fas fa-arrow-up text-[8px]"></i>}
                {formatValue(signal.value)}
              </div>
            </td>

            {/* Center Button Cell */}
            <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
              <button className="w-8 h-8 rounded-full bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white transition-all">
                <i className="fas fa-shopping-cart text-xs"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
</div>
```

### 셀 정렬 패턴

| 셀 타입 | 정렬 | 클래스 |
|---------|------|--------|
| 텍스트 (왼쪽) | `text-left` | 기본 |
| 숫자 (오른쪽) | `text-right` | `text-right` |
| 아이콘/버튼 (중앙) | `text-center` | `text-center` |
| 고정 너비 | - | `min-w-[120px]` |
| 줄바꿈 방지 | - | `whitespace-nowrap` |

## 3. 색상 조건부 셀

```tsx
{/* 숫자에 따른 색상 변화 */}
<td className={`px-4 py-3 text-right font-mono text-xs font-bold ${
  Math.abs(value) >= 0.01
    ? (value >= 0 ? 'text-green-400' : 'text-red-400')
    : 'text-gray-500'
}`}>
  {Math.abs(value) < 0.01 ? (
    <span className="text-gray-600 font-normal">0.0%</span>
  ) : (
    `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
  )}
</td>
```

## 4. 툴팁이 포함된 헤더

```tsx
// Simple Tooltip Component
const SimpleTooltip = ({ text, children, align = 'center' }) => {
  let positionClass = 'left-1/2 -translate-x-1/2';
  let arrowClass = 'left-1/2 -translate-x-1/2';

  if (align === 'right') {
    positionClass = 'right-0 translate-x-0';
    arrowClass = 'right-4 translate-x-0';
  } else if (align === 'left') {
    positionClass = 'left-0 translate-x-0';
    arrowClass = 'left-4 translate-x-0';
  }

  return (
    <div className="group relative flex items-center justify-center gap-1 cursor-help">
      {children}
      <div className={`absolute top-full mt-2 hidden group-hover:block w-48 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-[100] text-center border border-white/10 pointer-events-none ${positionClass}`}>
        {text}
        <div className={`absolute bottom-full border-4 border-transparent border-b-gray-900 ${arrowClass}`}></div>
      </div>
    </div>
  );
};

// Usage in Table Header
<th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
  <SimpleTooltip text="설명 텍스트" align="left">
    <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
  </SimpleTooltip>
  <span className="ml-1">Column Name</span>
</th>
```

## 5. 로딩/빈 상태

```tsx
<tbody className="divide-y divide-white/5 text-sm">
  {/* Loading State */}
  {loading ? (
    <tr>
      <td colSpan={11} className="p-8 text-center text-gray-500">
        <i className="fas fa-spinner fa-spin text-2xl text-blue-500/50 mb-3"></i>
        <p className="text-xs">Loading signals...</p>
      </td>
    </tr>
  ) : data.length === 0 ? (
    /* Empty State */
    <tr>
      <td colSpan={11} className="p-8 text-center text-gray-500">
        <p>No data found.</p>
      </td>
    </tr>
  ) : (
    /* Data Rows */
    data.map((row) => (
      <tr key={row.id}>...</tr>
    ))
  )}
</tbody>
```

## 6. 테이블 위/아래 컨트롤

```tsx
{/* Above Table: Title + Filter Tabs */}
<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
  <div className="flex items-center gap-3">
    <h3 className="text-lg font-bold text-white">Table Title</h3>
    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs font-bold rounded-full">
      Count
    </span>
  </div>

  <div className="flex items-center gap-2">
    <button className="px-3 py-1.5 text-xs font-bold rounded-lg bg-rose-600 text-white">
      Tab 1
    </button>
    <button className="px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5 text-gray-400 border border-white/10">
      Tab 2
    </button>
  </div>
</div>

{/* Table */}

{/* Below Table: Footer Info */}
<div className="text-center text-xs text-gray-500 mt-4">
  Last updated: {lastUpdated || '-'}
</div>
```

## 7. 모바일 카드로 변환 (선택사항)

테이블이 모바일에서 카드 형태로 표시되어야 할 때:

```tsx
<div className="md:block hidden">
  {/* Desktop: Table View */}
  <table>...</table>
</div>

<div className="md:hidden space-y-4">
  {/* Mobile: Card View */}
  {data.map((item) => (
    <div key={item.id} className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
      <div className="flex justify-between items-center mb-2">
        <span className="font-bold">{item.name}</span>
        <span className="text-sm text-gray-400">{item.ticker}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-500">Value:</span>
          <span className="ml-2">{item.value}</span>
        </div>
        {/* More fields... */}
      </div>
    </div>
  ))}
</div>
```

## 요약

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 테이블 너비 | 스크롤 가능 (`overflow-x-auto`) | 전체 너비 |
| 최소 너비 | 1000px | - |
| 셀 패딩 | `px-4 py-3` | 동일 |
| 텍스트 크기 | `text-sm` (14px) | 동일 |
| 헤더 텍스트 | `text-[10px]` | 동일 |
