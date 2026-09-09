import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Sidebar from './Sidebar';
import ChatWidget from './ChatWidget';
import { getAuthHeaders } from './chatHelpers';

vi.mock('next/navigation', () => ({ usePathname: () => '/dashboard/kr' }));
vi.mock('next-auth/react', () => ({ useSession: () => ({ data: null, status: 'unauthenticated' }), signOut: vi.fn() }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false }) }));
vi.mock('./PaperTradingModal', () => ({ default: () => null }));
vi.mock('./SettingsModal', () => ({ default: ({ isOpen, onSave }: { isOpen: boolean; onSave: (name: string, email: string, persona: string) => Promise<void> }) => isOpen ? <button onClick={() => void onSave('검수', 'qa@example.test', '')}>합성 프로필 저장</button> : null }));

const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  fetchMock.mockImplementation(async () => new Response(JSON.stringify({ response: '합성 응답', remaining: 10 }), { headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('scrollTo', vi.fn());
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

function expectHeaders(url: string) {
  const request = fetchMock.mock.calls.find(([input]) => input === url);
  expect(request).toBeDefined();
  const headers = new Headers(request?.[1]?.headers);
  expect(headers.get('X-Session-Id')).toBe(getAuthHeaders()['X-Session-Id']);
  expect(headers.get('Content-Type')).toBe('application/json');
  expect(headers.has('X-User-Email')).toBe(false);
}

describe('FE-038 공통 브라우저 세션 헤더', () => {
  it('위젯 전송이 공용 헤더의 세션을 유지한다', async () => {
    render(<ChatWidget />);
    fireEvent.click(screen.getByRole('button', { name: 'AI 상담' }));
    fireEvent.change(screen.getByPlaceholderText("메시지를 입력하세요... (슬래시 커맨드 '/' 사용 가능)"), { target: { value: '합성 검수' } });
    fireEvent.click(screen.getByRole('button', { name: '보내기' }));
    await screen.findByText('합성 응답');
    expectHeaders('/api/kr/chatbot');
  });
  it('사이드바 프로필 저장과 감사 요청이 같은 공용 세션을 유지한다', async () => {
    render(<Sidebar />);
    act(() => { window.dispatchEvent(new Event('open-settings')); });
    fireEvent.click(screen.getByRole('button', { name: '합성 프로필 저장' }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === '/api/system/log-event')).toBe(true));
    expectHeaders('/api/kr/chatbot/profile');
    expectHeaders('/api/system/log-event');
  });
});
