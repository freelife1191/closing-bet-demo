# 타이포그래피 반응형 패턴

이 문서는 텍스트와 타이포그래피의 반응형 디자인 패턴을 다룹니다.

## 1. 텍스트 크기 반응형

### 헤딩 (Heading)

```tsx
{/* Page Title */}
<h1 className="
  text-3xl        /* Mobile: 30px */
  md:text-4xl     /* Tablet: 36px */
  lg:text-5xl     /* Desktop: 48px */
  font-bold tracking-tighter
">
  페이지 제목
</h1>

{/* Section Title */}
<h2 className="
  text-2xl        /* Mobile: 24px */
  md:text-3xl     /* Tablet+: 30px */
  font-bold
">
  섹션 제목
</h2>

{/* Subsection Title */}
<h3 className="
  text-lg         /* Mobile: 18px */
  md:text-xl      /* Tablet+: 20px */
  font-bold
">
  소섹션 제목
</h3>
```

### 본문 (Body Text)

```tsx
<p className="
  text-sm         /* Mobile: 14px */
  md:text-base    /* Tablet+: 16px */
  text-gray-400 leading-relaxed
">
  본문 텍스트입니다.
</p>
```

### 캡션/라벨

```tsx
<span className="
  text-[10px]     /* 10px - 모바일에서도 고정 */
  text-xs         /* 12px */
  text-gray-500
">
  캡션 텍스트
</span>
```

## 2. 텍스트 줄바꿈 제어

### Truncate (말줄임표)

```tsx
{/* 한 줄 자름 */}
<div className="truncate">
  아주 긴 텍스트입니다...
</div>

{/* 2줄 자름 */}
<div className="line-clamp-2">
  아주 긴 텍스트입니다.
  두 번째 줄입니다.
  세 번째 줄은 보이지 않습니다...
</div>

{/* 3줄 자름 */}
<div className="line-clamp-3">
  긴 텍스트 내용...
</div>

{/* 줄바꿈 방지 */}
<div className="whitespace-nowrap">
  줄바꿈하지 않는 텍스트
</div>
```

### CSS 설정 (필요시)

```css
/* globals.css */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

## 3. 텍스트 정렬 반응형

```tsx
{/* 모바일: 중앙, 데스크탑: 좌측 */}
<h1 className="
  text-center md:text-left
">
  제목
</h1>

{/* 모바일: 좌측, 데스크탑: 중앙 */}
<div className="
  text-left md:text-center
">
  내용
</div>

{/* 숫자 정렬 (항상 우측) */}
<span className="text-right block">
  1,234.56
</span>
```

## 4. 텍스트 색상 & 상태

```tsx
{/* Primary Text */}
<p className="text-white">주요 텍스트</p>

{/* Secondary Text */}
<p className="text-gray-400">2차 텍스트</p>

{/* Tertiary Text */}
<p className="text-gray-500">3차 텍스트</p>

{/* Link Text */}
<a className="text-blue-400 hover:text-blue-300 transition-colors">
  링크
</a>

{/* Number Colors (Positive/Negative) */}
<span className={value >= 0 ? 'text-green-400' : 'text-red-400'}>
  {value >= 0 ? '+' : ''}{value}%
</span>
```

## 5. 텍스트 강조

```tsx
{/* Bold */}
<strong className="font-bold">굵은 텍스트</strong>

{/* Gradient Text */}
<span className="
  text-transparent bg-clip-text
  bg-gradient-to-r from-blue-400 to-purple-400
">
  그라데이션 텍스트
</span>

{/* Highlight */}
<span className="bg-blue-500/20 text-blue-400 px-1 rounded">
  하이라이트
</span>

{/* Monospace (Numbers) */}
<span className="font-mono">
  123.45
</span>
```

## 6. 아이콘 + 텍스트

```tsx
{/* Icon + Text Horizontal */}
<div className="flex items-center gap-2">
  <i className="fas fa-chart-line text-rose-400"></i>
  <span>텍스트</span>
</div>

{/* Icon + Text Vertical (Mobile) */}
<div className="flex flex-col items-center gap-1 sm:hidden">
  <i className="fas fa-home text-xl"></i>
  <span className="text-[10px]">홈</span>
</div>
```

## 7. 뱃지/태그

```tsx
{/* Status Badge */}
<span className="
  inline-flex items-center gap-2
  px-3 py-1 rounded-full border
  text-xs font-bold
  bg-rose-500/20 text-rose-400 border-rose-500/20
">
  <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
  Status
</span>

{/* Count Badge */}
<span className="
  px-2 py-0.5 rounded-full
  bg-blue-500/20 text-blue-400 text-xs font-bold
">
  123
</span>

{/* Label Badge */}
<span className="
  px-1.5 py-0.5 rounded
  bg-amber-500/10 text-amber-500
  text-[10px] font-bold border border-amber-500/20
">
  Win Rate
</span>
```

## 8. 애니메이션 텍스트

```tsx
{/* Pulse Animation */}
<span className="
  text-emerald-500 font-bold
  animate-pulse
">
  진행 중
</span>

{/* Ping Animation */}
<span className="
  inline-flex relative
">
  <span className="w-2 h-2 rounded-full bg-blue-500 absolute animate-ping"></span>
  <span className="w-2 h-2 rounded-full bg-blue-500 relative"></span>
</span>
```

## 9. 텍스트 유틸리티

```tsx
{/* Uppercase */}
<div className="uppercase text-xs tracking-widest">
  UPPERCASE
</div>

{/* Tracking (Letter Spacing) */}
<div className="
  tracking-tighter    {/* -0.05em */}
  tracking-tight      {/* -0.025em */}
  tracking-normal     {/* 0 */}
  tracking-wide       {/* 0.025em */}
  tracking-wider      {/* 0.05em */}
  tracking-widest     {/* 0.1em */}
">
  Letter Spacing
</div>

{/* Leading (Line Height) */}
<p className="
  leading-tight      {/* 1.25 */}
  leading-snug       {/* 1.375 */}
  leading-normal     {/* 1.5 */}
  leading-relaxed    {/* 1.625 */}
  leading-loose      {/* 2 */}
">
  Line Height
</p>
```

## 10. 한글 텍스트 최적화

```tsx
{/* 한글 줄바꿈 최적화 */}
<p className="
  break-keep       /* 단어 단위 줄바꿈 (한글 권장) */
  break-words      /* 영어 단어 줄바꿈 */
">
  한글 텍스트는 줄바꿈 시 단어가 깨지지 않도록 하는 것이 좋습니다.
</p>
```

## 11. 텍스트 요약

| 용도 | 모바일 | 데스크탑 |
|------|--------|----------|
| 페이지 제목 (h1) | `text-3xl` (30px) | `text-5xl` (48px) |
| 섹션 제목 (h2) | `text-2xl` (24px) | `text-3xl` (30px) |
| 소제목 (h3) | `text-lg` (18px) | `text-xl` (20px) |
| 본문 (p) | `text-sm` (14px) | `text-base` (16px) |
| 캡션 | `text-[10px]` | `text-xs` (12px) |
| 작은 텍스트 | `text-[10px]` | `text-[10px]` |

### 텍스트 크기 매핑

| Tailwind 클래스 | 픽셀 값 |
|-----------------|---------|
| `text-[10px]` | 10px |
| `text-xs` | 12px |
| `text-sm` | 14px |
| `text-base` | 16px |
| `text-lg` | 18px |
| `text-xl` | 20px |
| `text-2xl` | 24px |
| `text-3xl` | 30px |
| `text-4xl` | 36px |
| `text-5xl` | 48px |
