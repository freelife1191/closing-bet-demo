# Page-Level Responsive Design Patterns

Reference guide for implementing responsive layouts in landing pages and dashboards.

## Table of Contents
1. [Landing Page Patterns](#landing-page-patterns)
2. [Dashboard Overview Patterns](#dashboard-overview-patterns)
3. [Button Group Responsive](#button-group-responsive)
4. [Date Picker Responsive](#date-picker-responsive)

---

## Landing Page Patterns

**Source**: `frontend/src/app/page.tsx`

### Hero Section Responsive

**Lines 39-86**: Full hero section with mobile-first approach.

```tsx
<section className="relative pt-20 pb-32 px-6 overflow-hidden">
  {/* Background Glow - Decorative elements */}
  <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none"></div>

  <div className="max-w-4xl mx-auto text-center relative z-10">
    {/* Status Badge - Always visible */}
    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 text-xs text-blue-400 font-bold mb-8">
      <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
      System Operational: v2.0 Released
    </div>

    {/* Main Headline - Typography scaling */}
    <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-8 leading-tight">
      한국 주식 시장을 위한<br />
      <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-rose-400">
        AI 기반 퀀트 분석 솔루션
      </span>
    </h1>

    {/* Description - Scaled for readability */}
    <p className="text-xl text-gray-400 mb-12 max-w-2xl mx-auto leading-relaxed">
      VCP 패턴 인식, 기관/외국인 수급 추적, 그리고 <span className="text-indigo-400 font-semibold">Gemini & GPT Dual AI 엔진</span>이 결합된 올인원 주식 분석 패키지입니다.
    </p>

    {/* CTA Buttons - Stack on mobile, row on desktop */}
    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
      <Link
        href="/dashboard/kr"
        className="w-full sm:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2"
      >
        <i className="fas fa-terminal"></i>
        설치 가이드
      </Link>
      <Link
        href="/dashboard/kr"
        className="w-full sm:w-auto px-8 py-4 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2"
      >
        <i className="fas fa-search"></i>
        분석 엔진 살펴보기
      </Link>
    </div>
```

**Key Patterns**:
- `text-5xl md:text-7xl` - Typography scales from mobile to desktop
- `flex-col sm:flex-row` - Buttons stack on mobile, row on small+ screens
- `w-full sm:w-auto` - Full width buttons on mobile only
- `max-w-2xl mx-auto` - Content constrained with auto centering

### Navigation Responsive

**Lines 13-35**: Fixed header with hidden elements on mobile.

```tsx
<nav className="fixed top-0 left-0 right-0 z-50 bg-[#0E1117]/80 backdrop-blur-md border-b border-white/5">
  <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
    {/* Logo - Always visible */}
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
        <i className="fas fa-chart-line text-white text-sm"></i>
      </div>
      <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
        KR Market Package
      </span>
    </div>

    {/* Nav Links - Hidden on mobile */}
    <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-400">
      <a href="#features" className="hover:text-white transition-colors">기능</a>
      <a href="#architecture" className="hover:text-white transition-colors">아키텍처</a>
      <a href="#ai-analysis" className="hover:text-white transition-colors">AI 분석</a>
    </div>

    {/* CTA Button - Always visible */}
    <Link
      href="/dashboard/kr"
      className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-bold rounded-full transition-all border border-white/10"
    >
      Get Started
    </Link>
  </div>
</nav>
```

**Key Patterns**:
- `hidden md:flex` - Navigation links hidden on mobile, visible at `md` (768px) breakpoint
- Fixed header with `pt-16` offset on main content
- Mobile: Logo + CTA only
- Desktop+: Logo + Nav Links + CTA

### Feature Grid Layouts

**Lines 96-150, 162-211**: Three-column responsive grids.

```tsx
{/* Architecture Section - 3 columns */}
<div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
  {/* Card 1 */}
  <div className="relative z-10 p-8 rounded-3xl bg-[#0E1117] border border-white/10 hover:border-indigo-500/30 transition-all group">
    {/* Content */}
  </div>
  {/* Card 2, 3... */}
</div>

{/* Features Section - 3 columns */}
<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
  {/* Feature Cards */}
</div>
```

**Key Patterns**:
- `grid-cols-1 md:grid-cols-3` - Single column on mobile, 3 columns on desktop
- `gap-8` / `gap-6` - Consistent spacing between cards
- Cards use `p-8` padding for breathing room

### Two-Column Split Sections

**Lines 219-249**: Side-by-side content with stacking on mobile.

```tsx
<div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
  <div>
    <div className="w-12 h-12 rounded-xl bg-indigo-500 flex items-center justify-center mb-4">
      <i className="fas fa-brain text-2xl text-white"></i>
    </div>
    <h2 className="text-3xl font-bold mb-2">Dual AI Analysis System</h2>
    <p className="text-gray-400">최신 LLM 모델들의 상호 검증을 통한 신뢰도 높은 분석</p>
  </div>
  <div className="flex items-center gap-2">
    <span className="px-3 py-1 bg-purple-500/20 text-purple-400 text-xs font-bold rounded-full border border-purple-500/30">DUAL ENGINE</span>
  </div>
</div>
```

**Key Patterns**:
- `flex-col md:flex-row` - Vertical stack on mobile, horizontal on desktop
- `md:items-center` - Vertically center items when in row layout
- `gap-6` - Consistent spacing in both orientations

### Tab Interface Responsive

**Lines 260-279**: Button group tabs that adapt to screen size.

```tsx
<div className="inline-flex p-1 rounded-xl bg-[#1c1c1e] border border-white/10 mb-12">
  <button
    className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
      activeTab === 'vcp'
        ? 'bg-[#2c2c2e] text-white shadow-lg'
        : 'text-gray-500 hover:text-gray-300'
    }`}
  >
    VCP 분석
  </button>
  <button /* similar pattern */>수급 점수</button>
  <button /* similar pattern */>종가베팅 V2</button>
</div>
```

**Key Patterns**:
- `inline-flex` - Container shrinks to fit content
- No explicit responsive classes needed - buttons adapt naturally
- `px-6 py-2` - Touch-friendly tap targets (44px min height)

### Tech Stack Logo Grid

**Lines 78-84**: Flexible logo grid.

```tsx
<div className="mt-16 pt-8 border-t border-white/5 flex flex-wrap justify-center gap-8 md:gap-12 opacity-50 grayscale hover:grayscale-0 transition-all duration-500">
  <div className="flex items-center gap-2 text-sm font-semibold">
    <i className="fab fa-python text-xl"></i> Python
  </div>
  <div className="flex items-center gap-2 text-sm font-semibold">
    <i className="fab fa-react text-xl"></i> Next.js
  </div>
  {/* More logos... */}
</div>
```

**Key Patterns**:
- `flex-wrap` - Items wrap to multiple lines on small screens
- `justify-center` - Centered in both orientations
- `gap-8 md:gap-12` - More spacing on desktop

---

## Dashboard Overview Patterns

**Source**: `frontend/src/app/dashboard/kr/page.tsx`

### Page Header Layout

**Lines 250-369**: Complex header with controls.

```tsx
<div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
  {/* Left: Title Section */}
  <div>
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-rose-500/20 bg-rose-500/5 text-xs text-rose-400 font-medium mb-4">
      <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
      KR 마켓 알파
    </div>
    <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
      스마트머니 <span className="text-transparent bg-clip-text bg-gradient-to-r from-rose-400 to-amber-400">추적</span>
    </h2>
    <p className="text-gray-400 text-lg">VCP 패턴 & 기관/외국인 수급 추적</p>
  </div>

  {/* Right: Controls Section */}
  <div className="flex flex-col items-end gap-2">
    {/* Mode Toggle Button Group */}
    <div className="flex items-center gap-3 bg-[#1c1c1e] p-1 rounded-lg border border-white/10">
      <button className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
        useTodayMode
          ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
          : 'text-gray-400 hover:text-white hover:bg-white/5'
      }`}>
        <i className="fas fa-clock mr-1.5"></i> 실시간
      </button>
      <button className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
        !useTodayMode
          ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/20'
          : 'text-gray-400 hover:text-white hover:bg-white/5'
      }`}>
        <i className="far fa-calendar-alt mr-1.5"></i> 날짜 지정
      </button>
    </div>

    {/* Status Info */}
    <div className="flex flex-col items-end gap-1 px-1">
      <div className="text-[10px] text-gray-500 font-medium flex items-center gap-1.5">
        {/* Interval selector */}
      </div>
    </div>

    {/* Date Picker - Conditional */}
    {!useTodayMode && (
      <div className="flex items-center gap-2 animate-in fade-in slide-in-from-top-1 mt-1">
        <input
          type="date"
          value={targetDate}
          max={new Date().toISOString().split('T')[0]}
          onChange={(e) => setTargetDate(e.target.value)}
          className="bg-[#1c1c1e] border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
        />
      </div>
    )}
  </div>
</div>
```

**Key Patterns**:
- `flex-col md:flex-row` - Stack on mobile, side-by-side on desktop
- `md:items-end` - Align bottom when horizontal
- `items-end` - Right section aligns to end
- Conditional rendering with animation for date picker

### Market Gate Section

**Lines 372-463**: Asymmetric grid layout.

```tsx
<section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
  {/* Gate Score Card - 1/4 width on desktop */}
  <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group">
    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity text-rose-500">
      <i className="fas fa-chart-line text-4xl"></i>
    </div>
    <h3 className="text-sm font-bold text-gray-400 mb-4 flex items-center gap-2 relative z-10">
      KR Market Gate
      <Tooltip content="..." position="bottom" align="left">
        <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
      </Tooltip>
      <div className="hidden lg:block ml-auto w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></div>
    </h3>
    {/* Circular progress indicator */}
  </div>

  {/* Sector Grid - 3/4 width on desktop */}
  <div className="lg:col-span-3 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <div className="flex items-center justify-between mb-4">
      <h3 className="text-sm font-bold text-gray-400 flex items-center gap-2">
        KOSPI 200 Sector Index
      </h3>
      <div className="flex items-center gap-4 text-[10px] font-bold text-gray-500 uppercase tracking-tighter">
        {/* Legend items */}
      </div>
    </div>
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      {/* Sector cards */}
    </div>
  </div>
</section>
```

**Key Patterns**:
- `grid-cols-1 lg:grid-cols-4` - 4-column grid on large screens
- `lg:col-span-1` / `lg:col-span-3` - 1:3 ratio on desktop
- `hidden lg:block` - Status indicator only on desktop
- Nested responsive grid for sectors: `grid-cols-2 sm:grid-cols-3 md:grid-cols-4`

### KPI Cards Grid

**Lines 466-567**: Four-card performance metrics.

```tsx
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  {/* Card 1: Today's Signals */}
  <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-rose-500/30 transition-all">
    <div className="absolute top-0 right-0 w-20 h-20 bg-rose-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
    <div className="flex items-center gap-2 mb-1">
      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Today&apos;s Signals</div>
      <Tooltip content="..." position="bottom" align="left">
        <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
      </Tooltip>
    </div>
    <div className="text-3xl font-black text-white group-hover:text-rose-400 transition-colors">
      {loading ? '--' : signalsData?.signals?.length ?? 0}
    </div>
    <div className="mt-2 text-xs text-gray-500">VCP + 외국인 순매수</div>
  </div>

  {/* Card 2, 3, 4 - Similar pattern */}
</div>
```

**Key Patterns**:
- `grid-cols-1 md:grid-cols-4` - Full width on mobile, 4 columns on desktop
- Consistent card structure with gradient glow effects
- Hover states for interactivity
- Decorative blur circles for visual interest

### Market Indices/Commodities/Crypto Grids

**Lines 571-778**: Three sections with similar card patterns.

```tsx
{/* Section Header */}
<div className="flex items-center justify-between mb-3">
  <h3 className="text-base font-bold text-white flex items-center gap-2">
    <span className="w-1 h-5 bg-rose-500 rounded-full"></span>
    Market Indices
    <Tooltip content="주요 국내외 증시 지수 현황입니다.">
      <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-xs"></i>
    </Tooltip>
  </h3>
</div>

{/* Cards Grid - 2 columns on mobile, 4 on desktop */}
<div className="grid grid-cols-2 md:grid-cols-4 gap-4">
  {/* Individual Card */}
  <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
    <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KOSPI</div>
    <div className="flex items-end gap-2">
      <span className="text-xl font-black text-white">
        {loading ? '--' : gateData?.kospi_close?.toLocaleString() ?? '--'}
      </span>
      {gateData && (
        <span className={`text-xs font-bold mb-0.5 ${gateData.kospi_change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
          <i className={`fas fa-caret-${gateData.kospi_change_pct >= 0 ? 'up' : 'down'} mr-0.5`}></i>
          {gateData.kospi_change_pct >= 0 ? '+' : ''}{gateData.kospi_change_pct?.toFixed(1)}%
        </span>
      )}
    </div>
  </div>
  {/* More cards... */}
</div>
```

**Key Patterns**:
- `grid-cols-2 md:grid-cols-4` - 2 columns on mobile, 4 on desktop
- Consistent card padding: `p-4`
- `items-end` alignment for price + percentage
- Color-coded percentage indicators

---

## Button Group Responsive

### Toggle Button Group Pattern

**Lines 263-284, 357-367**: Segmented control for mode switching.

```tsx
{/* Primary Toggle - Realtime vs Date Picker */}
<div className="flex items-center gap-3 bg-[#1c1c1e] p-1 rounded-lg border border-white/10">
  <button
    onClick={() => { setUseTodayMode(true); setTargetDate(''); }}
    className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
      useTodayMode
        ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
        : 'text-gray-400 hover:text-white hover:bg-white/5'
    }`}
  >
    <i className="fas fa-clock mr-1.5"></i>
    실시간
  </button>
  <button
    onClick={() => { setUseTodayMode(false); if (!targetDate) setTargetDate(getLastBusinessDay()); }}
    className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
      !useTodayMode
        ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/20'
        : 'text-gray-400 hover:text-white hover:bg-white/5'
    }`}
  >
    <i className="far fa-calendar-alt mr-1.5"></i>
    날짜 지정
  </button>
</div>
```

### Tab Group Pattern (Landing Page)

**Lines 260-279**: Three-tab content switcher.

```tsx
<div className="inline-flex p-1 rounded-xl bg-[#1c1c1e] border border-white/10 mb-12">
  <button
    onClick={() => setActiveTab('vcp')}
    className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
      activeTab === 'vcp'
        ? 'bg-[#2c2c2e] text-white shadow-lg'
        : 'text-gray-500 hover:text-gray-300'
    }`}
  >
    VCP 분석
  </button>
  <button
    onClick={() => setActiveTab('supply')}
    className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
      activeTab === 'supply'
        ? 'bg-[#2c2c2e] text-white shadow-lg'
        : 'text-gray-500 hover:text-gray-300'
    }`}
  >
    수급 점수
  </button>
  <button
    onClick={() => setActiveTab('closing')}
    className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${
      activeTab === 'closing'
        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
        : 'text-gray-500 hover:text-gray-300'
    }`}
  >
    종가베팅 V2
  </button>
