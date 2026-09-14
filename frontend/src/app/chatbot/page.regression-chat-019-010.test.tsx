// Regression: [CHAT-019][CHAT-010] — 빠른 조회 도구 모음이 명령 목록을 가리고,
// 모바일 drawer가 화면 전환과 키보드 조작 뒤에 접근 불가능한 상태로 남던 문제.

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatbotPage from './page';

const SESSION_ID = 'sess-chat-019-010';
const SESSION_TITLE = '메뉴에서 선택할 대화';

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/chatbot/models') {
      return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
    }
    if (path === '/api/kr/chatbot/sessions') {
      return { sessions: [{ id: SESSION_ID, title: SESSION_TITLE, updated_at: '2026-09-14T00:00:00Z' }] };
    }
    if (path.startsWith('/api/kr/chatbot/history')) return { history: [] };
    return {};
  }),
}));

vi.mock('@/app/components/Sidebar', () => ({ default: () => null }));
vi.mock('@/app/components/SettingsModal', () => ({ default: () => null }));
vi.mock('@/app/components/PaperTradingModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: ({ children }: { children?: string }) => children ?? '' }));

function openMobileMenu(): HTMLButtonElement {
  const opener = screen.getByRole('button', { name: '메뉴 열기' });
  if (!(opener instanceof HTMLButtonElement)) {
    throw new Error('메뉴 열기 조작은 버튼이어야 합니다.');
  }
  fireEvent.click(opener);
  return opener;
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  localStorage.clear();
  vi.clearAllMocks();
});

describe('[CHAT-019] 챗봇 명령 목록과 빠른 조회', () => {
  it('명령 목록은 빠른 조회보다 앞에 쌓이고, 스크롤 가능한 최대 높이를 둔다', async () => {
    render(<ChatbotPage />);

    expect(await screen.findByRole('button', { name: '시장 현황' })).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText('메시지 입력...'), { target: { value: '/' } });

    const commandPopup = await screen.findByText('사용 가능한 명령어');
    const popupShell = commandPopup.parentElement;
    const quickToolbar = screen.getByRole('button', { name: '시장 현황' }).parentElement?.parentElement;

    expect(popupShell?.classList.contains('max-h-64')).toBe(true);
    expect(popupShell?.classList.contains('overflow-y-auto')).toBe(true);
    expect(popupShell?.classList.contains('z-40')).toBe(true);
    expect(quickToolbar?.classList.contains('absolute')).toBe(false);
  });

  it('실제 명령 범위에 맞춰 현재 세션과 내 대화·메모리를 구분해 설명한다', async () => {
    render(<ChatbotPage />);

    fireEvent.change(screen.getByPlaceholderText('메시지 입력...'), { target: { value: '/clear' } });

    expect(await screen.findByText('현재 세션 메시지 삭제')).toBeTruthy();
    expect(screen.getByText('내 대화와 메모리 프로필 삭제')).toBeTruthy();
  });
});

describe('[CHAT-010] 모바일 drawer 접근성', () => {
  it('접힌 탐색 메뉴를 inert로 만들어 Tab 대상에서 제외한다', async () => {
    render(<ChatbotPage />);
    await screen.findByRole('button', { name: SESSION_TITLE });
    openMobileMenu();

    fireEvent.click(screen.getByRole('button', { name: '메뉴' }));

    const navigation = screen.getByRole('link', { name: '대시보드 홈' }).parentElement?.parentElement;
    expect(navigation?.hasAttribute('inert')).toBe(true);
  });

  it('닫기와 Escape는 메뉴 열기 버튼으로 초점을 되돌린다', async () => {
    render(<ChatbotPage />);
    await screen.findByRole('button', { name: SESSION_TITLE });
    const opener = openMobileMenu();

    fireEvent.click(screen.getByRole('button', { name: '메뉴 닫기' }));
    await waitFor(() => expect(document.activeElement).toBe(opener));

    fireEvent.click(opener);
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it('확인 대화상자가 열리면 첫 Escape는 대화상자만 닫고 다음 Escape가 drawer를 닫는다', async () => {
    render(<ChatbotPage />);
    await screen.findByRole('button', { name: SESSION_TITLE });
    const opener = openMobileMenu();
    const deleteButtons = await screen.findAllByRole('button', { name: `${SESSION_TITLE} 삭제` });

    fireEvent.click(deleteButtons[0]);

    const confirmation = await screen.findByRole('dialog', { name: '대화 삭제' });
    const cancel = within(confirmation).getByRole('button', { name: '취소' });
    cancel.focus();
    fireEvent.keyDown(cancel, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '대화 삭제' })).toBeNull();
      expect(screen.queryByRole('button', { name: '메뉴 닫기' })).not.toBeNull();
    });

    const drawerClose = screen.getByRole('button', { name: '메뉴 닫기' });
    drawerClose.focus();
    fireEvent.keyDown(drawerClose, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '메뉴 닫기' })).toBeNull();
      expect(document.activeElement).toBe(opener);
    });
  });

  it('대화 항목 선택 뒤에도 메뉴 열기 버튼으로 초점을 되돌린다', async () => {
    render(<ChatbotPage />);
    const opener = openMobileMenu();
    const item = await screen.findAllByRole('button', { name: SESSION_TITLE });

    fireEvent.click(item[0]);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '메뉴 닫기' })).toBeNull();
      expect(document.activeElement).toBe(opener);
    });
  });

  it('lg 전환은 drawer만 닫고 숨겨지는 메뉴 열기 버튼에는 초점을 옮기지 않는다', async () => {
    render(<ChatbotPage />);
    await screen.findByRole('button', { name: SESSION_TITLE });
    const opener = openMobileMenu();
    const closeButton = screen.getByRole('button', { name: '메뉴 닫기' });
    closeButton.focus();

    act(() => {
      const desktopMediaQuery = window.matchMedia('(min-width: 1024px)');
      const desktopChange = new Event('change');
      Object.defineProperty(desktopChange, 'matches', { value: true });
      desktopMediaQuery.dispatchEvent(desktopChange);
    });

    expect(screen.queryByRole('button', { name: '메뉴 닫기' })).toBeNull();
    expect(document.activeElement).not.toBe(opener);
  });
});
