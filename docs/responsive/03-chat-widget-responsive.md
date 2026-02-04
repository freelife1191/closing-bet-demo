# ChatWidget Responsive Design Reference

Reference: `frontend/src/app/components/ChatWidget.tsx`

## Overview

The ChatWidget is a floating chat interface that transforms between different layouts based on screen size. On mobile, it's a full-screen overlay; on desktop, it's a fixed-size floating panel.

---

## 1. Floating Button Responsive Patterns

### Position Changes

**Line 502-503**: Button container uses responsive positioning

```tsx
<div className="fixed bottom-3 right-3 md:bottom-6 md:right-6 z-[120] flex flex-col items-end">
```

| Breakpoint | Position |
|------------|----------|
| Mobile (< 768px) | `bottom-3 right-3` (12px from edges) |
| Desktop (≥ 768px) | `bottom-6 right-6` (24px from edges) |

### Size Changes

**Line 505**: Button icon scales with screen size

```tsx
className={`w-11 h-11 md:w-14 md:h-14 rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 active:scale-95 group ${isOpen ? 'bg-[#2c2c2e] hover:bg-[#3a3a3c] text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
```

| Breakpoint | Size | Icon Size |
|------------|------|-----------|
| Mobile (< 768px) | `w-11 h-11` (44px) | `text-lg` |
| Desktop (≥ 768px) | `w-14 h-14` (56px) | `text-2xl` |

**Line 508-509**: Icon animations remain consistent across sizes

```tsx
<i className={`fas fa-comment-dots text-lg md:text-2xl transition-all duration-300 absolute ${isOpen ? 'opacity-0 rotate-90 scale-50' : 'opacity-100 rotate-0 scale-100'}`}></i>
<i className={`fas fa-times text-lg md:text-2xl transition-all duration-300 absolute ${isOpen ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'}`}></i>
```

---

## 2. Chat Panel Responsive Patterns

### Full-Screen Mobile / Fixed-Size Desktop

**Line 261**: Main container transforms layout completely

```tsx
<div className="fixed inset-0 z-[110] w-full h-[100dvh] md:fixed md:inset-auto md:bottom-24 md:right-6 md:w-[430px] md:h-[730px] md:max-h-[80vh] bg-[#1c1c1e] md:border border-white/10 md:rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-fade-in font-sans md:z-[110]">
```

| Property | Mobile (< 768px) | Desktop (≥ 768px) |
|----------|------------------|-------------------|
| Position | `fixed inset-0` | `md:fixed md:inset-auto` |
| Location | Full screen | `md:bottom-24 md:right-6` |
| Width | `w-full` (100%) | `md:w-[430px]` |
| Height | `h-[100dvh]` (viewport) | `md:h-[730px] md:max-h-[80vh]` |
| Border | None | `md:border` |
| Border Radius | None | `md:rounded-2xl` |

**Key Pattern**: Mobile uses `100dvh` (dynamic viewport height) to handle mobile browser chrome, while desktop uses fixed pixel dimensions with max-height constraint.

---

## 3. Message Area Responsive Patterns

### Empty State Greeting

**Line 312**: Heading scales with screen size

```tsx
<h2 className="text-xl md:text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400 break-keep">
  안녕하세요, {session?.user?.name || '투자자'}님! 👋
</h2>
```

| Breakpoint | Font Size |
|------------|-----------|
| Mobile | `text-xl` (20px) |
| Desktop | `md:text-2xl` (24px) |

**Line 315-316**: Description maintains consistent max-width

```tsx
<p className="text-gray-400 text-sm leading-relaxed break-keep max-w-[280px] mx-auto">
  <strong className="text-white">스마트머니봇</strong>이 VCP 패턴 분석과<br />시장 동향 예측을 도와드립니다.
</p>
```

### Message Bubbles

**Line 341**: Message bubbles have responsive max-width

```tsx
<div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${msg.role === 'user'
  ? 'bg-blue-600 text-white whitespace-pre-wrap'
  : 'bg-[#2c2c2e] text-gray-200'
  }`}>
```

- `max-w-[85%]` ensures messages never fill entire width on any screen
- Consistent padding and font size across all breakpoints
- `whitespace-pre-wrap` preserves formatting on user messages

### Message Container

**Line 338**: Message area padding adapts

```tsx
<div className="p-4 space-y-4 pb-20">
```

- `pb-20` provides space for input area and persistent suggestions
- Consistent padding on all screen sizes

---

## 4. Input Area Responsive Patterns

### Input Container

**Line 450-451**: Input area maintains consistent layout

```tsx
<div className="p-3 bg-[#1c1c1e] border-t border-white/5 relative z-20 flex-shrink-0">
  <div className="flex items-end gap-2 bg-[#2c2c2e] rounded-3xl p-2 pl-4 relative transition-all ring-1 ring-white/5 focus-within:ring-blue-500/50">
```

**Key Patterns**:
- `flex-shrink-0` prevents input area from being compressed
- `rounded-3xl` creates pill shape consistent across all sizes
- `focus-within:ring-blue-500/50` provides visual feedback on focus

### Textarea Auto-Resize

**Line 465-477**: Textarea expands with content up to max height

```tsx
<textarea
  ref={textareaRef}
  value={input}
  onChange={(e) => setInput(e.target.value)}
  onKeyDown={handleKeyDown}
  placeholder="메시지를 입력하세요..."
  className="flex-1 bg-transparent text-white text-sm placeholder-gray-500 resize-none focus:outline-none custom-scrollbar py-1.5 leading-relaxed max-h-[100px] min-h-[36px]"
  rows={1}
  onInput={(e) => {
    const target = e.target as HTMLTextAreaElement;
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 100)}px`;
  }}
