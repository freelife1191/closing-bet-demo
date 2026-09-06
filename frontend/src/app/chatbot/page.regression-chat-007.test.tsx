// Regression: [CHAT-007] — 사이드바 대화 항목을 키보드로 열 수 없고 삭제와 구분되지 않던 문제
// Found by /qa-only on 2026-09-05 ([CHAT-003]·[CHAT-004]·[CHAT-016]·[CHAT-017] 사이클)
//
// 대화 항목은 `div` 에 `onClick` 만 달려 있어 Tab 으로 닿을 수 없었고, 그 안에 이름 없는
// 삭제 `button` 이 중첩되어 있었다. 접근성 트리에는 이름 없는 버튼만 보여 대화를 여는
// 조작과 되돌릴 수 없는 삭제가 똑같이 보였다. 이제 항목은 제목을 이름으로 가진 버튼이고,
// 삭제는 「<제목> 삭제」라는 이름의 형제 버튼이다. 입력 영역의 아이콘 전용 버튼도 이름을 갖는다.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchAPI } from '@/lib/api';

import ChatbotPage from './page';

const SESSION_ID = 'sess-a11y-001';
const SESSION_TITLE = '삼성전자 수급 질문';

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/chatbot/models') {
      return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
    }
    if (path === '/api/kr/chatbot/sessions') {
      return {
        sessions: [{ id: SESSION_ID, title: SESSION_TITLE, updated_at: '2026-09-05T00:00:00Z' }],
      };
    }
    if (path.startsWith('/api/kr/chatbot/history')) {
      return { history: [] };
    }
    return {};
  }),
}));

vi.mock('@/app/components/Sidebar', () => ({ default: () => null }));
vi.mock('@/app/components/SettingsModal', () => ({ default: () => null }));
// 삭제 확인 모달은 열렸는지만 보면 되므로 제목만 그린다.
vi.mock('@/app/components/ConfirmationModal', () => ({
  default: ({ isOpen, title }: { isOpen: boolean; title: string }) =>
    isOpen ? <div role="dialog">{title}</div> : null,
}));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/PaperTradingModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({
  default: ({ children }: { children?: string }) => children ?? '',
}));

const historyCalls = () =>
  vi.mocked(fetchAPI).mock.calls.map(([path]) => String(path)).filter((p) => p.startsWith('/api/kr/chatbot/history'));

describe('ChatbotPage - 사이드바 대화 항목의 키보드 접근성', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('대화 항목은 제목을 이름으로 가진 버튼이고, 누르면 그 대화의 기록을 요청한다', async () => {
    render(<ChatbotPage />);

    const item = await screen.findByRole('button', { name: SESSION_TITLE });
    expect(historyCalls()).toHaveLength(0);

    fireEvent.click(item);

    await waitFor(() => {
      expect(historyCalls()).toEqual([`/api/kr/chatbot/history?session_id=${SESSION_ID}`]);
    });
    expect(item.getAttribute('aria-current')).toBe('true');
  });

  it('삭제는 「<제목> 삭제」 이름의 형제 버튼이고, 누르면 대화를 열지 않고 확인 모달만 띄운다', async () => {
    render(<ChatbotPage />);

    const item = await screen.findByRole('button', { name: SESSION_TITLE });
    const remove = screen.getByRole('button', { name: `${SESSION_TITLE} 삭제` });
    expect(remove.parentElement).toBe(item.parentElement);

    fireEvent.click(remove);

    expect((await screen.findByRole('dialog')).textContent).toContain('대화 삭제');
    expect(historyCalls()).toHaveLength(0);
  });

  it('아이콘 전용 버튼이 접근 가능한 이름을 갖고, 문서에 중첩된 버튼이 없다', async () => {
    render(<ChatbotPage />);
    await screen.findByRole('button', { name: SESSION_TITLE });

    for (const name of ['메뉴 열기', '파일 첨부', '음성 입력', '프로필 설정 열기', '스마트머니봇']) {
      expect(screen.getByRole('button', { name })).not.toBeNull();
    }

    // 보내기 버튼은 입력이 있을 때만 그려진다. 입력만 하고 보내지는 않는다.
    fireEvent.change(screen.getByPlaceholderText('메시지 입력...'), { target: { value: '삼성전자' } });
    expect(screen.getByRole('button', { name: '보내기' })).not.toBeNull();

    // 버튼 안에 버튼이 있으면 HTML 로도 무효하고 보조 기술도 둘을 구분하지 못한다.
    expect(document.querySelector('button button')).toBeNull();
  });
});
