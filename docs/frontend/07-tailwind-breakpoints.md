# Tailwind CSS 브레이크포인트 가이드

이 문서는 프로젝트에서 사용하는 Tailwind CSS 브레이크포인트 설정과 반응형 클래스 사용법을 다룹니다.

## 1. 기본 브레이크포인트

```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
      },
    },
  },
  plugins: [],
};

export default config;
```

### 기본 브레이크포인트 값

Tailwind CSS 기본 브레이크포인트를 사용합니다:

| 접두사 | 최소 너비 | 일반적 디바이스 |
|--------|-----------|----------------|
| (없음) | 0px | 모바일 (기본) |
| `sm:` | 640px | 작은 태블릿, 가로 모바일 |
| `md:` | 768px | 태블릿 |
| `lg:` | 1024px | 작은 데스크탑, 노트북 |
| `xl:` | 1280px | 데스크탑 |
| `2xl:` | 1536px | 대형 화면 |

## 2. 모바일 퍼스트 (Mobile First)

Tailwind는 Mobile First 접근 방식을 사용합니다:

```tsx
{/* 기본: 모바일 스타일 */}
<div className="p-4">

  {/* sm: 640px 이상 적용 */}
  <div className="sm:p-6">

    {/* md: 768px 이상 적용 */}
    <div className="md:p-8">

      {/* lg: 1024px 이상 적용 */}
      <div className="lg:p-12">
```

### 예시

```tsx
<div className="
  p-4        /* 모바일: 16px */
  sm:p-6     /* 640px+: 24px */
  md:p-8     /* 768px+: 32px */
  lg:p-12    /* 1024px+: 48px */
">
  Content
</div>
```

## 3. 자주 사용하는 반응형 패턴

### Flex Direction

```tsx
{/* 모바일: 세로, 데스크탑: 가로 */}
<div className="flex flex-col md:flex-row gap-4">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

### Grid Columns

```tsx
{/* 모바일: 1열, 태블릿: 2열, 데스크탑: 4열 */}
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  <div>Item 1</div>
  <div>Item 2</div>
  <div>Item 3</div>
  <div>Item 4</div>
</div>
```

### 숨김/표시

```tsx
{/* 모바일에서만 표시 */}
<div className="block md:hidden">Mobile Only</div>

{/* 데스크탑에서만 표시 */}
<div className="hidden md:block">Desktop Only</div>

{/* 모바일에서 숨김, 태블릿+에서 표시 */}
<div className="hidden sm:block">Tablet+</div>
```

### 너비

```tsx
{/* 모바일: 전체, 태블릿: 절반, 데스크탑: 1/4 */}
<div className="w-full sm:w-1/2 lg:w-1/4">
  Responsive width
</div>
```

### 텍스트 크기

```tsx
<h1 className="
  text-2xl    /* 모바일: 24px */
  md:text-4xl  /* 데스크탑: 36px */
  lg:text-5xl  /* 큰 화면: 48px */
">
  Responsive Title
</h1>
```

### 간격 (Spacing)

```tsx
<div className="
  gap-2       /* 모바일: 8px */
  md:gap-4    /* 데스크탑: 16px */
  lg:gap-8    /* 큰 화면: 32px */
">
  {items}
</div>
```

## 4. 고급 반응형 패턴

### 화면 방향에 따른 스타일

```tsx
{/* 가로 모드에서만 2열 */}
<div className="grid grid-cols-1 landscape:grid-cols-2">
  {items}
</div>
```

### Hover를 브레이크포인트와 결합

```tsx
{/* 데스크탑에서만 호버 효과 */}
<div className="hover:bg-white/5 md:hover:bg-white/10">
  Hover me
</div>
```

### Focus-within (입력창 활성 상태)

```tsx
<div className="ring-1 ring-white/5 focus-within:ring-blue-500/50">
  <input type="text" className="focus:outline-none" />
</div>
```

### Responsive Container Queries (지원 브라우저)

```tsx
<div className="
  [@media(min-width:640px)]:bg-blue-500
  [@media(min-width:768px)]:bg-green-500
">
  Container Query
</div>
```

## 5. 일반적 레이아웃 조합

### Sidebar + Main Content

```tsx
<aside className="
  fixed left-0 top-0 bottom-0 w-64
  hidden md:flex flex-col
  z-50
">
  Sidebar
</aside>

<main className="
  md:ml-64 ml-0
  pt-16
  min-h-screen
">
  Content
</main>
```

### Header + Breadcrumb

```tsx
<header className="
  fixed top-0 left-0 right-0 md:left-64
  h-16
  z-40
">
  {/* Breadcrumb: 모바일에서 숨김 */}
  <nav className="hidden sm:flex items-center gap-2">
    <a href="/">Home</a>
    <span>/</span>
    <span>Current</span>
  </nav>

  {/* Mobile Title: 모바일에서만 표시 */}
  <h1 className="sm:hidden">Page Title</h1>
</header>
```

### Card Grid

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  {cards.map(card => (
    <div key={card.id} className="p-4 rounded-xl border">
      {card.content}
    </div>
  ))}
</div>
```

## 6. 미디어 쿼리와 매핑

Tailwind 클래스를 CSS로 변환:

```css
/* Tailwind: hidden md:block */
@media (min-width: 768px) {
  .md\:block {
    display: block;
  }
}

/* Tailwind: flex-col md:flex-row */
.flex-col {
  flex-direction: column;
}

@media (min-width: 768px) {
  .md\:flex-row {
    flex-direction: row;
  }
}
```

## 7. 사용자 정의 브레이크포인트

필요한 경우 `tailwind.config.ts`에서 커스텀 브레이크포인트 추가:

```typescript
const config: Config = {
  theme: {
    screens: {
      'xs': '480px',      /* 작은 모바일 */
      'sm': '640px',      /* 기본값과 동일 */
      'md': '768px',      /* 기본값과 동일 */
      'lg': '1024px',     /* 기본값과 동일 */
      'xl': '1280px',     /* 기본값과 동일 */
      '2xl': '1536px',    /* 기본값과 동일 */
      // 추가
      'tablet': '640px',
      'laptop': '1024px',
      'desktop': '1280px',
    },
  },
};
```

## 요약

| 패턴 | 클래스 | 효과 |
|------|--------|------|
| 모바일 퍼스트 | `class md:class` | 기본→데스크탑 |
| 방향 전환 | `flex-col md:flex-row` | 세로→가로 |
| 그리드 열 | `grid-cols-1 md:grid-cols-4` | 1열→4열 |
| 숨김/표시 | `hidden md:block` | 숨김→표시 |
| 텍스트 크기 | `text-sm md:text-base` | 작게→크게 |
