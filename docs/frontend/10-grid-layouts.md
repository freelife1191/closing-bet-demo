# 그리드 레이아웃 패턴

이 문서는 CSS Grid를 활용한 반응형 레이아웃 패턴을 다룹니다.

## 1. 기본 그리드 패턴

### 고정 열 개수

```tsx
{/* 1열 (모바일) → 2열 → 4열 */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  {items.map(item => (
    <div key={item.id} className="p-4 rounded-xl border">
      {item.content}
    </div>
  ))}
</div>
```

### 자동 열 개수 (minmax)

```tsx
{/* 최소 250px, 자동으로 열 조정 */}
<div className="
  grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))]
  gap-4
">
  {items.map(item => (
    <div key={item.id}>...</div>
  ))}
</div>
```

### 열 너비 비율

```tsx
{/* 1:3 비율 (25% / 75%) */}
<div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
  <div className="lg:col-span-1">Sidebar (25%)</div>
  <div className="lg:col-span-3">Content (75%)</div>
</div>

{/* 1:1:2 비율 */}
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  <div className="md:col-span-1">25%</div>
  <div className="md:col-span-1">25%</div>
  <div className="md:col-span-2">50%</div>
</div>
```

## 2. 카드 그리드 예시

### KPI 카드 (4열)

```tsx
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  {/* 모바일: 1열, 태블릿+: 4열 */}
  <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <div className="text-[10px] text-gray-500 mb-1">METRIC 1</div>
    <div className="text-3xl font-black">123</div>
  </div>
  <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <div className="text-[10px] text-gray-500 mb-1">METRIC 2</div>
    <div className="text-3xl font-black">456</div>
  </div>
  <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <div className="text-[10px] text-gray-500 mb-1">METRIC 3</div>
    <div className="text-3xl font-black">789</div>
  </div>
  <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <div className="text-[10px] text-gray-500 mb-1">METRIC 4</div>
    <div className="text-3xl font-black">012</div>
  </div>
</div>
```

### 섹터 카드 (2→3→4열)

```tsx
<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
  {/* 모바일: 2열, small: 3열, medium+: 4열 */}
  {sectors.map(sector => (
    <div
      key={sector.name}
      className="p-3 rounded-xl border"
    >
      <div className="text-xs font-bold truncate">{sector.name}</div>
      <div className="text-lg font-black">{sector.value}%</div>
    </div>
  ))}
</div>
```

### 인덱스 카드 (2→4열)

```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
  {/* 모바일: 2열, 태블릿+: 4열 */}
  {indices.map(index => (
    <div key={index.name} className="p-4 rounded-2xl border">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">
        {index.name}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-xl font-black">{index.value}</span>
        <span className="text-xs font-bold text-green-400">
          +{index.change}%
        </span>
      </div>
    </div>
  ))}
</div>
```

## 3. 대시보드 레이아웃

### 2열 분할 (Score + Sectors)

```tsx
<section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
  {/* Left: Score Card (1/4) */}
  <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border">
    <h3 className="text-sm font-bold mb-4">Market Score</h3>
    {/* Score Content */}
  </div>

  {/* Right: Sector Grid (3/4) */}
  <div className="lg:col-span-3 p-6 rounded-2xl bg-[#1c1c1e] border">
    <h3 className="text-sm font-bold mb-4">Sectors</h3>
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {/* Nested Grid for Sectors */}
    </div>
  </div>
</section>
```

## 4. 폼 레이아웃

### 2열 폼

```tsx
<form className="grid grid-cols-1 md:grid-cols-2 gap-4">
  <div>
    <label className="block text-sm font-medium mb-1">First Name</label>
    <input type="text" className="w-full px-3 py-2 rounded-lg" />
  </div>
  <div>
    <label className="block text-sm font-medium mb-1">Last Name</label>
    <input type="text" className="w-full px-3 py-2 rounded-lg" />
  </div>
  {/* Full width submit button */}
  <div className="md:col-span-2">
    <button className="w-full">Submit</button>
  </div>
</form>
```

## 5. 복합 레이아웃

### 헤더 + 콘텐츠 + 사이드바

```tsx
<div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6">
  {/* Main Content (Auto) */}
  <div className="space-y-6">
    <section>...</section>
    <section>...</section>
  </div>

  {/* Sidebar (Fixed 300px) */}
  <aside className="space-y-4">
    <div className="p-4 rounded-xl border">Widget 1</div>
    <div className="p-4 rounded-xl border">Widget 2</div>
  </aside>
</div>
```

## 6. 이미지 갤러리 그리드

### 정사각형 카드

```tsx
<div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
  {images.map(img => (
    <div key={img.id} className="aspect-square rounded-xl overflow-hidden">
      <img src={img.url} alt={img.alt} className="w-full h-full object-cover" />
    </div>
  ))}
</div>
```

### Masonry-style (높이 다름)

```tsx
<div className="columns-2 sm:columns-3 lg:columns-4 gap-4 space-y-4">
  {items.map(item => (
    <div key={item.id} className="break-inside-avoid rounded-xl overflow-hidden">
      <img src={item.image} alt="" className="w-full" />
    </div>
  ))}
</div>
```

## 7. 그리드 간격 (Gap)

```tsx
{/* Tight spacing */}
<div className="grid grid-cols-4 gap-2">...</div>

{/* Normal spacing */}
<div className="grid grid-cols-4 gap-4">...</div>

{/* Loose spacing */}
<div className="grid grid-cols-4 gap-6">...</div>

{/* Custom spacing */}
<div className="grid grid-cols-4 gap-x-4 gap-y-8">
  {/* Horizontal: 4, Vertical: 8 */}
</div>
```

## 8. 그리드 정렬

```tsx
{/* 수직 정렬 */}
<div className="grid grid-cols-2 items-center">
  <div>Item 1</div>
  <div>Item 2 (same height)</div>
</div>

{/* 시작 기준 정렬 */}
<div className="grid grid-cols-2 items-start">
  <div>Tall content</div>
  <div>Short content</div>
</div>

{/* 끝 기준 정렬 */}
<div className="grid grid-cols-2 items-end">
  <div>Content 1</div>
  <div>Content 2</div>
</div>
```

## 9. 반응형 그리드 요약

| 패턴 | 모바일 | 태블릿 | 데스크탑 |
|------|--------|--------|----------|
| 4열 카드 | 1열 | 2열 | 4열 |
| 섹터 카드 | 2열 | 3열 | 4열 |
| 인덱스 카드 | 2열 | 4열 | 4열 |
| KPI 카드 | 1열 | 4열 | 4열 |
| 폼 | 1열 | 2열 | 2열 |
| 갤러리 | 2열 | 3열 | 4열 |

## 10. 일반적 Grid 클래스 조합

```tsx
{/* Mobile: Full width, Tablet+: 50%, Desktop+: 25% */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

{/* Mobile: 2列, Tablet+: 3列, Desktop+: 4列 */}
<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">

{/* Mobile: Full width column span */}
<div className="md:col-span-2 lg:col-span-1">
```
