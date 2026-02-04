# 모바일 전용 패턴 (Overlay, Hamburger, Touch)

이 문서는 모바일 환경에서 특별히 고려해야 하는 UI 패턴을 다룹니다.

## 1. 모바일 사이드바 오버레이

### 전체 패턴

```tsx
'use client';

import { useState, useEffect } from 'react';

export default function MobileSidebar() {
  const [isOpen, setIsOpen] = useState(false);

  // Close on route change
  useEffect(() => {
    const handleClose = () => setIsOpen(false);
    window.addEventListener('sidebar-toggle', handleClose);
    return () => window.removeEventListener('sidebar-toggle', handleClose);
  }, []);

  return (
    <>
      {/* 1. Backdrop Overlay (Mobile Only) */}
      {isOpen && (
        <div
          className="
            fixed inset-0
            bg-black/60 backdrop-blur-sm
            z-[59] md:hidden
            transition-opacity
          "
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* 2. Sidebar (Slide Animation) */}
      <aside className={`
        w-64 border-r border-white/10 bg-[#1c1c1e]
        flex flex-col h-screen fixed left-0 top-0 z-[60]
        transition-transform duration-300
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>
        {/* Sidebar Content */}
      </aside>
    </>
  );
}
```

### 핵심 클래스

| 클래스 | 설명 |
|--------|------|
| `fixed inset-0` | 전체 화면 덮기 |
| `bg-black/60 backdrop-blur-sm` | 반투명 배경 + 블러 |
| `z-[59]` | 사이드바(z-[60])보다 아래 |
| `md:hidden` | 데스크탑에서 숨김 |
| `transition-opacity` | 페이드 효과 |

## 2. 햄버거 메뉴 버튼

```tsx
{/* Trigger Button */}
<button
  onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
  className="
    md:hidden
    text-gray-400 hover:text-white
    p-2 -ml-2
    transition-colors
  "
>
  <i className="fas fa-bars text-xl"></i>
</button>
```

### 이벤트 기반 토글

```tsx
// 보내는 쪽 (Header)
window.dispatchEvent(new Event('sidebar-toggle'));

// 받는 쪽 (Sidebar)
useEffect(() => {
  const handleToggle = () => setIsOpen(prev => !prev);
  window.addEventListener('sidebar-toggle', handleToggle);
  return () => window.removeEventListener('sidebar-toggle', handleToggle);
}, []);
```

## 3. 모바일 전용 토스트/알림

```tsx
interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info';
  onClose: () => void;
}

