# 카드 컴포넌트 반응형 패턴

이 문서는 카드 컴포넌트의 반응형 디자인 패턴을 다룹니다.

## 1. 기본 카드 패턴

```tsx
<div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-rose-500/30 transition-all">
  {/* Optional: Background Glow Effect */}
  <div className="absolute top-0 right-0 w-20 h-20 bg-rose-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>

  {/* Card Content */}
  <div className="relative z-10">
    <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">
      Label
    </div>
    <div className="text-3xl font-black text-white">
      Value
    </div>
    <div className="mt-2 text-xs text-gray-500">
      Description
    </div>
  </div>
</div>
```

### 기본 카드 클래스

| 클래스 | 설명 |
|--------|------|
| `p-5` | 내부 패딩 20px |
| `rounded-2xl` | 모서리 라운드 16px |
| `bg-[#1c1c1e]` | 배경색 (다크 테마) |
| `border border-white/10` | 테두리 |
| `group` | 호버 효과 그룹화 |
| `hover:border-rose-500/30` | 호버 시 테두리 색상 |

## 2. 통계 카드 (KPI Card)

### 기본형

```tsx
<div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-rose-500/30 transition-all">
  {/* Background Glow */}
  <div className="absolute top-0 right-0 w-20 h-20 bg-rose-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>

  {/* Header */}
  <div className="flex items-center gap-2 mb-1">
    <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
      Metric Name
    </div>
    {/* Optional: Tooltip Icon */}
    <span className="text-gray-600 cursor-help">
      <i className="fas fa-question-circle text-[10px]"></i>
    </span>
  </div>

  {/* Main Value */}
  <div className="text-3xl font-black text-white group-hover:text-rose-400 transition-colors">
    1,234
  </div>

  {/* Description */}
  <div className="mt-2 text-xs text-gray-500">
    Additional info
  </div>
</div>
```

### 승률/성과 카드

```tsx
<div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-amber-500/30 transition-all">
  <div className="absolute top-0 right-0 w-20 h-20 bg-amber-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>

  {/* Header with Badge */}
  <div className="flex justify-between items-start">
    <div className="flex items-center gap-2 mb-1">
      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">
        Strategy Name
      </div>
    </div>
    <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 text-[10px] font-bold border border-amber-500/20">
      Win Rate
    </span>
  </div>

  {/* Value + Additional Info */}
  <div className="flex items-baseline gap-2">
    <span className="text-3xl font-black text-white group-hover:text-amber-400 transition-colors">
      75<span className="text-base text-gray-600">%</span>
    </span>
    <span className="text-xs font-bold text-green-400">
      Avg. +5.2%
    </span>
  </div>

  {/* Footer Info */}
  <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
    <span>10 trades</span>
    <i className="fas fa-check-circle text-emerald-500"></i>
  </div>
</div>
```

## 3. 인덱스/가격 카드

```tsx
<div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
  {/* Label */}
  <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">
    KOSPI
  </div>

  {/* Value + Change */}
  <div className="flex items-end gap-2">
    <span className="text-xl font-black text-white">
      2,543.12
    </span>
    <span className="text-xs font-bold mb-0.5 text-green-400">
      <i className="fas fa-caret-up mr-0.5"></i>
      +1.2%
    </span>
  </div>
</div>
```

### 색상 변화 (양수/음수)

```tsx
<span className={`text-xs font-bold mb-0.5 ${
  change >= 0 ? 'text-green-400' : 'text-blue-400'
}`}>
  <i className={`fas fa-caret-${change >= 0 ? 'up' : 'down'} mr-0.5`}></i>
  {change >= 0 ? '+' : ''}{change.toFixed(1)}%
</span>
```

## 4. 점수 원형 카드 (Score Circle)