</div>
```

**Key Patterns**:
- `inline-flex` - Container fits content
- `px-6 py-2` - Minimum 44px touch target
- Active state: solid background + shadow
- Inactive state: subtle hover effect
- No explicit responsive classes needed

---

## Date Picker Responsive

### Conditional Date Input

**Lines 357-367**: Date picker that appears based on mode.

```tsx
{!useTodayMode && (
  <div className="flex items-center gap-2 animate-in fade-in slide-in-from-top-1 mt-1">
    <input
      type="date"
      value={targetDate}
      max={new Date().toISOString().split('T')[0]} // Prevent future dates
      onChange={(e) => setTargetDate(e.target.value)}
      className="bg-[#1c1c1e] border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
    />
  </div>
)}
```

**Key Patterns**:
- Conditional rendering: only show when date mode is active
- `animate-in fade-in slide-in-from-top-1` - Smooth entrance animation
- `max` attribute prevents future date selection
- Native HTML5 date input - no responsive styling needed
- Dark theme styling with focus state

### Custom Interval Selector

**Lines 290-343**: Custom input with dropdown hybrid.

```tsx
{/* Custom value mode - number input */}
{![1, 5, 10, 15, 30, 60].includes(updateInterval) ? (
  <div className="flex items-center gap-1 ml-0.5">
    <input
      type="number"
      min="1"
      max="1440"
      value={updateInterval}
      onChange={(e) => {
        const val = Number(e.target.value);
        if (val >= 1 && val <= 1440) {
          handleIntervalChange(val);
        }
      }}
      className="w-12 bg-[#1c1c1e] border border-gray-700 rounded text-[10px] px-1.5 py-0.5 text-center text-blue-400 focus:outline-none focus:border-blue-500 [appearance:textfield] [&::-webkit-outer-spin-button]:opacity-100 [&::-webkit-inner-spin-button]:opacity-100"
    />
    <span className="text-[10px] text-gray-500">분</span>
    <button
      onClick={() => handleIntervalChange(5)}
      className="text-[9px] text-gray-600 hover:text-gray-400 ml-1"
      title="Reset to default (5min)"
    >
      <i className="fas fa-times"></i>
    </button>
  </div>
) : (
  /* Dropdown mode */
  <select
    value={updateInterval}
    onChange={(e) => {
      const val = e.target.value;
      if (val === 'custom') {
        handleIntervalChange(2);
      } else {
        handleIntervalChange(Number(val));
      }
    }}
    className="bg-transparent border-none text-[10px] font-bold text-gray-400 hover:text-blue-400 focus:ring-0 cursor-pointer appearance-none text-right pr-0 ml-0.5 transition-colors outline-none"
    style={{ WebkitAppearance: 'none', MozAppearance: 'none' }}
  >
    <option value={1} className="bg-[#1c1c1e] text-gray-300">1분</option>
    <option value={5} className="bg-[#1c1c1e] text-gray-300">5분</option>
    {/* More options... */}
    <option value="custom" className="bg-[#1c1c1e] text-gray-300">직접입력...</option>
  </select>
)}
```

**Key Patterns**:
- Hybrid UI: dropdown or custom number input
- Form validation with min/max constraints
- Custom spinner visibility with Tailwind arbitrary properties
- Style reset for native appearance
- Reset button to return to default

---

## Quick Reference

### Common Responsive Classes

| Pattern | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Text Scale | `text-4xl` | - | `md:text-5xl` |
| Grid Columns | `grid-cols-1` | `sm:grid-cols-2` | `md:grid-cols-4` |
| Flex Direction | `flex-col` | - | `md:flex-row` |
| Hide/Show | `hidden` | - | `md:block` |
| Width | `w-full` | - | `sm:w-auto` |
| Gap | `gap-4` | - | `md:gap-8` |

### Breakpoint Reference

| Breakpoint | Min Width | Use Case |
|------------|-----------|----------|
| `sm` | 640px | Small tablets, landscape phones |
| `md` | 768px | Tablets |
| `lg` | 1024px | Small laptops |
| `xl` | 1280px | Desktops |

### Touch Target Minimums

- Buttons: `px-6 py-2` (minimum 44px height)
- Inputs: `px-3 py-1.5` (minimum 44px height)
- Icon buttons: `p-1.5` + adequate icon size

---

## Best Practices

1. **Mobile-First Approach**: Start with mobile styles, use `md:` and above for desktop overrides
2. **Touch-Friendly Targets**: Ensure minimum 44x44px tap targets
3. **Content Hierarchy**: Use responsive typography to maintain hierarchy across screen sizes
4. **Conditional Rendering**: Show/hide complex UI elements based on screen size
5. **Flexible Layouts**: Prefer flex/grid over fixed widths
6. **Consistent Spacing**: Use `gap-*` utilities instead of manual margins
7. **Text Wrapping**: Allow natural text wrapping with `max-w-*` constraints