/>
```

**Responsive Behavior**:
- `flex-1` takes available horizontal space
- `min-h-[36px]` ensures minimum tap target size
- `max-h-[100px]` caps expansion at 100px with scroll
- `text-sm` maintains consistent font size across all breakpoints

### Command & Send Buttons

**Line 454-462**: Command button with fixed size

```tsx
<div className="relative flex-shrink-0 pb-[1px]">
  <button
    onClick={() => setInput('/ ')}
    className="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-blue-400 transition-colors"
    title="명령어"
  >
    <i className="fas fa-terminal text-xs"></i>
  </button>
</div>
```

**Line 481-493**: Send button with loading state

```tsx
<div className="flex-shrink-0 pb-[1px]">
  <button
    onClick={() => handleSend()}
    disabled={!input.trim() || isLoading}
    className="w-8 h-8 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 rounded-lg flex items-center justify-center text-white transition-all shadow-lg active:scale-95"
  >
    {isLoading ? (
      <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
    ) : (
      <i className="fas fa-paper-plane text-xs"></i>
    )}
  </button>
</div>
```

**Key Pattern**: Both buttons are `flex-shrink-0` with fixed `w-8 h-8` (32px) - consistent across all breakpoints.

---

## 5. Suggestions Grid Responsive Patterns

### Welcome State Grid

**Line 322**: Empty state uses 2-column grid

```tsx
<div className="grid grid-cols-2 gap-2">
  {WELCOME_SUGGESTIONS.map((suggestion, idx) => (
    <button
      key={idx}
      onClick={() => handleSuggestionClick(suggestion)}
      className="bg-[#2c2c2e] hover:bg-[#3a3a3c] border border-white/5 hover:border-blue-500/30 p-3 rounded-2xl transition-all duration-200 text-xs text-gray-300 hover:text-white text-left flex items-center justify-between group h-full min-h-[60px]"
    >
      <span className="line-clamp-2 leading-tight">{suggestion}</span>
      <i className="fas fa-arrow-right text-[10px] opacity-0 group-hover:opacity-100 transition-opacity text-blue-400 flex-shrink-0 ml-1"></i>
    </button>
  ))}
