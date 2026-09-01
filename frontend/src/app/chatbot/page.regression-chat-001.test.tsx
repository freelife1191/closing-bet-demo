// Regression: [CHAT-001] — 새 대화의 스트리밍이 매 청크를 세션 전환으로 오판하던 문제
// 근거: docs/dev-cycle/audits/AUDIT-CHAT.md §1.1

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchAPI } from '@/lib/api';

import ChatbotPage from './page';

const NEW_SESSION_ID = 'sess-new-001';
const OTHER_SESSION_ID = 'sess-old-002';

const historyTextOf = (sessionId: string) => `${sessionId} 에 남아 있던 답변`;

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/chatbot/models') {
      return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
    }
    if (path === '/api/kr/chatbot/sessions') {
      return {
        sessions: [
          { id: NEW_SESSION_ID, title: '방금 시작한 대화', updated_at: '2026-09-01T00:00:00Z' },
          { id: OTHER_SESSION_ID, title: '지난 대화', updated_at: '2026-08-31T00:00:00Z' },
        ],
      };
    }
    if (path.startsWith('/api/kr/chatbot/history')) {
      const sessionId = path.split('session_id=')[1];
      return { history: [{ role: 'model', parts: [historyTextOf(sessionId)] }] };
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
vi.mock('react-markdown', () => ({ default: ({ children }: { children?: string }) => children ?? null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

const mockedFetchAPI = vi.mocked(fetchAPI);

// 서버는 모든 청크에 session_id 를 싣고, 마지막 청크에는 done 까지 함께 싣는다.
// chatbot/chat_handlers.py:188 참고.
function streamChunks(sessionId: string) {
  return [
    { session_id: sessionId, chunk: '안' },
    { session_id: sessionId, chunk: '녕' },
    { session_id: sessionId, chunk: '하' },
    { session_id: sessionId, chunk: '세' },
    { session_id: sessionId, chunk: '요' },
    { session_id: sessionId, done: true },
  ];
}

function sseResponse(chunks: Record<string, unknown>[], onChunk?: (consumed: number) => void) {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    headers: {
      get: (name: string) => (name.toLowerCase() === 'content-type' ? 'text/event-stream' : null),
    },
    body: {
      getReader: () => ({
        read: async () => {
          // 실제 스트림처럼 청크 사이에서 태스크를 넘긴다. 그래야 React 가 청크마다
          // 렌더를 커밋하고 effect 를 돌릴 기회를 얻는다.
          await new Promise(resolve => setTimeout(resolve, 0));
          if (index >= chunks.length) return { value: undefined, done: true };
          const payload = encoder.encode(`data: ${JSON.stringify(chunks[index++])}\n\n`);
          onChunk?.(index);
          return { value: payload, done: false };
        },
      }),
    },
  };
}

function sessionListCallCount() {
  return mockedFetchAPI.mock.calls.filter(call => call[0] === '/api/kr/chatbot/sessions').length;
}

function send(text: string) {
  const textarea = screen.getByPlaceholderText('메시지 입력...');
  fireEvent.change(textarea, { target: { value: text } });
  fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
}

async function settle() {
  await act(async () => {
    await new Promise(resolve => setTimeout(resolve, 10));
  });
}

async function startNewChatAndSend() {
  render(<ChatbotPage />);
  await screen.findAllByText('지난 대화');
  send('안녕');
  await screen.findByText('안녕하세요');
}

describe('ChatbotPage - 새 대화의 세션 전환', () => {
  beforeEach(() => {
    // jsdom 은 scrollIntoView 를 구현하지 않는다. 자동 스크롤 effect 가 마운트 직후 부른다.
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.clear();
    mockedFetchAPI.mockClear();
    global.fetch = vi.fn(async () => sseResponse(streamChunks(NEW_SESSION_ID))) as unknown as typeof fetch;
  });

  it('세션 목록을 청크마다 다시 부르지 않는다', async () => {
    await startNewChatAndSend();

    // 마운트 1회 + 세션이 생겼을 때 1회 + 스트림이 끝났을 때 1회.
    // 델타가 다섯 개지만 호출은 세 번을 넘지 않는다.
    await waitFor(() => expect(sessionListCallCount()).toBe(3));
  });

  it('스트림이 끝난 뒤 다른 세션을 열면 그 세션의 기록을 불러온다', async () => {
    await startNewChatAndSend();

    fireEvent.click(screen.getAllByText('지난 대화')[0]);

    expect(await screen.findByText(historyTextOf(OTHER_SESSION_ID))).toBeTruthy();
  });

  it('응답이 흐르는 도중에 다른 세션을 열면 그 세션에 머무른다', async () => {
    localStorage.setItem('chatbot_last_session_id', NEW_SESSION_ID);

    let consumed = 0;
    let switched = false;
    global.fetch = vi.fn(async () =>
      sseResponse(streamChunks(NEW_SESSION_ID), count => {
        consumed = count;
        if (switched) return;
        switched = true;
        fireEvent.click(screen.getAllByText('지난 대화')[0]);
      }),
    ) as unknown as typeof fetch;

    render(<ChatbotPage />);
    await screen.findByText(historyTextOf(NEW_SESSION_ID));

    send('안녕');
    await waitFor(() => expect(consumed).toBe(streamChunks(NEW_SESSION_ID).length));
    await settle();

    // 남은 청크가 화면을 원래 세션으로 되돌리면 이 값이 다시 덮어써진다.
    expect(localStorage.getItem('chatbot_last_session_id')).toBe(OTHER_SESSION_ID);
  });
});
