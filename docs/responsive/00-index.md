# Responsive Design Reference

Quick navigation guide for the project's responsive design patterns and components.

## About This Project's Responsive Approach

This project uses **Tailwind CSS** with a **mobile-first** design philosophy. All components are built responsively from the ground up, ensuring optimal user experience across all device sizes.

### Key Principles

- **Mobile First**: Base styles target mobile, with breakpoints for larger screens
- **Touch-Friendly**: Minimum 44x44px touch targets on mobile
- **Performance-Oriented**: CSS transitions and minimal JavaScript
- **Consistent Breakpoints**: Standard Tailwind breakpoints across all components

## Quick Links

| Document | Description |
|----------|-------------|
| [Layout Basics](../frontend/01-layout-basics.md) | Sidebar, Header, Main layout patterns |
| [Dashboard Layout](../frontend/02-dashboard-layout.md) | Dashboard-specific layout structures |
| [Card Components](../frontend/03-card-components.md) | KPI cards, stat cards, score circles |
| [Table Components](../frontend/04-table-components.md) | Responsive tables with mobile patterns |
| [Modal Components](../frontend/05-modal-components.md) | Modals, bottom sheets, dialogs |
| [Chat Widget](../frontend/06-chat-widget.md) | Floating chat widget responsive patterns |
| [Tailwind Breakpoints](../frontend/07-tailwind-breakpoints.md) | Complete breakpoint reference |
| [Mobile Patterns](../frontend/08-mobile-patterns.md) | Mobile-specific UI patterns |
| [Typography](../frontend/09-typography-text.md) | Responsive text and font sizing |
| [Grid Layouts](../frontend/10-grid-layouts.md) | Grid system and responsive layouts |

## Tailwind CSS Breakpoints

This project uses standard Tailwind CSS breakpoints:

| Breakpoint | Min Width | Target Devices |
|------------|-----------|----------------|
| (base) | 0px | Mobile phones |
| `sm:` | 640px | Small tablets, landscape phones |
| `md:` | 768px | Tablets portrait |
| `lg:` | 1024px | Small desktops, laptops |
| `xl:` | 1280px | Desktops |
| `2xl:` | 1536px | Large screens |

## Quick Reference

### Responsive Class Patterns

```tsx
{/* Mobile First - Base styles apply to mobile */}
<div className="p-4 md:p-8">
  {/* Mobile: 16px padding, Desktop: 32px */}
</div>

{/* Direction Change */}
<div className="flex flex-col md:flex-row gap-4">
  {/* Vertical on mobile, horizontal on desktop */}
</div>

{/* Hide/Show */}
<div className="hidden md:block">Desktop only</div>
<div className="block md:hidden">Mobile only</div>

{/* Grid Columns */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
  {/* 1 col mobile, 2 cols tablet, 4 cols desktop */}
</div>
```

### Common Component Patterns

| Component | Mobile Behavior | Desktop Behavior |
|-----------|----------------|------------------|
| **Sidebar** | Hidden, slides in with overlay | Always visible, fixed left |
| **Header** | Full width, simplified | Offset by sidebar width |
| **Cards** | 1 column grid | 2-4 column grid |
| **Tables** | Horizontal scroll or card view | Full width, no scroll |
| **Modals** | Full width or bottom sheet | Centered, max-width |
| **Chat Widget** | Floating bottom-right | Floating bottom-right, larger |

### Mobile-Only Patterns

- **Sidebar Overlay**: `fixed inset-0 bg-black/60 backdrop-blur-sm`
- **Bottom Sheet**: `fixed bottom-0 rounded-t-3xl`
- **Touch Targets**: `min-w-[44px] min-h-[44px]`
- **Safe Area**: `pb-safe` for iOS home indicator
- **Horizontal Scroll**: `overflow-x-auto snap-x -webkit-overflow-scrolling:touch`

## Getting Started

1. **Choose your pattern**: Browse the documentation above for the component you need
2. **Copy the code**: All examples are production-ready
3. **Customize**: Adjust colors, spacing, and breakpoints as needed
4. **Test**: Verify on actual devices at all breakpoint sizes

## File Locations

```
docs/
├── frontend/
│   ├── 00-index.md              # Frontend documentation index
│   ├── 01-layout-basics.md      # Layout patterns
│   ├── 02-dashboard-layout.md   # Dashboard layouts
│   ├── 03-card-components.md    # Card components
│   ├── 04-table-components.md   # Table components
│   ├── 05-modal-components.md   # Modal patterns
│   ├── 06-chat-widget.md        # Chat widget
│   ├── 07-tailwind-breakpoints.md # Breakpoint reference
│   ├── 08-mobile-patterns.md    # Mobile patterns
│   ├── 09-typography-text.md    # Typography
│   └── 10-grid-layouts.md       # Grid layouts
└── responsive/
    └── 00-index.md              # This file
```
