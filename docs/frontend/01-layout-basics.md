# 레이아웃 기본 패턴 (Sidebar, Header, Main)

이 문서는 사이드바, 헤더, 메인 콘텐츠 영역의 기본 레이아웃 반응형 패턴을 다룹니다.

## 1. 전체 레이아웃 구조 (Dashboard Layout)

### 기본 템플릿

```tsx
// app/dashboard/layout.tsx
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-black text-white">
      <Sidebar />
      <Header />

      {/* Main Content Area */}
      <main className="md:pl-64 pl-0 pt-16 min-h-screen transition-all duration-300 overflow-x-hidden">
        <div className="p-4 md:p-8 max-w-[1600px] mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
```

### 핵심 포인트

| 클래스 | 설명 |
|--------|------|
| `md:pl-64 pl-0` | 모바일: 왼쪽 패딩 없음, 데스크탑: 사이드바 너비(256px)만큼 패딩 |
| `pt-16` | 헤더 높이(64px)만큼 상단 패딩 |
| `max-w-[1600px]` | 최대 너비 제한 (대형 화면) |
| `mx-auto` | 중앙 정렬 |

## 2. 사이드바 (Sidebar Component)

### 전체 코드 패턴

```tsx
// components/Sidebar.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

export default function Sidebar() {
  const pathname = usePathname();
  const [isKrExpanded, setIsKrExpanded] = useState(true);

  // Mobile Sidebar State
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // Close mobile sidebar on path change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

  // Listen for mobile sidebar toggle
  useEffect(() => {
    const handleSidebarToggle = () => setIsMobileOpen(prev => !prev);
    window.addEventListener('sidebar-toggle', handleSidebarToggle);
    return () => window.removeEventListener('sidebar-toggle', handleSidebarToggle);
  }, []);

  const isActive = (path: string) => pathname === path;

  return (
    <>
      {/* Mobile Sidebar Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[59] md:hidden transition-opacity"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside className={`
        w-64 border-r border-white/10 bg-[#1c1c1e]
        flex flex-col h-screen fixed left-0 top-0 z-[60]
        transition-transform duration-300
        ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>
        {/* Logo */}
        <Link href="/" className="p-6 flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold">
            M
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
            마켓플로우
          </span>
        </Link>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-2 space-y-1 overflow-y-auto custom-scrollbar">
          {/* Navigation Items */}
          <div className="text-xs font-semibold text-gray-500 mb-2 px-2 mt-4">DASHBOARD</div>

          {/* KR Market Group */}
          <div>
            <button
              onClick={() => setIsKrExpanded(!isKrExpanded)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors text-gray-400 hover:bg-white/5 hover:text-white"
            >
              <div className="flex items-center gap-3">
                <i className="fas fa-chart-line w-5 text-center text-rose-400"></i>
                KR Market
              </div>
              <i className={`fas fa-chevron-down text-xs transition-transform ${isKrExpanded ? 'rotate-180' : ''}`}></i>
            </button>

            {isKrExpanded && (
              <div className="ml-4 mt-1 space-y-0.5 border-l border-white/10 pl-3">
                <Link
                  href="/dashboard/kr"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive('/dashboard/kr')
                      ? 'text-blue-400 bg-blue-500/5'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  ● Overview
                </Link>
                <Link
                  href="/dashboard/kr/vcp"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive('/dashboard/kr/vcp')
                      ? 'text-rose-400 bg-rose-500/5'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  ● VCP 시그널
                </Link>
              </div>
            )}
          </div>
        </nav>

        {/* Footer / User Section */}
        <div className="p-4 border-t border-white/10">
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-left transition-colors">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-blue-500 flex items-center justify-center text-xs font-bold text-white">
              U
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">User Name</div>
              <div className="text-xs text-gray-500 truncate">user@example.com</div>
            </div>
          </button>
        </div>
      </aside>
    </>
  );
}
```

### 사이드바 반응형 핵심 패턴

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 위치 | `fixed` (화면 밖) | `fixed` (왼쪽) |
| 변환 | `translate-x-0` (열림) / `-translate-x-full` (닫힘) | `translate-x-0` (항상 표시) |
| 오버레이 | 표시 (열림 시) | 없음 |
| z-index | `z-[60]` | `z-[60]` |

### Toggle Button Pattern

```tsx
// Header 컴포넌트에서 토글 버튼
<button
  onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
  className="md:hidden text-gray-400 hover:text-white p-2 -ml-2 transition-colors"
