# Modal Components - Responsive Design Reference

Reference documentation for responsive patterns in modal components (Modal base, PaperTradingModal, SettingsModal).

## Contents

1. [Modal Base Component](#1-modal-base-component)
2. [PaperTradingModal - Responsive Patterns](#2-papertradingmodal-responsive-patterns)
3. [SettingsModal - Responsive Patterns](#3-settingsmodal-responsive-patterns)
4. [Full-Screen vs Centered Modals](#4-full-screen-vs-centered-modals)
5. [Common Responsive Utilities](#5-common-responsive-utilities)

---

## 1. Modal Base Component

**Source**: `frontend/src/app/components/Modal.tsx`

### Basic Modal Structure

```tsx
// Lines 29-35: Container with backdrop
<div className={`fixed inset-0 z-[100] flex items-center justify-center
  transition-opacity duration-200
  ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>

  {/* Backdrop */}
  <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

  {/* Modal Content */}
  <div className={`relative bg-[#1c1c1e] border border-white/10 rounded-2xl
    shadow-2xl w-full ${maxWidth ? maxWidth : (wide ? 'max-w-4xl' : 'max-w-md')}
    overflow-hidden flex flex-col max-h-[90vh]
    transform transition-all duration-200
    ${isOpen ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'}`}>
```

### Responsive Key Points

| Aspect | Pattern | Notes |
|--------|---------|-------|
| **Positioning** | `fixed inset-0 flex items-center justify-center` | Always centered |
| **Max Width** | `max-w-md` (default) or `max-w-4xl` (wide) | Via `wide` prop or `maxWidth` prop |
| **Max Height** | `max-h-[90vh]` | Prevents overflow on small screens |
| **Z-Index** | `z-[100]` | Above all content |
| **Animations** | Scale + translate transitions | Smooth open/close |

### Header/Body/Footer Structure

```tsx
// Lines 36-58: Header, Body, Footer
{/* Header */}
<div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
  <h3 className="text-lg font-bold text-white flex items-center gap-2">
    {title}
  </h3>
  <button onClick={onClose} className="text-gray-400 hover:text-white
    transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10">
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
```

**Key Patterns**:
- Fixed padding (`px-6 py-4`) - no responsive breakpoints
- Body uses `overflow-y-auto` for scrollable content
- Footer buttons aligned with `justify-end`

---

## 2. PaperTradingModal - Responsive Patterns

**Source**: `frontend/src/app/components/PaperTradingModal.tsx`

### Full-Screen Modal Layout

```tsx
// Lines 311-313: Full-width modal with top positioning
<div className="fixed inset-0 z-[100] flex items-start justify-center p-4 pt-32">
  <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
  <div className="relative bg-[#1c1c1e] w-full max-w-[90vw] max-h-[85vh]
    rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden
    animate-in fade-in zoom-in-95 duration-200">
```

**Responsive Breakdown**:
- **Mobile**: Full width `w-full`, max 90vw, starts from top (`pt-32`)
- **Container padding**: `p-4` on all sides
- **Height**: `max-h-[85vh]` to prevent viewport overflow

### Header - Responsive Flex Direction

```tsx
// Lines 316-365: Header with flex-direction change
<div className="flex flex-col md:flex-row md:items-center justify-between
  p-4 md:p-5 border-b border-white/10 bg-[#252529] gap-4 md:gap-0">

  {/* Title Section */}
  <div className="flex items-center gap-3">
    <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br
      from-indigo-500 to-purple-600 flex items-center justify-center
      shadow-lg shadow-indigo-500/20 flex-shrink-0">
      <i className="fas fa-chart-line text-white text-lg md:text-xl"></i>
    </div>
    <div>
      <h2 className="text-lg md:text-xl font-bold text-white whitespace-nowrap">
        모의투자 포트폴리오
      </h2>
      <div className="text-xs text-slate-400 font-medium">Paper Trading Account</div>
    </div>

    {/* Mobile Close Button */}
    <button onClick={onClose} className="ml-auto md:hidden w-8 h-8 rounded-full
      bg-white/5 flex items-center justify-center text-gray-400 hover:text-white">
      <i className="fas fa-times"></i>
    </button>
  </div>

  {/* Asset Display - Responsive */}
  <div className="flex flex-col md:flex-row md:items-center gap-3 w-full md:w-auto">
    {portfolio && (
      <div className="flex flex-row items-center justify-between md:justify-start
        gap-4 px-4 py-3 md:py-2 bg-black/20 rounded-xl border border-white/5
        md:mr-4 w-full md:w-auto">
        {/* Asset values */}
      </div>
    )}

    {/* Desktop Close Button */}
    <button onClick={onClose} className="hidden md:flex w-8 h-8 rounded-full
      bg-white/5 hover:bg-white/10 items-center justify-center text-gray-400
      hover:text-white transition-colors">
      <i className="fas fa-times"></i>
    </button>
  </div>
</div>
```

**Responsive Changes**:

| Element | Mobile (< 768px) | Desktop (>= 768px) |
|---------|------------------|-------------------|
| **Flex Direction** | `flex-col` | `md:flex-row` |
| **Items Alignment** | Default | `md:items-center` |
| **Gap** | `gap-4` | `md:gap-0` |
| **Padding** | `p-4` | `md:p-5` |
| **Icon Size** | `w-10 h-10` | `md:w-12 md:h-12` |
| **Title Size** | `text-lg` | `md:text-xl` |
| **Close Button** | Inside title section | Separate, right side |
| **Asset Card** | `w-full` full width | `md:w-auto` auto width |

### Horizontal Scrollable Tabs

```tsx
// Lines 368-388: Overflow-x scrollable tabs
<div className="flex border-b border-white/10 bg-[#1c1c1e] overflow-x-auto no-scrollbar">
  {[
    { id: 'overview', label: '자산 개요', icon: 'fa-wallet' },
    { id: 'holdings', label: '보유 종목', icon: 'fa-list' },
    { id: 'chart', label: '수익 차트', icon: 'fa-chart-area' },
    { id: 'history', label: '거래 내역', icon: 'fa-history' }
  ].map(tab => (
    <button
      key={tab.id}
      onClick={() => setActiveTab(tab.id as any)}
      className={`flex-none flex items-center gap-2 px-6 py-4 text-sm font-medium
        transition-colors relative whitespace-nowrap
        ${activeTab === tab.id ? 'text-white' : 'text-gray-500 hover:text-gray-300'}`}
    >
      <i className={`fas ${tab.icon}`}></i>
      {tab.label}
      {activeTab === tab.id && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-rose-500
          shadow-[0_-2px_8px_rgba(244,63,94,0.5)]"></div>
      )}
    </button>
  ))}
</div>
```

**Key Patterns**:
- `overflow-x-auto` enables horizontal scroll on mobile
- `flex-none` prevents buttons from shrinking
- `whitespace-nowrap` keeps labels on single line
- `no-scrollbar` utility class hides scrollbar (custom utility)

### Content Area - Responsive Padding

```tsx
// Line 391: Content container
<div className="flex-1 overflow-y-auto p-4 md:p-6 bg-[#18181b]">
```

**Padding**:
- Mobile: `p-4` (16px)
- Desktop: `md:p-6` (24px)

### Grid Layouts - Overview Tab

```tsx
// Lines 403-444: Responsive grid for overview cards
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
  <div className="bg-[#252529] p-5 md:p-6 rounded-2xl border border-white/5
    relative overflow-hidden group hover:border-white/10 transition-colors">
    {/* Card content */}
  </div>
</div>
```

**Grid Breakdown**:
- **Mobile**: Single column `grid-cols-1`
- **Desktop**: Two columns `md:grid-cols-2`
- **Card Padding**: `p-5` mobile, `md:p-6` desktop
- **Gap**: `gap-4` (16px) consistent

### Tables - Horizontal Scroll

```tsx
// Lines 451-528: Holdings table with overflow
<div className="bg-[#252529] rounded-xl border border-white/5 overflow-hidden">
  <div className="overflow-x-auto">
    <table className="w-full text-left border-collapse min-w-[800px]">
      {/* Table rows */}
    </table>
  </div>
</div>
```

**Key Patterns**:
- Outer container: `overflow-hidden` for border radius
- Inner wrapper: `overflow-x-auto` for scroll
- Table: `min-w-[800px]` ensures minimum width, triggers scroll

### Chart Controls - Flex Wrap

```tsx
// Lines 535-548: Flex wrap for responsive controls
<div className="bg-[#252529] p-3 rounded-xl border border-white/5
  flex flex-wrap gap-2 items-center">
  <span className="text-xs text-gray-500 font-bold px-2">이동평균선</span>
  {[3, 5, 10, 20, 60, 120].map(d => (
    <label key={d} className="flex items-center gap-1.5 px-2 py-1
      bg-black/20 rounded cursor-pointer hover:bg-black/40 transition-colors">
      {/* Checkbox */}
    </label>
  ))}
</div>
```

**Patterns**:
- `flex-wrap` allows wrapping on small screens
- `gap-2` consistent spacing
- Labels use `cursor-pointer` for touch targets

---

## 3. SettingsModal - Responsive Patterns

**Source**: `frontend/src/app/components/SettingsModal.tsx`

### Sidebar/Content Layout Transformation

```tsx
// Lines 350-386: Responsive sidebar transformation
<div className="flex flex-col md:flex-row gap-6 md:gap-10 h-full md:min-h-[500px] text-gray-300">

  {/* Sidebar - Becomes horizontal tabs on mobile */}
  <div className="w-full md:w-48 flex-shrink-0 flex md:flex-col gap-2 md:gap-1
    overflow-x-auto md:overflow-visible pb-2 md:pb-0 no-scrollbar">

    {/* Section Labels - Desktop only */}
    <div className="hidden md:block text-xs font-bold text-gray-500 px-3 mb-2
      uppercase tracking-wider">계정</div>

    {/* Tab Buttons */}
    <button
      onClick={() => setActiveTab('profile')}
      className={`flex-none md:w-full text-left px-4 md:px-3 py-2
        rounded-full md:rounded-[6px] text-sm md:text-[15px] font-medium
        transition-all whitespace-nowrap
        ${activeTab === 'profile'
          ? 'bg-[#3b3b40] text-white'
          : 'bg-white/5 md:bg-transparent text-gray-400 hover:text-gray-200
            hover:bg-white/10 md:hover:bg-white/5'}`}
    >
      일반
    </button>

    {/* More tabs... */}
  </div>

  {/* Content Area */}
  <div className="flex-1 max-w-2xl pt-0">
    {/* Tab content */}
  </div>
</div>
```

**Responsive Transformation**:

| Aspect | Mobile (< 768px) | Desktop (>= 768px) |
|--------|------------------|-------------------|
| **Layout Direction** | `flex-col` | `md:flex-row` |
| **Sidebar Width** | `w-full` | `md:w-48` (192px) |
| **Sidebar Orientation** | Horizontal row | Vertical column |
| **Sidebar Overflow** | `overflow-x-auto` | `md:overflow-visible` |
| **Gap** | `gap-6` | `md:gap-10` |
| **Section Labels** | Hidden (`hidden md:block`) | Visible |
| **Button Width** | Auto (`flex-none`) | Full (`md:w-full`) |
| **Button Shape** | Pill (`rounded-full`) | Rounded rect (`md:rounded-[6px]`) |
| **Button Padding** | `px-4` | `md:px-3` |
| **Button Background** | `bg-white/5` | `md:bg-transparent` |

### Google Login Section - Flex Direction Change

```tsx
// Lines 518-539: Responsive Google login section
{!isGoogleLoggedIn ? (
  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <div className="text-sm font-medium text-white mb-1">계정 연동</div>
      <div className="text-xs text-gray-500 break-keep leading-relaxed">
        구글 계정으로 로그인하여 설정을 동기화하세요.
        {/* Status messages */}
      </div>
    </div>
    <button
      onClick={handleGoogleLogin}
      className="w-full md:w-auto px-4 py-2 bg-white text-black text-xs font-bold
        rounded-lg hover:bg-gray-100 transition-colors flex items-center justify-center
        gap-2 flex-shrink-0"
    >
      <img src="https://www.google.com/favicon.ico" alt="G" className="w-3 h-3" />
      Google 로그인
    </button>
  </div>
) : (
  // Logged in state - single row
)}
```

**Responsive Changes**:
- **Mobile**: Column layout, button full width `w-full`
- **Desktop**: Row layout, button auto width `md:w-auto`

### Input Fields - Responsive Grid

```tsx
// Lines 872-893: SMTP settings with grid
<div className="grid grid-cols-2 gap-4">
  <div>
    <label className="block text-xs font-bold text-gray-500 mb-1.5">SMTP Host</label>
    <input type="text" className="w-full bg-[#18181b] border border-white/10
      rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none
      focus:border-orange-500 transition-colors" placeholder="smtp.gmail.com" />
  </div>
  <div>
    <label className="block text-xs font-bold text-gray-500 mb-1.5">SMTP Port</label>
    <input type="text" className="w-full bg-[#18181b] border border-white/10
      rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none
      focus:border-orange-500 transition-colors" placeholder="587" />
  </div>
</div>
```

**Pattern**: 2-column grid on all sizes - inputs are wide enough

---

## 4. Full-Screen vs Centered Modals

### Centered Modal (Base Modal)

```tsx
// Modal.tsx - Lines 30-35
<div className="fixed inset-0 z-[100] flex items-center justify-center">
  <div className="w-full max-w-md max-h-[90vh]">
    {/* Content */}
  </div>
</div>
```

**Characteristics**:
- Vertically and horizontally centered
- Constrained width (`max-w-md` or `max-w-4xl`)
- Used for: Settings, confirmations, simple forms

### Full-Screen Modal (PaperTradingModal)

```tsx
// PaperTradingModal.tsx - Lines 311-313
<div className="fixed inset-0 z-[100] flex items-start justify-center p-4 pt-32">
  <div className="w-full max-w-[90vw] max-h-[85vh]">
    {/* Content */}
  </div>
</div>
```

**Characteristics**:
- Positioned from top (`items-start`, `pt-32`)
- Maximum width (`max-w-[90vw]`)
- Used for: Complex data displays, dashboards

### Comparison Table

| Aspect | Centered | Full-Screen (Top) |
|--------|----------|-------------------|
| **Vertical Align** | `items-center` | `items-start` |
| **Top Spacing** | None | `pt-32` (128px) |
| **Width** | `max-w-md` to `max-w-4xl` | `max-w-[90vw]` |
| **Height** | `max-h-[90vh]` | `max-h-[85vh]` |
| **Use Case** | Forms, confirmations | Data-heavy content |

---

## 5. Common Responsive Utilities

### Breakpoint Reference

| Breakpoint | Min Width | Usage in Modals |
|------------|-----------|-----------------|
| `sm` | 640px | Rarely used |
| `md` | 768px | Primary breakpoint |
| `lg` | 1024px | Rarely used |
| `xl` | 1280px | Not used |

### Common Responsive Patterns

#### Flex Direction Change

```tsx
// Mobile column, desktop row
className="flex flex-col md:flex-row gap-4"
```

#### Padding Scale

```tsx
// Mobile 16px, desktop 24px
className="p-4 md:p-6"
```

#### Width Changes

```tsx
// Mobile full, desktop auto
className="w-full md:w-auto"

// Mobile auto, desktop fixed
className="md:w-48"
```

#### Element Visibility

```tsx
// Hide on mobile, show on desktop
className="hidden md:block"

// Show on mobile, hide on desktop
className="md:hidden"
```

#### Text Scaling

```tsx
// Size progression
className="text-sm md:text-base"      // 14px → 16px
className="text-lg md:text-xl"        // 18px → 20px
className="text-[10px] md:text-xs"    // 10px → 12px
```

#### Icon/Avatar Sizing

```tsx
// Mobile 40px, desktop 48px
className="w-10 h-10 md:w-12 md:h-12"
```

### Horizontal Scroll Pattern

```tsx
// For tabs, tables, cards
<div className="overflow-x-auto no-scrollbar">
  <div className="flex gap-4 min-w-max">
    {/* Items */}
  </div>
</div>
```

### Table Scroll Pattern

```tsx
<div className="overflow-x-auto">
  <table className="w-full min-w-[800px]">
    {/* Table content */}
  </table>
</div>
```

---

## Quick Reference Card Patterns

### Card Component Structure

```tsx
<div className="bg-[#252529] p-5 md:p-6 rounded-2xl border border-white/5
  hover:border-white/10 transition-colors">
  <div className="text-gray-400 text-sm font-medium mb-1">Label</div>
  <div className="text-3xl md:text-4xl font-bold text-white">Value</div>
</div>
```

### Input Group Pattern

```tsx
<div className="flex flex-col md:flex-row gap-2">
  <input className="w-full md:flex-1" />
  <button className="w-full md:w-auto">Submit</button>
</div>
```

---

## File Locations

- **Modal Base**: `/frontend/src/app/components/Modal.tsx`
- **PaperTradingModal**: `/frontend/src/app/components/PaperTradingModal.tsx`
- **SettingsModal**: `/frontend/src/app/components/SettingsModal.tsx`

---

## Tailwind Classes Summary

| Category | Common Classes |
|----------|---------------|
| **Layout** | `flex`, `flex-col`, `md:flex-row`, `grid`, `grid-cols-1`, `md:grid-cols-2` |
| **Spacing** | `p-4`, `md:p-6`, `gap-4`, `md:gap-6` |
| **Sizing** | `w-full`, `md:w-auto`, `md:w-48`, `max-w-md`, `max-w-4xl` |
| **Overflow** | `overflow-x-auto`, `overflow-y-auto` |
| **Visibility** | `hidden`, `md:block`, `md:hidden` |
| **Typography** | `text-sm`, `md:text-base`, `text-lg`, `md:text-xl` |
