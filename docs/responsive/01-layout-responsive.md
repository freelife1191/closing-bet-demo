# Responsive Design Reference - Layout Components

This document covers responsive patterns for the core layout components: Header, Sidebar, and Dashboard Layout.

## Table of Contents
1. [Header Responsive Patterns](#header-responsive-patterns)
2. [Sidebar Responsive Patterns](#sidebar-responsive-patterns)
3. [Dashboard Layout Responsive Patterns](#dashboard-layout-responsive-patterns)
4. [Tailwind Breakpoints Reference](#tailwind-breakpoints-reference)

---

## Header Responsive Patterns

**Source:** `frontend/src/app/components/Header.tsx`

### Mobile Menu Button (lines 48-53)

```tsx
{/* Mobile Menu Button */}
<button
  onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
  className="md:hidden text-gray-400 hover:text-white p-2 -ml-2 transition-colors"
>
  <i className="fas fa-bars text-xl"></i>
</button>
```

**Pattern:** The hamburger menu button uses `md:hidden` to display only on mobile/tablet devices (< 768px). It dispatches a custom `sidebar-toggle` event that the Sidebar component listens to.

### Breadcrumb Display (lines 55-58)

```tsx
{/* Breadcrumbs (Mobile: Hidden on very small screens if needed, usually fine) */}
<div className="hidden sm:block">{getBreadcrumbs()}</div>
<div className="sm:hidden text-sm font-bold text-white">KR Market</div>
```

**Pattern:**
- Desktop/Tablet (sm+): Full breadcrumb path with navigation
- Mobile (< 640px): Simplified page title ("KR Market") instead of breadcrumbs

### Search Bar Hide/Show (lines 62-77)

```tsx
{/* Search Bar */}
<div className="relative hidden md:block">
  <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i>
  <input
    type="text"
    placeholder="Search markets, tickers..."
    className="w-full md:w-80 bg-[#1c1c1e] border border-white/10 rounded-lg py-2 pl-10 pr-12 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 transition-colors"
  />
  <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500 border border-white/10 rounded px-1.5 py-0.5">
    K
  </div>
</div>
{/* Mobile Search Icon */}
<button className="md:hidden w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-400">
  <i className="fas fa-search"></i>
</button>
```

**Pattern:**
- Desktop (md+): Full search input with keyboard shortcut indicator
- Mobile (< 768px): Icon-only button that would typically open a search modal

### Header Positioning (line 44)

```tsx
<header className="h-16 border-b border-white/10 bg-[#000000]/95 backdrop-blur supports-[backdrop-filter]:bg-[#000000]/60 flex items-center justify-between px-4 md:px-6 fixed top-0 md:left-64 left-0 right-0 z-40 transition-all duration-300">
```

**Pattern:**
- `fixed top-0 left-0 right-0`: Full width on mobile
- `md:left-64`: Offset by sidebar width (256px) on desktop
- `px-4 md:px-6`: Responsive horizontal padding

---

## Sidebar Responsive Patterns

**Source:** `frontend/src/app/components/Sidebar.tsx`

### Mobile Sidebar State Management (lines 28-34, 54-56)

```tsx
// Mobile Sidebar State
const [isMobileOpen, setIsMobileOpen] = useState(false);

// Close mobile sidebar on path change
useEffect(() => {
  setIsMobileOpen(false);
}, [pathname]);

// Listen for mobile sidebar toggle
const handleSidebarToggle = () => setIsMobileOpen(prev => !prev);
window.addEventListener('sidebar-toggle', handleSidebarToggle);
```

**Pattern:**
- State-controlled visibility on mobile
- Auto-closes on route navigation (better UX)
- Event-driven toggle from Header button

### Mobile Overlay (lines 128-134)

```tsx
{/* Mobile Sidebar Overlay */}
{isMobileOpen && (
  <div
    className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[59] md:hidden transition-opacity"
    onClick={() => setIsMobileOpen(false)}
  />
)}
```

**Pattern:**
- Backdrop overlay appears only on mobile (`md:hidden`)
- Click-to-dismiss functionality
- High z-index (59) below sidebar (60) but above content
- Semi-transparent with blur effect

### Sidebar Transform/Position (line 136)

```tsx
<aside className={`w-64 border-r border-white/10 bg-[#1c1c1e] flex flex-col h-screen fixed left-0 top-0 z-[60] transition-transform duration-300 ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}>
```

**Pattern:**
- `fixed left-0 top-0 h-screen`: Fixed position, full height
- Mobile: `-translate-x-full` (hidden off-screen) or `translate-x-0` (visible)
- Desktop: `md:translate-x-0` (always visible)
- `transition-transform duration-300`: Smooth slide animation

**Key Classes:**
| Breakpoint | Behavior |
|------------|----------|
| Mobile (< 768px) | Toggled via `translate-x` based on `isMobileOpen` state |
| Desktop (md+, >= 768px) | Always visible (`translate-x-0` override) |

### Sidebar Width Impact on Layout

The sidebar uses fixed width `w-64` (256px). The dashboard layout must account for this offset.

---

## Dashboard Layout Responsive Patterns

**Source:** `frontend/src/app/dashboard/layout.tsx`

### Main Content Offset (line 15)

```tsx
<main className="md:pl-64 pl-0 pt-16 min-h-screen transition-all duration-300 overflow-x-hidden">
```

**Pattern:**
- `pl-0`: No left padding on mobile (sidebar is hidden/off-screen)
- `md:pl-64`: Left padding equals sidebar width on desktop
- `pt-16`: Top padding equals header height (64px)
- `transition-all`: Smooth responsive transitions

### Content Container Padding (line 16)

```tsx
<div className="p-4 md:p-8 max-w-[1600px] mx-auto">
```

**Pattern:**
- Mobile: `p-4` (16px padding on all sides)
- Desktop: `md:p-8` (32px padding on all sides)
- `max-w-[1600px]`: Maximum width for readability on ultra-wide screens
- `mx-auto`: Centers content horizontally

### Complete Layout Structure (lines 9-21)

```tsx
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
```

**Z-Index Stack:**
1. Content: Default (auto)
2. Header: `z-40`
3. Sidebar Overlay: `z-[59]`
4. Sidebar: `z-[60]`

---

## Tailwind Breakpoints Reference

| Breakpoint | Min Width | CSS Media Query | Usage in Project |
|------------|-----------|-----------------|------------------|
| `sm` | 640px | `@media (min-width: 640px)` | Breadcrumb display toggle |
| `md` | 768px | `@media (min-width: 768px)` | Sidebar visibility, search bar, header offset |
| `lg` | 1024px | `@media (min-width: 1024px)` | Not heavily used in current layout |
| `xl` | 1280px | `@media (min-width: 1280px)` | Not heavily used in current layout |
| `2xl` | 1536px | `@media (min-width: 1536px)` | Not heavily used in current layout |

### Mobile-First Approach

All responsive classes follow mobile-first approach:
1. Base classes = Mobile styles
2. `md:`, `sm:` prefixes = Desktop/tablet overrides

Example:
```tsx
className="pl-0 md:pl-64"
// Mobile: 0 padding
// Desktop+: 256px padding
```

---

## Quick Reference Patterns

### Pattern 1: Element Hide/Show by Breakpoint
```tsx
{/* Hide on mobile, show on desktop */}
<div className="hidden md:block">...</div>

{/* Show on mobile, hide on desktop */}
<div className="block md:hidden">...</div>

{/* Hide on mobile, show on tablet+ */}
<div className="hidden sm:block">...</div>
```

### Pattern 2: Fixed Sidebar with Mobile Overlay
```tsx
{/* State */}
const [isMobileOpen, setIsMobileOpen] = useState(false);

{/* Overlay - mobile only */}
{isMobileOpen && (
  <div className="fixed inset-0 bg-black/60 md:hidden" onClick={closeHandler} />
)}

{/* Sidebar */}
<aside className={`
  fixed left-0 top-0 h-screen z-50 transition-transform
  ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'}
  md:translate-x-0
`}>
  {/* Sidebar content */}
</aside>
```

### Pattern 3: Header with Sidebar Offset
```tsx
<header className="
  fixed top-0 left-0 right-0 z-40
  md:left-64
  h-16
">
  {/* Header content */}
</header>
```

### Pattern 4: Main Content with Conditional Offset
```tsx
<main className="
  pt-16           {/* Header height */}
  pl-0 md:pl-64   {/* Sidebar offset: 0 mobile, 256px desktop */}
  min-h-screen
">
  <div className="p-4 md:p-8">
    {/* Page content */}
  </div>
</main>
```

---

## Related Documentation

- [Tailwind Breakpoints](../frontend/07-tailwind-breakpoints.md) - Detailed breakpoint guide
- [Mobile Patterns](../frontend/08-mobile-patterns.md) - Mobile-specific UI patterns
- [Grid Layouts](../frontend/10-grid-layouts.md) - Grid-based responsive layouts