export default function MobileToast({ message, type, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const bgClass = {
    success: 'bg-green-600',
    error: 'bg-red-600',
    info: 'bg-blue-600'
  }[type];

  return (
    <div className="
      fixed bottom-20 left-4 right-4
      md:bottom-8 md:left-auto md:right-8 md:w-80
      z-[150]
      animate-slide-up
    ">
      <div className={`${bgClass} text-white px-4 py-3 rounded-xl shadow-lg`}>
        <p className="text-sm">{message}</p>
      </div>
    </div>
  );
}
```

### 모바일 vs 데스크탑 위치

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 위치 | `bottom-20 left-4 right-4` | `bottom-8 right-8` |
| 너비 | 전체 (왼쪽 여백 16px) | 고정 `w-80` (320px) |

## 4. 터치 영역 최소 크기

### 버튼/링크

```tsx
{/* 최소 44x44px (Apple HIG 권장) */}
<button className="
  w-11 h-11
  min-w-[44px] min-h-[44px]
  flex items-center justify-center
  rounded-lg
">
  <i className="fas fa-search"></i>
</button>
```

### 아이콘 버튼 크기 가이드

| 크기 | 클래스 | 용도 |
|------|--------|------|
| 작음 | `w-8 h-8` (32px) | 좁은 공간 |
| 기본 | `w-11 h-11` (44px) | 터치 권장 |
| 큼 | `w-14 h-14` (56px) | 주요 액션 |

## 5. 모바일 네비게이션 바 (Bottom)

```tsx
<div className="
  fixed bottom-0 left-0 right-0
  bg-[#1c1c1e] border-t border-white/10
  flex justify-around items-center
  h-16 pb-safe
  md:hidden
  z-50
">
  {navItems.map((item) => (
    <button
      key={item.id}
      className={`
        flex flex-col items-center justify-center
        w-full h-full
        ${isActive(item.id) ? 'text-blue-500' : 'text-gray-400'}
      `}
    >
      <i className={`fas fa-${item.icon} text-xl`}></i>
      <span className="text-[10px] mt-1">{item.label}</span>
    </button>
  ))}
</div>
```

### iOS Safe Area 지원

```css
/* globals.css */
@supports (padding: max(0px)) {
  .pb-safe {
    padding-bottom: max(1rem, env(safe-area-inset-bottom));
  }
}
```

## 6. 모바일 드래그 인디케이터

```tsx
<div className="
  md:hidden
  w-12 h-1 bg-white/20 rounded-full mx-auto mb-4
">
  {/* 바텀시트에서 드래그 가능 표시 */}
</div>
```

## 7. 스크롤 컨테이너 (가로 스크롤)

```tsx
{/* Suggestion Chips - Horizontal Scroll */}
<div className="
  flex gap-2 overflow-x-auto
  custom-scrollbar-hide
  snap-x snap-mandatory
  -webkit-overflow-scrolling: touch
">
  {suggestions.map((s, i) => (
    <button
      key={i}
      className="
        flex-shrink-0 px-4 py-2
        bg-[#2c2c2e] rounded-full
        text-sm text-gray-300
        snap-start
      "
    >
      {s}
    </button>
  ))}
</div>
```

### 부드러운 스크롤 (momentum scrolling)

```css
/* globals.css */
-webkit-overflow-scrolling: touch;
scroll-behavior: smooth;
```

## 8. 모바일 입력창 (Auto-focus 문제 해결)

```tsx
const textareaRef = useRef<HTMLTextAreaElement>(null);

const handleSend = () => {
  // IME 조합 강제 종료 (한글 입력 문제 해결)
  if (textareaRef.current) {
    textareaRef.current.blur();  // 키보드 내리기
    textareaRef.current.value = '';  // 값 초기화
  }
  setInput('');
  // ... 전송 로직
};

<textarea
  ref={textareaRef}
  value={input}
  onChange={(e) => setInput(e.target.value)}
  className="
    flex-1 bg-transparent text-white text-sm
    resize-none focus:outline-none
    py-1.5 leading-relaxed
    max-h-[100px] min-h-[36px]
  "
/>
```

## 9. Pull-to-Refresh 영역 확보

```tsx
<main className="
  pb-20 md:pb-0
  min-h-screen
">
  {/* 모바일에서 하단 패딩 확보로 콘텐츠 가려짐 방지 */}
</main>
```

## 10. 모바일 테이블 (카드로 변환)

```tsx
{/* Desktop: Table */}
<div className="hidden md:block">
  <table>...</table>
</div>

{/* Mobile: Cards */}
<div className="md:hidden space-y-4">
  {data.map((item) => (
    <div key={item.id} className="
      p-4 rounded-2xl bg-[#1c1c1e] border border-white/10
    ">
      <div className="flex justify-between items-center mb-2">
        <span className="font-bold">{item.name}</span>
        <span className="text-sm text-gray-400">{item.value}</span>
      </div>
    </div>
  ))}
</div>
```

## 11. 모바일 최적화 툴팁

```tsx
{/* 길게 누르기 (Long Press) */}
<div
  className="relative"
  onContextMenu={(e) => {
    e.preventDefault();
    setShowTooltip(true);
  }}
>
  <button>Press & Hold</button>

  {/* Tooltip - Positioned for touch */}
  {showTooltip && (
    <div className="
      absolute bottom-full left-0 mb-2
      w-48 px-3 py-2
      bg-gray-900 text-white text-xs rounded
      z-50
    ">
      Tooltip content
    </div>
  )}
</div>
```

## 요약

| 패턴 | 주요 클래스 |
|------|-------------|
| 오버레이 | `fixed inset-0 bg-black/60 backdrop-blur-sm` |
| 햄버거 버튼 | `md:hidden p-2 min-w-[44px]` |
| 바텀 네비게이션 | `fixed bottom-0 md:hidden` |
| 터치 영역 | `min-w-[44px] min-h-[44px]` |
| 가로 스크롤 | `overflow-x-auto snap-x -webkit-overflow-scrolling:touch` |
| 입력창 | `ref + blur()` |
| 하단 여유 | `pb-20 md:pb-0` |
