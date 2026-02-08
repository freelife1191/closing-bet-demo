import React from 'react';

interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  className?: string; // Container className
  position?: 'top' | 'bottom';
  align?: 'left' | 'center' | 'right';
  as?: 'span' | 'div'; // Tag to render
}

export default function Tooltip({
  children,
  content,
  className = "",
  position = "top",
  align = "center",
  as: Component = 'span'
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
      <div className={`absolute ${alignClass} ${positionClass} min-w-[260px] w-max max-w-[320px] px-4 py-3 bg-gray-900/95 text-gray-200 text-xs font-medium rounded-xl opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-[100] border border-white/10 shadow-xl backdrop-blur-sm text-left leading-relaxed whitespace-normal break-keep`}>
        {content}
        <div className={`absolute ${arrowAlignClass} border-4 border-transparent ${arrowClass}`}></div>
      </div>
    </Component>
  );
}
