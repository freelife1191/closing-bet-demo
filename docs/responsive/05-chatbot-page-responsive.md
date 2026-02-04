# Chatbot Page - Responsive Design Reference

**Source File**: `frontend/src/app/chatbot/page.tsx`
**Last Updated**: 2026-02-04

## Table of Contents

1. [Mobile Sidebar Overlay Pattern](#1-mobile-sidebar-overlay-pattern)
2. [Desktop Sessions Sidebar Pattern](#2-desktop-sessions-sidebar-pattern)
3. [Main Chat Area Responsive Patterns](#3-main-chat-area-responsive-patterns)
4. [Suggestions Grid Responsive Patterns](#4-suggestions-grid-responsive-patterns)
5. [Input Area Responsive Patterns](#5-input-area-responsive-patterns)
6. [Model Selector Responsive Patterns](#6-model-selector-responsive-patterns)

---

## 1. Mobile Sidebar Overlay Pattern

**Location**: Lines 633-727

### Pattern: Full-screen Overlay with Backdrop

```tsx
// Line 634-636: Mobile sidebar overlay with z-index layering
{isMobileSidebarOpen && (
  <div className="fixed inset-0 z-50 flex md:hidden">
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
         onClick={() => setIsMobileSidebarOpen(false)}></div>
```

**Key Classes**:
- `fixed inset-0` - Covers entire viewport
- `z-50` - Above all content
- `md:hidden` - Only visible on mobile (< 768px)
- `bg-black/60 backdrop-blur-sm` - Dimmed backdrop effect

### Sidebar Container

```tsx
// Line 637: Slide-in panel
<div className="relative w-[280px] bg-[#1e1f20] h-full shadow-2xl
                flex flex-col animate-slide-in-left border-r border-white/10">
```

**Key Classes**:
- `w-[280px]` - Fixed width for mobile
- `relative` - Positioned over backdrop
- `h-full` - Full viewport height
- `animate-slide-in-left` - Custom slide animation

### Navigation Items (Mobile)

```tsx
// Line 647-662: Mobile navigation links
<Link href="/dashboard/kr" className="flex items-center gap-3 px-3 py-2.5
                                     text-gray-300 hover:bg-white/5 rounded-lg
                                     text-sm transition-colors">
```

**Key Classes**:
- `px-3 py-2.5` - Comfortable touch targets (min 44px height)
- `text-sm` - Readable on mobile
- `hover:bg-white/5` - Subtle hover feedback

### Session Items (Mobile)

```tsx
// Line 688-691: Mobile session items with active states
className={`group relative w-full text-left px-3 py-3 rounded-lg
            text-sm transition-colors cursor-pointer flex items-center gap-3
            ${currentSessionId === session.id
              ? 'bg-[#004a77]/40 text-blue-100'
              : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
```

**Key Classes**:
- `py-3` - Extra vertical padding for touch
- `w-full` - Full width for easy tapping

---

## 2. Desktop Sessions Sidebar Pattern

**Location**: Lines 763-806

### Pattern: Fixed-width Sidebar

```tsx
// Line 764: Desktop sessions sidebar
<div className="w-[260px] flex-shrink-0 flex flex-col bg-[#1e1f20]
                hidden md:flex border-r border-white/5">
```

**Key Classes**:
- `w-[260px]` - Fixed desktop width
- `flex-shrink-0` - Prevents shrinking
- `hidden md:flex` - Hidden on mobile, visible on desktop (>= 768px)
- `border-r border-white/5` - Subtle border

### Session Items (Desktop)

```tsx
// Line 782-785: Desktop session items
className={`group relative w-full text-left px-3 py-2.5 rounded-lg
            text-sm transition-colors cursor-pointer flex items-center gap-2
            ${currentSessionId === session.id
              ? 'bg-[#004a77]/40 text-blue-100'
              : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
            }`}
```

**Key Classes**:
- `py-2.5` - Slightly tighter than mobile (py-3)
- `gap-2` - Smaller icon gap than mobile (gap-3)

### Delete Button (Desktop)

```tsx
// Line 792: Desktop delete button with hover reveal
className="opacity-0 group-hover:opacity-100 p-1 text-gray-500
           hover:text-red-400 transition-opacity absolute right-2
           bg-[#1e1f20]/80 rounded shadow-sm"
```

**Key Classes**:
- `opacity-0 group-hover:opacity-100` - Reveal on hover
- `absolute right-2` - Positioned on right edge

---

## 3. Main Chat Area Responsive Patterns

**Location**: Lines 808-839, 842-1004

### Content Wrapper

```tsx
// Line 761: Content wrapper with sidebar offset
<div className="flex-1 flex pl-0 md:pl-64 h-full">
```

**Key Classes**:
- `pl-0 md:pl-64` - No padding on mobile, 256px on desktop (sidebar width)
- `flex-1` - Takes remaining space

### Top Bar

```tsx
// Line 812: Responsive top bar
<div className="h-14 flex items-center justify-between px-4 md:px-6
                sticky top-0 z-10 bg-[#000000]/80 backdrop-blur-sm
                border-b border-white/5 md:border-none">
```

**Key Classes**:
- `h-14` - Fixed header height
- `px-4 md:px-6` - Responsive horizontal padding
- `md:border-none` - No border on desktop
- `sticky top-0` - Sticks to top on scroll

### Hamburger Button (Mobile Only)

```tsx
// Line 815-820: Mobile menu trigger
<button
  onClick={() => setIsMobileSidebarOpen(true)}
  className="md:hidden w-8 h-8 flex items-center justify-center
             rounded-full hover:bg-white/10 active:bg-white/20
             transition-colors -ml-2"
>
```

**Key Classes**:
- `md:hidden` - Hidden on desktop
- `w-8 h-8` - 32px touch target
- `-ml-2` - Negative margin for alignment

### Chat Content Container

```tsx
// Line 842-843: Main chat content
<main className="flex-1 overflow-y-auto relative custom-scrollbar pb-40">
  <div className="max-w-3xl mx-auto px-4 py-8 min-h-full flex flex-col">
```

**Key Classes**:
- `max-w-3xl` - Constrain width for readability
- `mx-auto` - Center content
- `px-4` - Consistent horizontal padding
- `pb-40` - Bottom padding for fixed input area

### Empty State Typography

```tsx
// Line 849-854: Responsive greeting text
<h1 className="text-2xl md:text-5xl font-bold bg-clip-text text-transparent
               bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570]
               animate-fade-in-up break-keep leading-tight">
  안녕하세요, {userProfile?.name}님
</h1>
<h2 className="text-lg md:text-4xl font-bold text-[#444746] opacity-50
               animate-fade-in-up delay-100 break-keep leading-tight">
```

**Key Classes**:
- `text-2xl md:text-5xl` - Scale from mobile to desktop
- `break-keep` - Prevent Korean text breaking
- `leading-tight` - Compact line height

---

## 4. Suggestions Grid Responsive Patterns

**Location**: Lines 858-879

### Responsive Grid Layout

```tsx
// Line 858: Suggestions grid with responsive columns
<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4
                gap-2.5 md:gap-3 w-full max-w-4xl
                animate-fade-in-up delay-200 px-4 md:px-0">
```

**Key Classes**:
- `grid-cols-2` - 2 columns on mobile
- `md:grid-cols-3` - 3 columns on medium screens (>= 768px)
- `lg:grid-cols-4` - 4 columns on large screens (>= 1024px)
- `gap-2.5 md:gap-3` - Responsive gap spacing

### Suggestion Cards

```tsx
// Line 863: Card with responsive sizing
className="bg-[#1e1f20] hover:bg-[#333537] p-3 md:p-4
           rounded-2xl text-left transition-all h-32 md:h-48
           flex flex-col justify-between group relative overflow-hidden
           border border-white/5 active:scale-95 duration-200"
```

**Key Classes**:
- `p-3 md:p-4` - Responsive padding
- `h-32 md:h-48` - Responsive height (128px mobile, 192px desktop)
- `active:scale-95` - Press feedback on touch

### Card Content

```tsx
// Line 866: Background icon with responsive opacity/size
<div className="absolute top-0 right-0 p-2 md:p-3
                opacity-5 md:opacity-10 group-hover:opacity-20
                transition-opacity">
  <i className={`${card.icon} text-2xl md:text-4xl`}></i>
</div>

// Line 870: Description text with responsive size
<div className="text-[11px] md:text-sm text-gray-300 font-medium
                z-10 break-keep line-clamp-3 leading-relaxed">
  {card.desc}
</div>

// Line 874: Icon button with responsive size
<div className="self-end w-6 h-6 md:w-8 md:h-8 rounded-full
                bg-black/20 group-hover:bg-white/20 flex items-center
                justify-center transition-colors z-10">
  <i className={`${card.icon} text-[10px] md:text-xs
                 text-gray-400 group-hover:text-white`}></i>
</div>
```

**Key Classes**:
- `text-[11px] md:text-sm` - Scale font size
- `w-6 h-6 md:w-8 md:h-8` - Scale button size
- `line-clamp-3` - Limit to 3 lines

---

## 5. Input Area Responsive Patterns

**Location**: Lines 1006-1204

### Footer Container

```tsx
// Line 1007: Fixed footer with padding
<footer className="absolute bottom-0 left-0 right-0 p-4 bg-[#131314]">
  <div className="max-w-3xl mx-auto relative">
```

**Key Classes**:
- `absolute bottom-0` - Fixed at bottom
- `p-4` - Consistent padding
- `max-w-3xl mx-auto` - Center and constrain width

### Input Container

```tsx
// Line 1076: Rounded input with focus state
<div className="relative bg-[#1e1f20] rounded-[28px]
                focus-within:bg-[#2a2b2d] focus-within:ring-1
                focus-within:ring-white/20 transition-all shadow-lg">
```

**Key Classes**:
- `rounded-[28px]` - Fully rounded (pill shape)
- `focus-within:ring-1` - Ring when any child is focused

### File Attachments Preview

```tsx
// Line 1080: Horizontal scroll for file previews
<div className="px-4 pt-3 flex gap-2 overflow-x-auto custom-scrollbar">
  {attachedFiles.map((file, idx) => (
    <div key={idx} className="relative group shrink-0">
      <div className="w-16 h-16 rounded-lg bg-black/40
                      border border-white/10 flex items-center
                      justify-center overflow-hidden">
```

**Key Classes**:
- `overflow-x-auto` - Horizontal scroll for many files
- `shrink-0` - Prevent file items from shrinking
- `w-16 h-16` - Fixed thumbnail size

### Input Controls Layout

```tsx
// Line 1101: Input controls row
<div className="flex items-center pl-2 pr-2 py-2 gap-2">
```

**Key Classes**:
- `flex items-center` - Horizontal layout with alignment
- `gap-2` - Consistent spacing

### Plus Button

```tsx
// Line 1105: Plus button for file attachment
<button className="flex-shrink-0 w-8 h-8 flex items-center
                 justify-center text-gray-400 hover:text-white
                 hover:bg-white/10 rounded-full transition-colors"
        title="파일 첨부"
>
```

**Key Classes**:
- `flex-shrink-0` - Prevent shrinking
- `w-8 h-8` - Minimum touch target size

### Textarea

```tsx
// Line 1146-1162: Auto-resizing textarea
<textarea
  ref={inputRef}
  value={input}
  onChange={(e) => {
    setInput(e.target.value);
    // Auto-resize
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  }}
  className="flex-1 bg-transparent text-white px-2 resize-none
             max-h-[200px] focus:outline-none custom-scrollbar
             leading-relaxed py-2"
  style={{ height: 'auto', minHeight: '40px' }}
  rows={1}
/>
```

**Key Classes**:
- `flex-1` - Takes available space
- `resize-none` - Disable manual resize
- `max-h-[200px]` - Max height limit
- `minHeight: '40px'` - Minimum height via inline style

### Action Buttons

```tsx
// Line 1167: Mic button with recording state
<button
  className={`flex-shrink-0 w-10 h-10 rounded-full
              flex items-center justify-center transition-colors
              ${isRecording ? 'text-red-500 bg-red-500/10 animate-pulse'
                            : 'text-gray-400 hover:text-white hover:bg-white/10'}`}
  title="음성 입력"
>
```

**Key Classes**:
- `w-10 h-10` - 40px touch target
- `animate-pulse` - Pulse animation when recording
- Conditional classes for state

```tsx
// Line 1187-1192: Send button with hover effect
<button
  onClick={() => handleSend()}
  className="flex-shrink-0 w-10 h-10 rounded-full
             flex items-center justify-center text-white
             bg-blue-600 hover:bg-blue-500
             disabled:opacity-30 disabled:hover:bg-blue-600
             transition-all shadow-lg animate-fade-in"
>
```

---

## 6. Model Selector Responsive Patterns

**Location**: Lines 1034-1073, 1119-1141

### Pattern: Mobile Floating vs Desktop Inline

#### Mobile: Floating Above Input

```tsx
// Line 1051-1059: Mobile model selector (floating)
<div className="pointer-events-auto md:hidden relative group">
  <button
    className="flex items-center gap-2 px-3 py-1.5
               bg-[#1e1f20]/90 backdrop-blur-md
               border border-white/10 rounded-full
               text-xs text-gray-300 shadow-lg"
  >
    <i className="fas fa-sparkles text-blue-400"></i>
    <span>{currentModel.split('-').pop()?.toUpperCase() || 'MODEL'}</span>
    <i className="fas fa-chevron-down text-[10px] text-gray-500"></i>
  </button>
```

**Key Classes**:
- `md:hidden` - Only visible on mobile
- `pointer-events-auto` - Enable clicks while in pointer-events-none container
- `backdrop-blur-md` - Blur effect for floating UI

#### Desktop: Inline in Input Bar

```tsx
// Line 1120-1127: Desktop model selector (inline)
<div className="relative group flex-shrink-0 hidden md:block">
  <button
    className="flex items-center gap-2 px-3 py-1.5
               bg-black/20 hover:bg-white/10 rounded-full
               text-xs text-gray-300 transition-colors
               border border-white/5 h-8"
  >
```

**Key Classes**:
- `hidden md:block` - Only visible on desktop
- `flex-shrink-0` - Prevent shrinking
- `h-8` - Fixed height

### Dropdown/Dropup Menu

```tsx
// Line 1061-1072: Dropup menu for mobile
<div className="absolute bottom-full left-1/2 transform -translate-x-1/2
                mb-2 w-48 bg-[#2a2b2d] border border-white/10
                rounded-xl shadow-xl overflow-hidden
                invisible group-hover:visible opacity-0
                group-hover:opacity-100 transition-all z-40">
```

```tsx
// Line 1129-1140: Dropup menu for desktop
<div className="absolute bottom-full left-0 mb-2
                w-48 bg-[#2a2b2d] border border-white/10
                rounded-xl shadow-xl overflow-hidden
                invisible group-hover:visible opacity-0
                group-hover:opacity-100 transition-all z-30">
```

**Key Classes**:
- `absolute bottom-full` - Position above button
- `left-1/2 transform -translate-x-1/2` - Center align (mobile)
- `left-0` - Left align (desktop)
- `invisible group-hover:visible` - Show on hover
- `opacity-0 group-hover:opacity-100` - Fade in transition

---

## Responsive Breakpoints Reference

| Breakpoint | Size | Usage |
|------------|------|-------|
| `sm` | 640px | Small tablets |
| `md` | 768px | Tablets, small laptops |
| `lg` | 1024px | Desktops |
| `xl` | 1280px | Large desktops |

## Common Responsive Patterns Used

### Hide on Mobile / Show on Desktop
```tsx
className="hidden md:block"  // Desktop only
className="md:hidden"        // Mobile only
```

### Responsive Spacing
```tsx
className="px-4 md:px-6"     // Horizontal padding
className="py-2 md:py-3"     // Vertical padding
className="gap-2 md:gap-3"   // Gap spacing
```

### Responsive Typography
```tsx
className="text-sm md:text-base"      // Font size
className="text-xs md:text-sm"        // Small text
```

### Responsive Grid
```tsx
className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
```

---

## Best Practices Observed

1. **Touch Targets**: Minimum 32px (w-8 h-8) for all interactive elements
2. **Progressive Enhancement**: Mobile-first approach with `md:` prefixes
3. **Consistent Padding**: `px-4` for main content containers
4. **Backdrop Effects**: `backdrop-blur-sm/md` for overlay elements
5. **Smooth Transitions**: `transition-all`, `transition-colors` for state changes
6. **Active Feedback**: `active:scale-95` for button press feedback
7. **Overflow Handling**: `overflow-x-auto` for horizontal scrolling content
8. **Text Preservation**: `break-keep` for Korean text

---

## Related Components

- **Sidebar Component**: `frontend/src/app/components/Sidebar.tsx`
- **SettingsModal Component**: `frontend/src/app/components/SettingsModal.tsx`
- **Modal Component**: `frontend/src/app/components/Modal.tsx`
