import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import Tooltip from './Tooltip';

// [JONGGA-006] 툴팁이 세 벌로 흩어져 있던 동안 시각이 서로 달랐다. 하나로 모으면서
// 그 차이를 size 로 흡수했으므로, 세 값이 실제로 다른 상자를 만드는지 여기서 고정한다.
//
// 근거: AUDIT-JONGGA §2.2
function 툴팁상자(size?: 'sm' | 'md' | 'lg') {
  const { container } = render(
    <Tooltip content="설명" size={size}>
      <i />
    </Tooltip>,
  );
  return container.querySelector('.absolute')!.className;
}

describe('Tooltip 의 size', () => {
  it('기본값은 작은 시각이다', () => {
    // 호출 69곳 가운데 52곳이 작은 시각을 쓴다. 기본값이 그쪽이라야 프롭을 붙일 곳이 적다.
    const cls = 툴팁상자();
    expect(cls).toContain('w-52');
    expect(cls).toContain('text-[10px]');
    expect(cls).toContain('text-center');
  });

  it('md 는 폭만 넓히고 나머지는 sm 과 같다', () => {
    const cls = 툴팁상자('md');
    expect(cls).toContain('w-64');
    expect(cls).toContain('text-[10px]');
    expect(cls).toContain('px-3');
  });

  it('lg 는 종전 공용 시각을 그대로 낸다', () => {
    const cls = 툴팁상자('lg');
    expect(cls).toContain('min-w-[260px]');
    expect(cls).toContain('text-xs');
    expect(cls).toContain('text-left');
    expect(cls).toContain('break-keep');
  });

  it('세 시각이 공유하는 것은 크기가 달라져도 남는다', () => {
    // 배경과 z-index 는 프리셋에 넣지 않았다. 셋이 같아야 하는 값이기 때문이다.
    for (const size of ['sm', 'md', 'lg'] as const) {
      const cls = 툴팁상자(size);
      expect(cls).toContain('bg-gray-900/95');
      expect(cls).toContain('z-[100]');
    }
  });
});
