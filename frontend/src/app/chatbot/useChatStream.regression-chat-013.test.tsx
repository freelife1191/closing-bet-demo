import { act, renderHook, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Message } from './chatMessageParser';
import { useChatStream } from './useChatStream';

type ReadResult = { value: Uint8Array | undefined; done: boolean };

function controlledSse() {
  const encoder = new TextEncoder();
  const pendingReads: Array<(result: ReadResult) => void> = [];

  return {
    response: {
      headers: { get: (name: string) => name.toLowerCase() === 'content-type' ? 'text/event-stream' : null },
      body: { getReader: () => ({ read: () => new Promise<ReadResult>(resolve => pendingReads.push(resolve)) }) },
    },
    async deliver(event: Record<string, unknown>) {
      await waitFor(() => expect(pendingReads.length).toBeGreaterThan(0));
      const resolve = pendingReads.shift();
      if (!resolve) throw new Error('SSE reader is not waiting');
      await act(async () => resolve({ value: encoder.encode(`data: ${JSON.stringify(event)}\n\n`), done: false }));
    },
    async close() {
      await waitFor(() => expect(pendingReads.length).toBeGreaterThan(0));
      const resolve = pendingReads.shift();
      if (!resolve) throw new Error('SSE reader is not waiting');
      await act(async () => resolve({ value: undefined, done: true }));
    },
  };
}

function renderStream(currentSessionId: string | null) {
  const callbacks = {
    onSendStart: vi.fn(),
    onSessionAssigned: vi.fn(),
    onSessionsShouldRefresh: vi.fn(),
  };
  const hook = renderHook(
    ({ sessionId }) => {
      const [messages, setMessages] = useState<Message[]>([]);
      const stream = useChatStream({
        currentSessionId: sessionId,
        currentModel: 'gemini-3.7-flash',
        attachedFiles: [],
        setMessages,
        ...callbacks,
      });
      return { ...stream, messages };
    },
    { initialProps: { sessionId: currentSessionId } },
  );
  return { ...hook, callbacks };
}

afterEach(() => vi.unstubAllGlobals());

describe('[CHAT-013] useChatStream ownership', () => {
  it('SSE 전체 동안 busy를 유지하고 동기 중복 전송을 막으며 중단할 수 있다', async () => {
    const sse = controlledSse();
    const fetchMock = vi.fn(async () => sse.response);
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderStream('session-a');

    await act(async () => {
      void result.current.handleSend('첫 질문');
      void result.current.handleSend('두 번째 질문');
    });
    await sse.deliver({ session_id: 'session-a', answer_chunk: '답변' });

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(result.current.isLoading).toBe(true);

    act(() => result.current.handleStop());
    expect(result.current.isLoading).toBe(false);
    expect(result.current.messages.at(-2)?.isStreaming).toBe(false);
    expect(result.current.messages.at(-1)?.parts[0]).toBe('🛑 답변 생성이 중단되었습니다.');
  });

  it('다른 세션으로 바뀐 뒤 늦은 delta는 적용하지 않는다', async () => {
    const sse = controlledSse();
    vi.stubGlobal('fetch', vi.fn(async () => sse.response));
    const { result, rerender } = renderStream('session-a');

    await act(async () => { void result.current.handleSend('질문'); });
    await sse.deliver({ session_id: 'session-a', answer_chunk: '이전' });
    rerender({ sessionId: 'session-b' });
    await sse.deliver({ session_id: 'session-a', answer_chunk: '세션' });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.messages.map(message => message.parts[0])).not.toContain('이전세션');
  });

  it('새 세션 id를 배정받은 스트림은 같은 세션으로 전환된 뒤 계속 읽는다', async () => {
    const sse = controlledSse();
    vi.stubGlobal('fetch', vi.fn(async () => sse.response));
    const { result, rerender, callbacks } = renderStream(null);

    await act(async () => { void result.current.handleSend('새 질문'); });
    await sse.deliver({ session_id: 'session-new', answer_chunk: '새' });
    rerender({ sessionId: 'session-new' });
    await sse.deliver({ session_id: 'session-new', answer_chunk: ' 대화' });
    await sse.deliver({ session_id: 'session-new', done: true });
    await sse.close();

    expect(callbacks.onSessionAssigned).toHaveBeenCalledWith('session-new');
    expect(result.current.messages.at(-1)?.parts[0]).toBe('새 대화');
    expect(result.current.isLoading).toBe(false);
  });

  it('언마운트하면 진행 중 요청을 abort한다', async () => {
    let aborted = false;
    vi.stubGlobal('fetch', vi.fn((_url: string, init?: RequestInit) => new Promise(() => {
      init?.signal?.addEventListener('abort', () => { aborted = true; });
    })));
    const { result, unmount } = renderStream('session-a');

    await act(async () => { void result.current.handleSend('질문'); });
    unmount();

    expect(aborted).toBe(true);
  });

  it('즉시 JSON 응답은 finally 뒤에도 메시지로 남는다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      headers: { get: () => 'application/json' },
      json: async () => ({ response: '즉시 응답' }),
    })));
    const { result } = renderStream('session-a');

    await act(async () => { await result.current.handleSend('질문'); });

    expect(result.current.messages.at(-1)?.parts[0]).toBe('즉시 응답');
    expect(result.current.isLoading).toBe(false);
  });

  it('종료 SSE의 마지막 delta는 finally 뒤에도 메시지로 남는다', async () => {
    const encoder = new TextEncoder();
    vi.stubGlobal('fetch', vi.fn(async () => ({
      headers: { get: () => 'text/event-stream' },
      body: {
        getReader: () => ({
          read: async () => ({
            value: encoder.encode('data: {"session_id":"session-a","answer_chunk":"마지막","done":true}\n\n'),
            done: true,
          }),
        }),
      },
    })));
    const { result } = renderStream('session-a');

    await act(async () => { await result.current.handleSend('질문'); });

    expect(result.current.messages.at(-1)?.parts[0]).toBe('마지막');
    expect(result.current.messages.at(-1)?.isStreaming).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });
});
