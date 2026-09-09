// Regression: [CHAT-004] — 스트리밍 중에 앞선 메시지까지 다시 그리던 문제
// 근거: docs/dev-cycle/audits/AUDIT-CHAT.md §2.2, §4.1
//
// ChatMessage 를 memo 로 감쌌더라도, 페이지가 넘기는 콜백 프롭의 참조가 청크마다
// 새로 만들어지면 얕은 비교가 언제나 실패해 대화의 모든 메시지가 다시 그려진다.
// 이 검사는 그 상황을 렌더 횟수로 붙잡는다. 마크다운 렌더가 청크마다 반복되면
// 파싱 비용이 대화 길이에 비례해 늘어난다.

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChatbotPage from './page';

const SESSION_ID = 'sess-memo-001';
const HISTORY_TEXT = '이미 쌓여 있던 지난 답변';

// 마크다운 렌더가 몇 번 불렸는지 텍스트별로 센다.
const markdownRenderCounts = new Map<string, number>();

vi.mock('@/lib/api', () => ({
  fetchAPI: vi.fn(async (path: string) => {
    if (path === '/api/kr/chatbot/models') {
      return { models: ['gemini-3.7-flash'], current: 'gemini-3.7-flash' };
    }
    if (path === '/api/kr/chatbot/sessions') {
      return {
        sessions: [{ id: SESSION_ID, title: '지난 대화', updated_at: '2026-09-01T00:00:00Z' }],
      };
    }
    if (path.startsWith('/api/kr/chatbot/history')) {
      return { history: [{ role: 'model', parts: [HISTORY_TEXT] }] };
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
  default: ({ children }: { children?: string }) => {
    const text = children ?? '';
    markdownRenderCounts.set(text, (markdownRenderCounts.get(text) ?? 0) + 1);
    return text;
  },
}));

// 서버는 모든 청크에 session_id 를 싣고 마지막 청크에 done 을 싣는다.
const STREAM_CHUNKS = [
  { session_id: SESSION_ID, answer_chunk: '가' },
  { session_id: SESSION_ID, answer_chunk: '나' },
  { session_id: SESSION_ID, answer_chunk: '다' },
  { session_id: SESSION_ID, answer_chunk: '라' },
  { session_id: SESSION_ID, answer_chunk: '마' },
  { session_id: SESSION_ID, done: true },
];

function controlledSseResponse(chunks: Record<string, unknown>[]) {
  const encoder = new TextEncoder();
  let index = 0;
  const pendingReads: Array<(result: { value: Uint8Array | undefined; done: boolean }) => void> = [];

  return {
    response: {
      headers: {
        get: (name: string) => (name.toLowerCase() === 'content-type' ? 'text/event-stream' : null),
      },
      body: {
        getReader: () => ({
          read: () => new Promise(resolve => pendingReads.push(resolve)),
        }),
      },
    },
    async deliverNextChunk() {
      await waitFor(() => expect(pendingReads.length).toBeGreaterThan(0));
      const resolve = pendingReads.shift();
      if (!resolve) throw new Error('SSE 리더가 청크를 기다리고 있지 않습니다.');
      const payload = encoder.encode(`data: ${JSON.stringify(chunks[index++])}\n\n`);
      await act(async () => {
        resolve({ value: payload, done: false });
      });
    },
    async close() {
      await waitFor(() => expect(pendingReads.length).toBeGreaterThan(0));
      const resolve = pendingReads.shift();
      if (!resolve) throw new Error('SSE 리더가 종료 신호를 기다리고 있지 않습니다.');
      await act(async () => {
        resolve({ value: undefined, done: true });
      });
    },
  };
}

describe('ChatbotPage - 스트리밍 중 앞선 메시지의 재렌더', () => {
  beforeEach(() => {
    // jsdom 은 scrollIntoView 를 구현하지 않는다. 자동 스크롤 effect 가 마운트 직후 부른다.
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.clear();
    localStorage.setItem('chatbot_last_session_id', SESSION_ID);
    markdownRenderCounts.clear();
  });

  it('청크가 도착해도 앞선 메시지를 다시 그리지 않는다', async () => {
    const stream = controlledSseResponse(STREAM_CHUNKS);
    global.fetch = vi.fn(async () => stream.response) as unknown as typeof fetch;
    render(<ChatbotPage />);
    await screen.findByText(HISTORY_TEXT);

    const beforeSend = markdownRenderCounts.get(HISTORY_TEXT) ?? 0;
    expect(beforeSend).toBeGreaterThan(0);

    const textarea = screen.getByPlaceholderText('메시지 입력...');
    fireEvent.change(textarea, { target: { value: '안녕' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    for (let chunkIndex = 0; chunkIndex < STREAM_CHUNKS.length; chunkIndex += 1) {
      await stream.deliverNextChunk();
    }
    await stream.close();
    await screen.findByText('가나다라마');

    // 델타가 다섯 개 흐르는 동안 지난 답변이 다시 파싱되면 이 값이 그만큼 늘어난다.
    // 사용자 메시지가 붙을 때 한 번은 늘 수 있으므로 두 번까지만 허용한다.
    const afterStream = markdownRenderCounts.get(HISTORY_TEXT) ?? 0;
    expect(afterStream - beforeSend).toBeLessThanOrEqual(2);
  });

  it('스트리밍 중인 메시지 자체는 청크마다 갱신된다', async () => {
    const stream = controlledSseResponse(STREAM_CHUNKS);
    global.fetch = vi.fn(async () => stream.response) as unknown as typeof fetch;
    render(<ChatbotPage />);
    await screen.findByText(HISTORY_TEXT);

    const textarea = screen.getByPlaceholderText('메시지 입력...');
    fireEvent.change(textarea, { target: { value: '안녕' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    await stream.deliverNextChunk();
    await screen.findByText('가');
    await stream.deliverNextChunk();
    await screen.findByText('가나');

    // 중간 상태가 실제로 화면에 그려졌는지 본다. memo 가 너무 세게 걸려 스트리밍
    // 메시지까지 멈추면 이 값들이 남지 않는다.
    expect(markdownRenderCounts.has('가나')).toBe(true);

    for (let chunkIndex = 2; chunkIndex < STREAM_CHUNKS.length; chunkIndex += 1) {
      await stream.deliverNextChunk();
    }
    await stream.close();
    await screen.findByText('가나다라마');
    expect(markdownRenderCounts.has('가나다라마')).toBe(true);
  });
});