>
  <i className="fas fa-bars text-xl"></i>
</button>
```

## 3. 헤더 (Header Component)

### 전체 코드 패턴

```tsx
// components/Header.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="
      h-16 border-b border-white/10 bg-[#000000]/95 backdrop-blur
      supports-[backdrop-filter]:bg-[#000000]/60
      flex items-center justify-between
      px-4 md:px-6
      fixed top-0 md:left-64 left-0 right-0 z-40
      transition-all duration-300
    ">
      {/* Left: Breadcrumb & Mobile Menu */}
      <div className="flex items-center gap-3">
        {/* Mobile Menu Button */}
        <button
          onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
          className="md:hidden text-gray-400 hover:text-white p-2 -ml-2 transition-colors"
        >
          <i className="fas fa-bars text-xl"></i>
        </button>

        {/* Breadcrumbs */}
        <div className="hidden sm:block">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Link href="/" className="hover:text-white transition-colors">
              <i className="fas fa-home"></i>
            </Link>
            <span>/</span>
            <span className="text-white font-medium">Current Page</span>
          </div>
        </div>
        {/* Mobile Title */}
        <div className="sm:hidden text-sm font-bold text-white">Page Title</div>
      </div>

      {/* Right: Search & Actions */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* Search Bar (Desktop Only) */}
        <div className="relative hidden md:block">
          <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i>
          <input
            type="text"
            placeholder="Search..."
            className="w-full md:w-80 bg-[#1c1c1e] border border-white/10 rounded-lg py-2 pl-10 pr-12 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
          />
        </div>

        {/* Mobile Search Icon */}
        <button className="md:hidden w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-400">
          <i className="fas fa-search"></i>
        </button>

        {/* Notifications */}
        <button className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-400 hover:text-white">
          <i className="far fa-bell text-lg"></i>
        </button>
      </div>
    </header>
  );
}
```

### 헤더 반응형 핵심 패턴

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 높이 | `h-16` (64px) | `h-16` (64px) |
| 왼쪽 위치 | `left-0` | `left-64` (사이드바 너비) |
| 패딩 | `px-4` | `px-6` |
| 검색창 | 아이콘만 표시 | 전체 검색창 표시 |
| Breadcrumb | 숨김 | 표시 |

## 4. 메인 콘텐츠 영역

### 기본 패턴

```tsx
<main className="md:pl-64 pl-0 pt-16 min-h-screen transition-all duration-300 overflow-x-hidden">
  <div className="p-4 md:p-8 max-w-[1600px] mx-auto">
    {/* Page Content */}
  </div>
</main>
```

### 반응형 패딩

| 화면 크기 | 패딩 값 |
|----------|---------|
| 모바일 (기본) | `p-4` (16px) |
| 태블릿+ (md:) | `p-8` (32px) |

### 최대 너비 제한

```tsx
<div className="max-w-[1600px] mx-auto">
  {/* 내용이 중앙 정렬되며 최대 1600px까지 확장 */}
</div>
```

## 5. 전체 레이아웃 결합 예시

```tsx
export default function AppLayout() {
  return (
    <div className="min-h-screen bg-black text-white">
      {/* 1. Sidebar - Fixed Position */}
      <aside className="
        fixed left-0 top-0 bottom-0 w-64
        bg-[#1c1c1e] border-r border-white/10
        z-50
        hidden md:flex flex-col
      ">
        {/* Sidebar Content */}
      </aside>

      {/* 2. Header - Fixed Top */}
      <header className="
        fixed top-0 right-0 left-0 md:left-64
        h-16
        bg-black/95 backdrop-blur
        border-b border-white/10
        z-40
      ">
        {/* Header Content */}
      </header>

      {/* 3. Main Content - Scrollable */}
      <main className="
        md:ml-64 ml-0
        mt-16
        min-h-screen
        p-4 md:p-8
      ">
        <div className="max-w-[1600px] mx-auto">
          {/* Page Content */}
        </div>
      </main>
    </div>
  );
}
```

## 요약

| 컴포넌트 | 고정 너비 | 반응형 동작 |
|----------|-----------|-------------|
| Sidebar | `w-64` (256px) | 모바일: 토글, 데스크탑: 항상 표시 |
| Header | `h-16` (64px) | 위치: 모바일 `left-0`, 데스크탑 `left-64` |
| Main | 가변 | 패딩: 모바일 16px, 데스크탑 32px |
