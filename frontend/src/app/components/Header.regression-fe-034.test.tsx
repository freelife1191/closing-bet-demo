import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Header from './Header';

const location = vi.hoisted(() => ({ pathname: '/dashboard/kr/closing-bet' }));
vi.mock('next/navigation', () => ({ usePathname: () => location.pathname }));

describe('[FE-034] 공용 탐색 경로', () => {
  it.each([
    ['/dashboard/kr/closing-bet', ['홈', '대시보드', '국내 시장', '종가베팅']],
    ['/dashboard/kr/vcp', ['홈', '대시보드', '국내 시장', 'VCP 시그널']],
    ['/', ['홈']],
  ])('%s의 순서와 현재 위치를 전달한다', (pathname, names) => {
    location.pathname = pathname;
    render(<Header />);
    const nav = screen.getByRole('navigation', { name: '현재 위치' });
    const list = within(nav).getByRole('list');
    expect(list.tagName).toBe('OL');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(names.length);
    expect(within(nav).getByRole('link', { name: '홈' }).getAttribute('href')).toBe('/');
    expect(items.slice(1).map(item => item.textContent?.replace('/', '').trim())).toEqual(names.slice(1));
    expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
    expect(items.at(-1)?.getAttribute('aria-current')).toBe('page');
    expect(Array.from(nav.querySelectorAll('span')).filter(span => span.textContent === '/').every(span => span.getAttribute('aria-hidden') === 'true')).toBe(true);
  });
});
