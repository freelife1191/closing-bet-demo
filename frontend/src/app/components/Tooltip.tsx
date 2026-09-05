import React from 'react';

// [JONGGA-006] 종전에는 같은 컴포넌트가 세 벌 있었다. 이 파일과
// dashboard/kr/closing-bet/page.tsx 와 dashboard/data-status/page.tsx 가 저마다
// 정의했고 시각이 서로 달랐다. 셋을 여기로 모으면서 그 차이를 size 로 흡수했다.
//
// 크기만 바뀌는 것이 아니라 안쪽 여백과 글자 크기와 모서리와 정렬이 함께 움직인다.
// 짧은 힌트를 띄우는 작은 툴팁은 가운데 정렬이 읽기 좋고, 여러 줄 설명을 담는 큰
// 툴팁은 왼쪽 정렬에 낱말 단위 줄바꿈이 필요하기 때문이다. 그래서 개별 프롭으로
// 쪼개지 않고 프리셋 하나로 둔다.
const SIZE_CLASSES = {
  sm: 'w-52 max-w-[220px] px-3 py-2 text-[10px] rounded-lg text-center',
  md: 'w-64 max-w-[280px] px-3 py-2 text-[10px] rounded-lg text-center',
  lg: 'min-w-[260px] w-max max-w-[320px] px-4 py-3 text-xs rounded-xl text-left break-keep',
} as const;

interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  className?: string; // Container className
  position?: 'top' | 'bottom';
  align?: 'left' | 'center' | 'right';
  as?: 'span' | 'div'; // Tag to render
  size?: keyof typeof SIZE_CLASSES;
}

export default function Tooltip({
  children,
  content,
  className = "",
  position = "top",
  align = "center",
  as: Component = 'span',
  size = 'sm'
}: TooltipProps) {
  const positionClass = position === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2';
  const arrowClass = position === 'bottom' ? 'bottom-full border-b-gray-900/95 -mb-1' : 'top-full border-t-gray-900/95 -mt-1';

  // Alignment classes
  let alignClass = 'left-1/2 -translate-x-1/2'; // Default center
  let arrowAlignClass = 'left-1/2 -translate-x-1/2';

  if (align === 'left') {
    alignClass = 'left-0';
    arrowAlignClass = 'left-4';
  } else if (align === 'right') {
    alignClass = 'right-0';
    arrowAlignClass = 'right-4';
  }

  // Base classes: Default to inline-flex for span, but allow full control via className
  // If className contains 'flex' or 'block', we trust it.
  // If not, we add 'inline-flex items-center' as default for span usage (like icons).
  // For div usage (cards), likely 'block' or 'flex' based on className.
  const baseClasses = `relative group/tooltip ${className.includes('flex') || className.includes('block') ? '' : 'inline-flex items-center'}`;

  return (
    <Component className={`${baseClasses} ${className}`}>
      {children}
      <div className={`absolute ${alignClass} ${positionClass} ${SIZE_CLASSES[size]} bg-gray-900/95 text-gray-200 font-medium opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-[100] border border-white/10 shadow-xl backdrop-blur-sm leading-relaxed whitespace-normal`}>
        {content}
        <div className={`absolute ${arrowAlignClass} border-4 border-transparent ${arrowClass}`}></div>
      </div>
    </Component>
  );
}
