import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatbotPage from './page';

const session = vi.hoisted(() => ({ useSession: vi.fn() }));

vi.mock('next-auth/react', () => ({ useSession: session.useSession }));
vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/chatbot/models') {
      return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
    }
    if (path === '/api/kr/chatbot/sessions') return { sessions: [] };
    return {};
  }),
}));
vi.mock('@/app/components/Sidebar', () => ({ default: () => null }));
vi.mock('@/app/components/SettingsModal', () => ({ default: () => null }));
vi.mock('@/app/components/ConfirmationModal', () => ({ default: () => null }));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/PaperTradingModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: ({ children }: { children?: string }) => children ?? '' }));

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  localStorage.clear();
  localStorage.setItem('user_profile', JSON.stringify({
    name: '저장된 이름', email: 'saved@example.com', persona: '저장된 페르소나',
  }));
  session.useSession.mockReturnValue({
    data: { user: { name: '세션 이름', email: 'session@example.com' } },
    status: 'authenticated',
  });
});

describe('[FE-022] 챗봇 사용자 표기', () => {
  it('인증 세션 이름을 표시하지만 저장된 프로필을 덮어쓰지 않는다', async () => {
    render(<ChatbotPage />);

    expect(await screen.findByText('안녕하세요, 세션 이름님')).toBeTruthy();
    expect(JSON.parse(localStorage.getItem('user_profile') as string)).toEqual({
      name: '저장된 이름', email: 'saved@example.com', persona: '저장된 페르소나',
    });
  });

  it.each(['null', 'not-json'])('손상된 로컬 캐시 %s는 기본 프로필로 정규화한다', async (cachedProfile) => {
    localStorage.setItem('user_profile', cachedProfile);
    session.useSession.mockReturnValue({ data: null, status: 'unauthenticated' });

    render(<ChatbotPage />);

    expect(await screen.findByText('안녕하세요, User님')).toBeTruthy();
  });
});