</div>
```

**Grid Behavior**:
- Always `grid-cols-2` regardless of screen size
- `gap-2` provides consistent 8px spacing
- `min-h-[60px]` ensures minimum touch target height
- `line-clamp-2` limits text to 2 lines with ellipsis

### Persistent Suggestions (Active Chat)

**Line 433-446**: Horizontal scrollable suggestions

```tsx
{messages.length > 0 && (
  <div className="bg-[#1c1c1e] border-t border-white/5 py-3 px-4 flex-shrink-0">
    <div className="flex gap-2 overflow-x-auto custom-scrollbar-hide">
      {WELCOME_SUGGESTIONS.map((suggestion, idx) => (
        <button
          key={idx}
          onClick={() => handleSuggestionClick(suggestion)}
          className="flex-shrink-0 px-3 py-1.5 bg-[#2c2c2e] hover:bg-blue-600 hover:text-white border border-white/5 rounded-full text-[11px] text-gray-400 hover:text-white transition-all whitespace-nowrap"
        >
          {suggestion}
        </button>
      ))}
    </div>
  </div>
)}
```

**Horizontal Scroll Pattern**:
- `flex gap-2 overflow-x-auto` creates horizontal scrolling container
- `flex-shrink-0` prevents button compression
- `whitespace-nowrap` keeps text on single line
- `custom-scrollbar-hide` hides scrollbar for cleaner UI
- Consistent pill shape with `rounded-full`

---

## 6. Header Responsive Patterns

**Line 264**: Header maintains consistent layout

```tsx
<div className="bg-[#2c2c2e] p-4 flex items-center justify-between border-b border-white/5 flex-shrink-0">
```

**Line 265-281**: Header content with overflow handling

```tsx
<div className="flex items-center gap-2 overflow-hidden">
  <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
    <i className="fas fa-robot text-sm text-white"></i>
  </div>
  <div className="min-w-0">
    <div className="font-bold text-white text-sm flex items-center gap-2 whitespace-nowrap">
      스마트머니봇
      {hasApiKey && (
        <i className="fas fa-key text-[10px] text-yellow-500 animate-pulse flex-shrink-0" title="개인 API Key 사용 중 (무제한)"></i>
      )}
    </div>
    <div className="flex items-center gap-1 whitespace-nowrap">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse flex-shrink-0"></span>
      <span className="text-[10px] text-gray-400 truncate">보통 1초 내 답변</span>
    </div>
  </div>
