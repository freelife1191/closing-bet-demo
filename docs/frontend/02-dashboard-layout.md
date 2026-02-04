# 대시보드 레이아웃 패턴

이 문서는 대시보드 페이지의 반응형 레이아웃 패턴을 다룹니다.

## 1. 페이지 헤더 영역

### 기본 패턴

```tsx
<div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
  <div>
    {/* Badge */}
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-rose-500/20 bg-rose-500/5 text-xs text-rose-400 font-medium mb-2 md:mb-4">
      <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
      Status Label
    </div>

    {/* Title */}
    <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
      메인 <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">타이틀</span>
    </h2>

    {/* Subtitle */}
    <p className="text-gray-400 text-sm md:text-lg">설명 텍스트</p>
  </div>

  {/* Action Buttons */}
  <div className="flex items-center gap-3 w-full md:w-auto">
    <button className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm">
      Action Button
    </button>
  </div>
</div>
```

### 반응형 텍스트 크기

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 제목 (h2) | `text-3xl` (30px) | `text-5xl` (48px) |
| 부제목 (p) | `text-sm` (14px) | `text-lg` (18px) |
| 배지 | `text-xs` (12px) | `text-xs` (12px) |

## 2. 2열 그리드 레이아웃 (Market Gate)

```tsx
<section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
  {/* Left: Score Card (1 column) */}
  <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <h3 className="text-sm font-bold text-gray-400 mb-4">Score Card</h3>
    {/* Content */}
  </div>

  {/* Right: Sector Grid (3 columns) */}
  <div className="lg:col-span-3 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <h3 className="text-sm font-bold text-gray-400 mb-4">Sector Grid</h3>
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {/* Sector Items */}
    </div>
  </div>
</section>
```

### 그리드 열 분할

| 화면 크기 | 좌측 카드 | 우측 섹터 |
|----------|----------|-----------|
| 모바일 (<1024px) | 전체 너비 | 전체 너비 (아래) |
| 데스크탑 (≥1024px) | 1/4 너비 | 3/4 너비 |

### 섹터 카드 내부 그리드

```tsx
<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
  {/* 모바일: 2열, small: 3열, medium+: 4열 */}
</div>
```

## 3. 4열 KPI 카드 레이아웃

```tsx
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  {/* KPI Card 1 */}
  <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-rose-500/30 transition-all">
    <div className="absolute top-0 right-0 w-20 h-20 bg-rose-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
    <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">
      Metric Label
    </div>
    <div className="text-3xl font-black text-white group-hover:text-rose-400 transition-colors">
      123
    </div>
    <div className="mt-2 text-xs text-gray-500">Description</div>
  </div>

  {/* KPI Card 2, 3, 4... */}
</div>
```

### KPI 카드 반응형

| 화면 크기 | 열 수 |
|----------|------|
| 모바일 (<768px) | 1열 |
| 태블릿+ (≥768px) | 4열 |

## 4. 데이터 카드 그리드 (Market Indices)

```tsx
<div>
  <div className="flex items-center justify-between mb-3">
    <h3 className="text-base font-bold text-white flex items-center gap-2">
      <span className="w-1 h-5 bg-rose-500 rounded-full"></span>
      Section Title
    </h3>
  </div>

  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
    {/* Index Card */}
    <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
      <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">
        INDEX NAME
      </div>
      <div className="flex items-end gap-2">
        <span className="text-xl font-black text-white">
          1,234.56
        </span>
        <span className="text-xs font-bold mb-0.5 text-green-400">
          <i className="fas fa-caret-up mr-0.5"></i>
          +1.2%
        </span>
      </div>
    </div>
  </div>
</div>
```

### 인덱스 카드 반응형

| 화면 크기 | 열 수 |
|----------|------|
| 모바일 | 2열 |
| 태블릿+ (md) | 4열 |

## 5. 대시보드 전체 레이아웃 예시

```tsx
export default function DashboardPage() {
  return (
    <div className="space-y-6 md:space-y-8 pb-20 md:pb-0">
      {/* 1. Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl md:text-5xl font-bold text-white">대시보드</h2>
          <p className="text-gray-400 text-sm md:text-lg">데이터 요약</p>
        </div>
      </div>

      {/* 2. Market Gate Section (1:3 ratio) */}
      <section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
          {/* Score Card */}
        </div>
        <div className="lg:col-span-3 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
          {/* Sector Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {/* Sector Cards */}
          </div>
        </div>
      </section>

      {/* 3. KPI Cards (4 columns) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* 4 KPI Cards */}
      </div>

      {/* 4. Market Indices Section (2 -> 4 columns) */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Index Cards */}
      </section>

      {/* 5. Commodities Section (2 -> 4 columns) */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Commodity Cards */}
      </section>
    </div>
  );
}
```

## 6. 필터/탭 영역

```tsx
<div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
  {/* Left: Title & Count */}
  <div className="flex items-center gap-3">
    <h3 className="text-lg font-bold text-white">Section Title</h3>
    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs font-bold rounded-full">
      Count
    </span>
  </div>

  {/* Right: Tab Buttons */}
  <div className="flex items-center gap-2">
    <button className="px-3 py-1.5 text-xs font-bold rounded-lg bg-rose-600 text-white">
      Tab 1
    </button>
    <button className="px-3 py-1.5 text-xs font-bold rounded-lg bg-white/5 text-gray-400 border border-white/10">
      Tab 2
    </button>
  </div>
</div>
```

## 7. 통계 요약 박스

```tsx
<div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 px-1">
  {/* Label */}
  <span className="text-[10px] text-gray-500 font-medium">
    통계 항목
  </span>

  {/* Value (수치 입력) */}
  {showCustomInput ? (
    <input
      type="number"
      min="1"
      max="1440"
      value={customValue}
      onChange={(e) => setCustomValue(Number(e.target.value))}
      className="w-12 bg-[#1c1c1e] border border-gray-700 rounded text-[10px] px-1.5 py-0.5 text-center text-blue-400"
    />
  ) : (
    <select
      value={value}
      onChange={(e) => setValue(Number(e.target.value))}
      className="bg-transparent border-none text-[10px] font-bold text-gray-400 cursor-pointer appearance-none"
    >
      <option value={1} className="bg-[#1c1c1e]">1분</option>
      <option value={5} className="bg-[#1c1c1e]">5분</option>
      <option value={30} className="bg-[#1c1c1e]">30분</option>
    </select>
  )}

  {/* Unit */}
  <span className="text-[10px] text-gray-500">분 마다</span>
</div>
```

## 요약

| 레이아웃 패턴 | 모바일 (<768px) | 태블릿 (768px-1023px) | 데스크탑 (≥1024px) |
|--------------|-----------------|---------------------|-------------------|
| 페이지 헤더 | 세로 배치 | 가로 배치 | 가로 배치 |
| KPI 카드 | 1열 | 4열 | 4열 |
| Market Gate | 1열+1열 (세로) | 1열+3열 | 1열+3열 |
| 섹터 카드 | 2열 | 3열 | 4열 |
| 인덱스 카드 | 2열 | 4열 | 4열 |
| 필터 영역 | 세로 배치 | 가로 배치 | 가로 배치 |
