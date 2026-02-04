# Frontend Responsive Design Reference

이 문서는 프로젝트에 적용된 모든 반응형(Responsive) 디자인 패턴을 레퍼런스용으로 정리한 것입니다.

## 목차

| 파일 | 설명 |
|------|------|
| [01-layout-basics.md](./01-layout-basics.md) | 레이아웃 기본 패턴 (Sidebar, Header, Main) |
| [02-dashboard-layout.md](./02-dashboard-layout.md) | 대시보드 레이아웃 패턴 |
| [03-card-components.md](./03-card-components.md) | 카드 컴포넌트 반응형 패턴 |
| [04-table-components.md](./04-table-components.md) | 테이블 컴포넌트 반응형 패턴 |
| [05-modal-components.md](./05-modal-components.md) | 모달/팝업 반응형 패턴 |
| [06-chat-widget.md](./06-chat-widget.md) | 채팅 위젯 반응형 패턴 |
| [07-tailwind-breakpoints.md](./07-tailwind-breakpoints.md) | Tailwind CSS 브레이크포인트 가이드 |
| [08-mobile-patterns.md](./08-mobile-patterns.md) | 모바일 전용 패턴 (Overlay, Hamburger 등) |
| [09-typography-text.md](./09-typography-text.md) | 타이포그래피 반응형 패턴 |
| [10-grid-layouts.md](./10-grid-layouts.md) | 그리드 레이아웃 패턴 |

## 빠른 시작

### Tailwind CSS 기본 브레이크포인트

```css
/* Tailwind CSS 기본 설정 (tailwind.config.ts 참고) */
sm: 640px   /* Small devices (landscape phones) */
md: 768px   /* Medium devices (tablets) */
lg: 1024px  /* Large devices (desktops) */
xl: 1280px  /* Extra large devices */
2xl: 1536px /* Extra extra large devices */
```

### 기본 반응형 패턴 예시

```tsx
/* 1. 모바일 우선 (Mobile First) */
<div className="p-4 md:p-8"> {/* 모바일 4, 데스크탑 8 */}
  Content
</div>

/* 2. 방향 변경 (Flex Direction) */
<div className="flex flex-col md:flex-row gap-4">
  <div>Column on mobile, Row on desktop</div>
</div>

/* 3. 숨김/표시 (Hide/Show) */
<div className="hidden md:block">Only show on desktop</div>
<div className="block md:hidden">Only show on mobile</div>

/* 4. 그리드 열 변경 (Grid Columns) */
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
  Responsive grid
</div>

/* 5. 너비 제어 (Width) */
<div className="w-full md:w-1/2 lg:w-1/4">
  Responsive width
</div>
```

## 프로젝트 반응형 철학

1. **Mobile First**: 모바일 화면을 기본으로 설계하고, 점진적으로 데스크탑에 맞게 확장
2. **Breakpoint Consistency**: `sm`(640px), `md`(768px), `lg`(1024px)를 일관되게 사용
3. **Touch-Friendly**: 모바일에서 최소 44px의 터치 영역 확보
4. **Performance**: 불필요한 렌더링 방지, CSS transitions 활용

## 적용 방법

1. 각 문서 파일을 참고하여 필요한 패턴을 찾습니다.
2. 코드를 복사하여 새 프로젝트에 붙여넣습니다.
3. 프로젝트의 디자인 시스템에 맞게 색상, 간격 등을 조정합니다.
4. 실제 디바이스에서 테스트하여 동작을 확인합니다.

## 주의사항

- 모든 예시는 Tailwind CSS를 사용하고 있습니다.
- 프로젝트에 Tailwind CSS가 설치되어 있어야 합니다.
- 기본 브레이크포인트 값은 `tailwind.config.ts`에서 수정 가능합니다.