</div>
```

**Key Patterns**:
- `overflow-hidden` on container prevents content overflow
- `flex-shrink-0` on icon prevents compression
- `min-w-0` allows text truncation in flex container
- `truncate` on status text adds ellipsis when needed
- `whitespace-nowrap` keeps text on single line

---

## 7. Command Popup Responsive Patterns

**Line 411-429**: Command suggestions popup

```tsx
{input.startsWith('/') && filteredCommands.length > 0 && (
  <div className="absolute bottom-[70px] left-2 right-2 bg-[#1c1c1e] border border-white/10 rounded-xl shadow-2xl overflow-hidden max-h-[200px] overflow-y-auto z-[60]">
    <div className="px-3 py-2 bg-[#2c2c2e] border-b border-white/5 text-[10px] font-bold text-gray-400">
      사용 가능한 명령어
    </div>
    {filteredCommands.map((cmd, idx) => (
      <button
        key={idx}
        onClick={() => handleCommandClick(cmd.cmd)}
        className={`w-full text-left px-4 py-2 text-xs flex justify-between items-center transition-colors group ${idx === selectedCommandIndex
          ? 'bg-blue-600/20 text-white'
          : 'text-gray-200 hover:bg-blue-600/20 hover:text-white'
          }`}
      >
        <span className={`font-mono font-bold ${idx === selectedCommandIndex ? 'text-blue-300' : 'text-blue-400'}`}>{cmd.cmd}</span>
        <span className="text-gray-500 group-hover:text-gray-300">{cmd.desc}</span>
      </button>
    ))}
  </div>
)}
```

**Responsive Behavior**:
- `absolute bottom-[70px]` positions above input area
- `left-2 right-2` maintains 8px margins on all screens
- `max-h-[200px]` caps height with scroll for overflow
- `overflow-y-auto` enables scrolling when many commands

---

## 8. Tooltip Responsive Patterns

**Line 513-528**: Onboarding tooltip

```tsx
{!isOpen && messages.length === 0 && showTooltip && (
  <div className="absolute right-16 top-1/2 -translate-y-1/2 bg-white text-black px-4 py-2 rounded-xl shadow-lg whitespace-nowrap animate-fade-in origin-right z-50">
    <button
      onClick={(e) => {
        e.stopPropagation();
        setShowTooltip(false);
      }}
      className="absolute -top-2 -left-2 w-5 h-5 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center text-gray-600 shadow-sm transition-colors z-10"
    >
      <i className="fas fa-times text-[10px]"></i>
    </button>
    <div className="text-sm font-bold">궁금한 건 채팅으로 문의하세요</div>
    <div className="text-xs text-gray-500">대화 시작하기</div>
    <div className="absolute top-1/2 -right-1.5 w-3 h-3 bg-white transform -translate-y-1/2 rotate-45"></div>
  </div>
)}
```

**Responsive Behavior**:
- `absolute right-16` positions 64px from right (leaves space for button)
- `top-1/2 -translate-y-1/2` vertically centers with button
- `whitespace-nowrap` prevents text wrapping
- `origin-right` scales animation from right edge
- Tooltip arrow uses `rotate-45` transform

---

## 9. Z-Index Layering

| Element | Z-Index | Purpose |
|---------|---------|---------|
| Command popup | `z-[60]` | Above content, below panel |
| Chat panel (mobile) | `z-[110]` | Above most content |
| Chat panel (desktop) | `md:z-[110]` | Above most content |
| Toggle button | `z-[120]` | Always on top |
| Input area | `z-[20]` | Above messages |
| Tooltip | `z-[50]` | Above content, below panel |

---

## 10. Loading State Responsive Patterns

**Line 392-403**: Thinking indicator

```tsx
{isLoading && (
  <div className="flex justify-start">
    <div className="bg-[#2c2c2e] rounded-xl px-4 py-3 border border-white/5">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
        <span className="text-xs text-gray-300 font-medium animate-pulse">
          {THINKING_STEPS[thinkingIndex]}
        </span>
      </div>
    </div>
  </div>
)}
```

**Consistent Behavior**:
- Spinner size (`w-4 h-4`) consistent across all breakpoints
- Text size (`text-xs`) maintains readability
- Animation (spin, pulse) works consistently

---

## Responsive Testing Checklist

- [ ] Mobile (< 768px): Full-screen overlay opens correctly
- [ ] Mobile (≥ 768px): Floating panel with correct dimensions (430px × 730px)
- [ ] Button position shifts from 12px to 24px margin at desktop breakpoint
- [ ] Button icon scales from 44px to 56px at desktop breakpoint
- [ ] Suggestions grid maintains 2-column layout on all screens
- [ ] Horizontal scrolling works for persistent suggestions
- [ ] Message bubbles respect 85% max-width
- [ ] Textarea auto-resizes up to 100px max height
- [ ] Command popup appears above input with correct positioning
- [ ] Tooltip positions correctly next to toggle button
- [ ] All touch targets meet minimum 44px height requirement
- [ ] Z-index layering prevents overlap issues

---

## Breakpoint Reference

| Breakpoint | Width | Usage in Component |
|------------|-------|-------------------|
| Mobile | < 768px | Full screen, smaller button, compact spacing |
| Desktop | ≥ 768px (`md:`) | Floating panel, larger button, fixed dimensions |

**Note**: This component only has one breakpoint (`md:`). Mobile-first approach with desktop overrides.