```tsx
<div className="p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group">
  <h3 className="text-sm font-bold text-gray-400 mb-4">
    Market Score
  </h3>

  {/* SVG Circle Progress */}
  <div className="flex flex-col items-center justify-center py-2">
    <div className="relative w-32 h-32 flex items-center justify-center">
      <svg className="w-full h-full -rotate-90">
        {/* Background Circle */}
        <circle
          cx="64" cy="64" r="58"
          stroke="currentColor" strokeWidth="8" fill="transparent"
          className="text-white/5"
        />
        {/* Progress Circle */}
        <circle
          cx="64" cy="64" r="58"
          stroke="currentColor" strokeWidth="8" fill="transparent"
          strokeDasharray="364.4"
          strokeDashoffset={364.4 - (364.4 * score) / 100}
          className={score >= 70 ? 'text-green-500' : score >= 40 ? 'text-yellow-500' : 'text-red-500'}
          style={{ transition: 'all 1s ease-out' }}
        />
      </svg>

      {/* Center Value */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-3xl font-black ${
          score >= 70 ? 'text-green-500' : score >= 40 ? 'text-yellow-500' : 'text-red-500'
        }`}>
          {score}
        </span>
        <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">
          Score
        </span>
      </div>
    </div>

    {/* Status Badge */}
    <div className={`mt-4 px-4 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-bold ${
      score >= 70 ? 'text-green-500' : score >= 40 ? 'text-yellow-500' : 'text-red-500'
    }`}>
      {score >= 70 ? 'Bullish' : score >= 40 ? 'Neutral' : 'Bearish'}
    </div>
  </div>
</div>
```

## 5. 섹터 카드 (Clickable)

```tsx
<div
  className={`
    p-3 rounded-xl border transition-all hover:scale-105 cursor-pointer
    ${getSectorColorClass(signal)}
  `}
>
  <div className="text-xs font-bold truncate">
    Sector Name
  </div>
  <div className={`text-lg font-black ${
    change >= 0 ? 'text-rose-400' : 'text-blue-400'
  }`}>
    {change >= 0 ? '+' : ''}{change.toFixed(2)}%
  </div>
</div>
```

### 색상 함수

```tsx
const getSectorColor = (signal: string) => {
  if (signal === 'bullish') return 'bg-green-500/20 text-green-400 border-green-500/30';
  if (signal === 'bearish') return 'bg-red-500/20 text-red-400 border-red-500/30';
  return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
};
```

## 6. 액션 버튼 카드

```tsx
<button
  onClick={handleAction}
  disabled={loading}
  className="
    p-5 rounded-2xl bg-[#1c1c1e] border border-white/10
    flex flex-col justify-center items-center gap-2
    cursor-pointer hover:bg-white/5 transition-all group
    disabled:opacity-50
  "
>
  {/* Icon Container */}
  <div className={`
    w-10 h-10 rounded-full bg-white/5
    flex items-center justify-center text-white
    group-hover:rotate-180 transition-transform duration-500
    ${loading ? 'animate-spin' : ''}
  `}>
    <i className="fas fa-sync-alt"></i>
  </div>

  {/* Text */}
  <div className="text-center">
    <div className="text-sm font-bold text-white">Refresh Data</div>
    <div className="text-[10px] text-gray-500">Last: 10:30 AM</div>
  </div>
</button>
```

## 7. 모바일 카드 그리드 예시

```tsx
export default function CardGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* 모바일: 1열, md+: 4열 */}
      {cards.map((card) => (
        <div key={card.id} className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10">
          {/* Card Content */}
        </div>
      ))}
    </div>
  );
}
```

## 요약

| 카드 타입 | 크기 | 주요 클래스 |
|-----------|------|-------------|
| 기본 카드 | 가변 | `p-5 rounded-2xl` |
| 인덱스 카드 | 작음 | `p-4 rounded-2xl` |
| 점수 카드 | 큼 | `p-6 rounded-2xl` (원형 그래프 포함) |
| 섹터 카드 | 작음 | `p-3 rounded-xl` |
| 버튼 카드 | 중간 | `p-5 rounded-2xl` (클릭 가능) |

### 반응형 너비

| 화면 크기 | 열 수 |
|----------|------|
| 모바일 (<768px) | 1열 (`grid-cols-1`) |
| 태블릿+ (≥768px) | 4열 (`md:grid-cols-4`) |
