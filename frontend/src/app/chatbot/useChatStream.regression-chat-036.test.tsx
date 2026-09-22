// Regression: [CHAT-036] — 스트림이 아닌 오류 응답과 done 없이 끊긴 스트림의 표시
// 근거: docs/dev-cycle/TODO.md [CHAT-036] ③·④. Next 프록시가 30초 무활동으로 upstream 을
// 끊으면 평문 `Internal Server Error` 500 이 오고, 스트림 도중 끊기면 done 이벤트가 없다.

import { act, renderHook, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Message } from './chatMessageParser';
import { useChatStream } from './useChatStream';

type ReadResult = { value: Uint8Array | undefined; done: boolean };

function controlledSse() {
  const encoder = new TextEncoder();
  const pendingReads: Array<(result: ReadResult) => void> = [];
  const nextRead = async () => {
    await waitFor(() => expect(pendingReads.length).toBeGreaterThan(0));
    const resolve = pendingReads.shift();
    if (!resolve) throw new Error('SSE reader is not waiting');
    return resolve;
  };

  return {
    response: {
      status: 200,
      headers: { get: (name: string) => name.toLowerCase() === 'content-type' ? 'text/event-stream' : null },
      body: { getReader: () => ({ read: () => new Promise<ReadResult>(resolve => pendingReads.push(resolve)) }) },
    },
    async deliver(event: Record<string, unknown>) {
      const resolve = await nextRead();
      await act(async () => resolve({ value: encoder.encode(`data: ${JSON.stringify(event)}\n\n`), done: false }));
    },
    async close() {
      const resolve = await nextRead();
      await act(async () => resolve({ value: undefined, done: true }));
    },
  };
}

function renderStream(currentSessionId: string | null) {
  return renderHook(() => {
    const [messages, setMessages] = useState<Message[]>([]);
    const stream = useChatStream({
      currentSessionId,
      currentModel: 'gemini-3.7-flash',
      attachedFiles: [],
      setMessages,
      onSendStart: vi.fn(),
      onSessionAssigned: vi.fn(),
      onSessionsShouldRefresh: vi.fn(),
    });
    return { ...stream, messages };
  });
}

afterEach(() => vi.unstubAllGlobals());

describe('[CHAT-036] useChatStream error surfaces', () => {
  it('평문 500 응답은 SyntaxError 대신 상태 코드 문구를 남긴다', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      status: 500,
      headers: { get: () => 'text/plain' },
      json: async () => { throw new SyntaxError(`Unexpected token 'I', "Internal S"... is not valid JSON`); },
    })));
    const { result } = renderStream('session-a');

    await act(async () => { await result.current.handleSend('질문'); });

    const last = result.current.messages.at(-1)?.parts[0];
    expect(last).toContain('HTTP 500');
    expect(last).not.toContain('Unexpected token');
    expect(result.current.isLoading).toBe(false);
  });

  it('done 없이 끝난 스트림은 받은 본문 뒤에 끊김 안내를 붙인다', async () => {
    const sse = controlledSse();
    vi.stubGlobal('fetch', vi.fn(async () => sse.response));
    const { result } = renderStream('session-a');

    await act(async () => { void result.current.handleSend('질문'); });
    await sse.deliver({ session_id: 'session-a', answer_chunk: '부분 답변' });
    await sse.close();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const last = result.current.messages.at(-1);
    expect(last?.isStreaming).toBe(false);
    expect(last?.parts[0]).toContain('부분 답변');
    expect(last?.parts[0]).toContain('응답이 중간에 끊겼습니다');
  });

  it('사용자가 중단한 스트림에는 끊김 안내를 붙이지 않는다', async () => {
    // 중단은 reader.read() 를 AbortError 로 끝내므로 안전망에 닿지 않아야 한다.
    const sse = controlledSse();
    vi.stubGlobal('fetch', vi.fn(async () => sse.response));
    const { result } = renderStream('session-a');

    await act(async () => { void result.current.handleSend('질문'); });
    await sse.deliver({ session_id: 'session-a', answer_chunk: '중단 전' });
    act(() => result.current.handleStop());

    expect(result.current.messages.at(-2)?.parts[0]).toBe('중단 전');
    expect(result.current.messages.at(-1)?.parts[0]).toBe('🛑 답변 생성이 중단되었습니다.');
  });

  it('done 으로 끝난 스트림에는 끊김 안내를 붙이지 않는다', async () => {
    const sse = controlledSse();
    vi.stubGlobal('fetch', vi.fn(async () => sse.response));
    const { result } = renderStream('session-a');

    await act(async () => { void result.current.handleSend('질문'); });
    await sse.deliver({ session_id: 'session-a', answer_chunk: '완전한 답변' });
    await sse.deliver({ session_id: 'session-a', done: true });
    await sse.close();
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.messages.at(-1)?.parts[0]).toBe('완전한 답변');
  });
});
