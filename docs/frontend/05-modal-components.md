# 모달/팝업 반응형 패턴

이 문서는 모달 및 팝업 컴포넌트의 반응형 디자인 패턴을 다룹니다.

## 1. 기본 모달 컴포넌트

### 전체 코드

```tsx
'use client';

import React, { useEffect, useState } from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  type?: 'default' | 'danger' | 'success';
  wide?: boolean;
  maxWidth?: string;
}

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  type = 'default',
  wide = false,
  maxWidth
}: ModalProps) {
  const [show, setShow] = useState(isOpen);

  useEffect(() => {
    if (isOpen) {
      setShow(true);
    } else {
      const timer = setTimeout(() => setShow(false), 200);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // ESC key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!show && !isOpen) return null;

  return (
    <div className={`
      fixed inset-0 z-[100] flex items-center justify-center
      transition-opacity duration-200
      ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}
    `}>
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className={`
        relative bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl
        w-full ${maxWidth || (wide ? 'max-w-4xl' : 'max-w-md')}
        overflow-hidden flex flex-col max-h-[90vh]
        transform transition-all duration-200
        ${isOpen ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'}
      `}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            {type === 'success' && <i className="fas fa-check-circle text-emerald-500"></i>}
            {type === 'danger' && <i className="fas fa-exclamation-circle text-red-500"></i>}
            {title}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10"
          >
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 text-gray-300 leading-relaxed text-sm overflow-y-auto">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="px-6 py-4 bg-[#151517] border-t border-white/5 flex justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
```

### 사용 예시

```tsx
<Modal
  isOpen={isModalOpen}
  onClose={() => setIsModalOpen(false)}
  title="모달 제목"
  type="success"
  footer={
    <>
      <button
        onClick={() => setIsModalOpen(false)}
        className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white"
      >
        취소
      </button>
      <button
        onClick={handleSubmit}
        className="px-4 py-2 rounded-lg text-sm font-bold text-white bg-blue-600 hover:bg-blue-500"
      >
        확인
      </button>
    </>
  }
>
  <p>모달 내용입니다.</p>
</Modal>
```

### 모달 크기 옵션

| prop 값 | 최대 너비 |
|---------|-----------|
| 기본 (없음) | `max-w-md` (448px) |
| `wide={true}` | `max-w-4xl` (896px) |
| `maxWidth="max-w-2xl"` | 672px |
| `maxWidth="max-w-lg"` | 512px |

## 2. 대형 모달 (Chart + Split Layout)

```tsx
<div className="
  fixed inset-0 z-[100] flex items-center justify-center
  p-4 bg-black/80 backdrop-blur-sm
" onClick={onClose}>
  <div
    className="
      bg-[#1c1c1e] border border-white/10 rounded-2xl
      w-full max-w-[95vw] h-[90vh]
      overflow-hidden shadow-2xl
      flex flex-col lg:flex-row
    "
    onClick={e => e.stopPropagation()}
  >
    {/* Left Section (Chart) */}
    <div className="
      flex-none lg:flex-1 flex flex-col
      h-[45vh] lg:h-auto
      border-b lg:border-b-0 lg:border-r border-white/10
    ">
      {/* Chart Header (Mobile Close Button) */}
      <div className="flex justify-between items-center p-4 border-b border-white/5">
        <h3 className="text-lg font-bold text-white">Title</h3>
        <button onClick={onClose} className="lg:hidden text-gray-400 hover:text-white">
          <i className="fas fa-times text-xl"></i>
        </button>
      </div>

      {/* Chart Content */}
      <div className="flex-1 p-2 lg:p-4 lg:min-h-[400px]">
        {/* Chart Component */}
      </div>
    </div>

    {/* Right Section (Panel) */}
    <div className="
      flex-1 lg:flex-none
      w-full lg:w-[500px]
      flex flex-col bg-[#131722] min-h-0
    ">
      {/* Panel Header (Desktop Close Button) */}
      <div className="flex items-center justify-between p-4 border-b border-white/5">
        <span className="text-sm font-bold text-white">Panel Title</span>
        <button onClick={onClose} className="hidden lg:block text-gray-400 hover:text-white">
          <i className="fas fa-times"></i>
        </button>
      </div>

      {/* Panel Content (Scrollable) */}
      <div className="flex-1 overflow-y-auto">
        {/* Content */}
      </div>
    </div>
  </div>
</div>
```

### 반응형 레이아웃

| 요소 | 모바일 | 데스크탑 |
|------|--------|----------|
| 전체 너비 | `95vw` | `95vw` |
| 전체 높이 | `90vh` | `90vh` |
| 레이아웃 방향 | 세로 (`flex-col`) | 가로 (`flex-row`) |
| 좌측 섹션 | `h-[45vh]` | `flex-1` |
| 우측 섹션 | `w-full` | `w-[500px]` |
| 닫기 버튼 | 좌측 상단 | 우측 상단 |

## 3. 바텀시트 (모바일 전용)

```tsx
<div className="
  fixed inset-x-0 bottom-0 z-[100]
  md:hidden
  bg-[#1c1c1e] border-t border-white/10 rounded-t-3xl
  p-6
  transform transition-transform duration-300
  ${isOpen ? 'translate-y-0' : 'translate-y-full'}
">
  {/* Handle for drag indicator */}
  <div className="w-12 h-1 bg-white/20 rounded-full mx-auto mb-4" />

  {/* Content */}
  <div className="max-h-[70vh] overflow-y-auto">
    {children}
  </div>
</div>
```

## 4. 드롭다운 메뉴

```tsx
<div className="relative">
  {/* Trigger Button */}
  <button
    onClick={() => setIsOpen(!isOpen)}
    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-sm"
  >
    Menu <i className={`fas fa-chevron-${isOpen ? 'up' : 'down'} ml-1`}></i>
  </button>

  {/* Dropdown */}
  {isOpen && (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-10"
        onClick={() => setIsOpen(false)}
      />

      {/* Menu */}
      <div className="
        absolute right-0 top-full mt-2
        w-48 bg-[#1c1c1e] border border-white/10
        rounded-xl shadow-2xl z-20 py-1
        max-h-60 overflow-y-auto
      ">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              onSelect(item);
              setIsOpen(false);
            }}
            className="
              w-full text-left px-4 py-2 text-sm
              hover:bg-white/5 transition-colors
              text-gray-300 hover:text-white
            "
          >
            {item.label}
          </button>
        ))}
      </div>
    </>
  )}
</div>
```

## 5. Confirm Dialog (간단 모달)

```tsx
<div className="
  fixed inset-0 z-[100] flex items-center justify-center
  bg-black/60 backdrop-blur-sm p-4
">
  <div className="
    bg-[#1c1c1e] border border-white/10 rounded-2xl
    w-full max-w-sm p-6
  ">
    {/* Icon */}
    <div className="w-12 h-12 rounded-full bg-rose-500/20 flex items-center justify-center mx-auto mb-4">
      <i className="fas fa-exclamation-triangle text-rose-500 text-xl"></i>
    </div>

    {/* Title */}
    <h3 className="text-lg font-bold text-white text-center mb-2">
      확인하시겠습니까?
    </h3>

    {/* Message */}
    <p className="text-sm text-gray-400 text-center mb-6">
      이 작업은 되돌릴 수 없습니다.
    </p>

    {/* Buttons */}
    <div className="flex gap-3">
      <button
        onClick={onCancel}
        className="flex-1 px-4 py-2 rounded-lg text-sm text-gray-400 bg-white/5 hover:bg-white/10"
      >
        취소
      </button>
      <button
        onClick={onConfirm}
        className="flex-1 px-4 py-2 rounded-lg text-sm font-bold text-white bg-rose-600 hover:bg-rose-500"
      >
        확인
      </button>
    </div>
  </div>
</div>
```

## 6. Tooltip (CSS only)

```tsx
<div className="group relative inline-block">
  {/* Trigger */}
  <button className="p-2 hover:bg-white/10 rounded-lg">
    <i className="fas fa-info-circle text-gray-400"></i>
  </button>

  {/* Tooltip */}
  <div className="
    absolute bottom-full left-1/2 -translate-x-1/2 mb-2
    w-48 px-3 py-2
    bg-gray-900 text-gray-200 text-[11px] font-medium
    rounded-lg
    opacity-0 group-hover:opacity-100
    transition-opacity
    pointer-events-none z-50
    border border-white/10 shadow-xl
    text-center
  ">
    Tooltip content here
    <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
  </div>
</div>
```

## 요약

| 컴포넌트 | 모바일 | 데스크탑 |
|----------|--------|----------|
| 기본 모달 | 전체 화면 `w-full` | `max-w-md` |
| 대형 모달 | 세로 분할 | 가로 분할 |
| 바텀시트 | 표시 | 숨김 (`md:hidden`) |
| 드롭다운 | 전체 너비 | 고정 너비 `w-48` |
| 툴팁 | 상대 위치 | 동일 |
