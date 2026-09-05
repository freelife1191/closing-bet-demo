// Regression: [CHAT-016] — 소유자가 바뀐 뒤 남은 세션 ID 로 화면이 잠기던 문제
// Found by /qa on 2026-09-05
// Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-05.md
//
// `[CHAT-016]` 이 히스토리 조회에 소유자 검사를 넣으면서, 남의 세션을 부르면 404 가
// 돌아온다. 그런데 화면은 마지막으로 본 세션 ID 를 localStorage 에 남겨 두고 다음
// 방문에서 그것을 복원한다. 소유자가 바뀌면(로그인, 로그아웃, 브라우저 세션 ID
// 재발급) 그 ID 는 더 이상 내 것이 아니므로 404 를 받는다.
//
// 종전 구현은 그 404 를 다른 실패와 같이 다루어 「⚠️ 대화 기록을 불러오는데
// 실패했습니다.」를 띄우고 멈췄다. 추천 질문 카드도 인사말도 사라져 사용자는 새 대화를
// 시작할 실마리를 잃었다. 이제는 죽은 세션 ID 를 버리고 새 대화 상태로 넘어간다.

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatbotPage from './page';

const STALE_SESSION_ID = 'sess-owned-by-someone-else';

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/chatbot/models') {
      return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
    }
    if (path === '/api/kr/chatbot/sessions') {
      // 소유자가 바뀌었으므로 내 목록은 비어 있다.
      return { sessions: [] };
    }
    if (path.startsWith('/api/kr/chatbot/history')) {
      // 서버가 남의 세션에 돌려주는 응답. fetchAPI 가 status 를 실어 던진다.
      const error: Error & { status?: number } = new Error('Session not found');
      error.status = 404;
      throw error;
    }
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
vi.mock('react-markdown', () => ({
  default: ({ children }: { children?: string }) => children ?? '',
}));

describe('ChatbotPage - 소유자가 바뀐 뒤의 죽은 세션 ID', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.clear();
    localStorage.setItem('chatbot_last_session_id', STALE_SESSION_ID);
  });

  it('404 를 받으면 오류 문구 대신 새 대화 상태로 넘어간다', async () => {
    render(<ChatbotPage />);

    await waitFor(() => {
      expect(localStorage.getItem('chatbot_last_session_id')).toBeNull();
    });

    expect(screen.queryByText(/대화 기록을 불러오는데 실패/)).toBeNull();
  });

  it('404 가 아닌 실패는 종전대로 오류 문구를 띄운다', async () => {
    const { fetchAPI } = await import('@/lib/api');
    (fetchAPI as ReturnType<typeof vi.fn>).mockImplementation(async (path: string) => {
      if (path === '/api/kr/chatbot/models') {
        return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
      }
      if (path === '/api/kr/chatbot/sessions') {
        return { sessions: [] };
      }
      if (path.startsWith('/api/kr/chatbot/history')) {
        const error: Error & { status?: number } = new Error('Internal Server Error');
        error.status = 500;
        throw error;
      }
      return {};
    });

    render(<ChatbotPage />);

    await screen.findByText(/대화 기록을 불러오는데 실패/);
    // 서버 장애는 사용자가 다시 시도할 수 있어야 하므로 세션 ID 를 버리지 않는다.
    expect(localStorage.getItem('chatbot_last_session_id')).toBe(STALE_SESSION_ID);
  });
});
