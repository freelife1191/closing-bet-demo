import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Header from './Header';
import ChatWidget from './ChatWidget';
const route = vi.hoisted(() => ({ path: '/dashboard/kr' }));
vi.mock('next/navigation', () => ({ usePathname: () => route.path }));
beforeEach(() => { route.path = '/dashboard/kr'; Element.prototype.scrollIntoView = vi.fn(); });

describe('header actions and chat access', () => {
  it('removes nonfunctional search while preserving menu and settings events', () => {
    const menu = vi.fn(); const settings = vi.fn();
    window.addEventListener('sidebar-toggle', menu); window.addEventListener('open-settings', settings);
    render(<Header />);
    expect(screen.queryByRole('button', { name: '검색' })).toBeNull();
    expect(screen.queryByPlaceholderText('Search markets, tickers...')).toBeNull();
    expect(screen.queryByText('⌘K')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '메뉴 열고 닫기' }));
    fireEvent.click(screen.getByRole('button', { name: '설정 열기' }));
    expect(menu).toHaveBeenCalledTimes(1); expect(settings).toHaveBeenCalledTimes(1);
    window.removeEventListener('sidebar-toggle', menu); window.removeEventListener('open-settings', settings);
  });
  it.each(['/dashboard/kr', '/'])('has one chat launcher and restores focus on close at %s', (path) => {
    route.path = path;
    render(<><Header /><ChatWidget /></>);
    const launcher = screen.getByRole('button', { name: 'AI 상담' });
    expect(screen.queryByText('궁금한 건 채팅으로 문의하세요')).toBeNull();
    launcher.focus(); fireEvent.click(launcher);
    expect(launcher.getAttribute('aria-expanded')).toBe('true');
    const close = screen.getByRole('button', { name: 'AI 상담 닫기' });
    close.focus(); fireEvent.click(close);
    expect(launcher.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(launcher);
  });
  it('keeps the dedicated chatbot page free of a second widget', () => {
    route.path = '/chatbot'; render(<ChatWidget />);
    expect(screen.queryByRole('button', { name: 'AI 상담' })).toBeNull();
  });
});
