'use client';

import { useCallback, useRef, useState } from 'react';

import { getAuthHeaders } from '../components/chatHelpers';
import { getMessagePartText, type Message } from './chatMessageParser';

export interface StreamEvent {
  error?: string;
  clear?: boolean;
  answer_clear?: boolean;
  reasoning_clear?: boolean;
  chunk?: string;
  answer_chunk?: string;
  reasoning_chunk?: string;
  session_id?: string;
  done?: boolean;
}

// 이벤트 하나를 마지막 메시지에 반영한다. 상태를 건드리지 않는 순수 함수라 단위 검사가
// 직접 부를 수 있다. 분기 순서는 옮기기 전 page.tsx 의 것과 같다. 한 이벤트에 비우기와
// 델타가 함께 실려 오는 경우가 있어서 비우기를 먼저 적용해야 한다.
export function applyStreamEvent(message: Message, data: StreamEvent): Message {
  let next = message;

  if (data.error) {
    next = { ...next, parts: [data.error], isStreaming: false };
  }
  if (data.clear) {
    next = { ...next, parts: [''], reasoning: '' };
  }
  if (data.answer_clear) {
    next = { ...next, parts: [''] };
  }
  if (data.reasoning_clear) {
    next = { ...next, reasoning: '' };
  }

  const answerDelta = typeof data.answer_chunk === 'string' ? data.answer_chunk : data.chunk;
  if (typeof answerDelta === 'string' && answerDelta.length > 0) {
    next = { ...next, parts: [getMessagePartText(next.parts[0]) + answerDelta] };
  }
  if (typeof data.reasoning_chunk === 'string' && data.reasoning_chunk.length > 0) {
    next = { ...next, reasoning: (next.reasoning || '') + data.reasoning_chunk };
  }
  if (data.done) {
    next = { ...next, isStreaming: false };
  }

  return next;
}

export interface UseChatStreamOptions {
  currentSessionId: string | null;
  currentModel: string;
  persona?: string;
  attachedFiles: File[];
  /** 훅 밖의 사유로 전송을 막아야 할 때 참으로 준다. 히스토리를 읽는 동안이 그렇다. */
  isDisabled?: boolean;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  /** 전송이 시작될 때 입력 칸과 첨부 목록을 비운다. 언제나 함께 비우므로 하나로 받는다. */
  onSendStart: () => void;
  /** 서버가 이 스트림에 새 세션을 배정했을 때 부른다. */
  onSessionAssigned: (sessionId: string) => void;
  /** 세션 목록을 다시 읽어야 할 때 부른다. */
  onSessionsShouldRefresh: () => void;
}

export function useChatStream({
  currentSessionId,
  currentModel,
  persona,
  attachedFiles,
  isDisabled = false,
  setMessages,
  onSendStart,
  onSessionAssigned,
  onSessionsShouldRefresh,
}: UseChatStreamOptions) {
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setMessages(prev => [...prev, { role: 'model', parts: ['🛑 답변 생성이 중단되었습니다.'] }]);
    }
  }, [setMessages]);

  const applyToLastMessage = useCallback((data: StreamEvent) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const last = prev[prev.length - 1];
      const nextMsg = applyStreamEvent(last, data);
      // 서버는 프론트가 읽지 않는 프레임도 보낸다. usage_metadata 만 실린 것이 그렇다.
      // 그런 프레임에서 배열을 새로 만들면 렌더가 한 번 더 돈다.
      if (nextMsg === last) return prev;
      const newMsgs = [...prev];
      newMsgs[newMsgs.length - 1] = nextMsg;
      return newMsgs;
    });
  }, [setMessages]);

  const handleSend = useCallback(async (text: string) => {
    if ((!text.trim() && attachedFiles.length === 0) || isLoading || isDisabled) return;

    // Display User Message locally first
    const displayMsg = text + (attachedFiles.length > 0 ? `\n[파일 ${attachedFiles.length}개 첨부]` : '');
    const userMsg: Message = {
      role: 'user',
      parts: [displayMsg],
      timestamp: new Date().toISOString(),
    };

    // Optimistic update
    setMessages(prev => [...prev, userMsg]);
    onSendStart();
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // 이 요청이 속한 세션. 화면에 표시 중인 세션(currentSessionId)과는 다른 값이다.
    // 응답이 흐르는 동안 사용자가 다른 세션을 열 수 있기 때문에 둘을 섞으면 안 된다.
    let streamSessionId = currentSessionId;

    try {
      const savedWatchlist = localStorage.getItem('watchlist');
      const watchlist = savedWatchlist ? JSON.parse(savedWatchlist) : [];
      const headers = getAuthHeaders();

      let res: Response;
      if (attachedFiles.length > 0) {
        // FormData 를 보낼 때는 Content-Type 을 지정하지 않는다. 브라우저가 경계
        // 문자열까지 넣어 스스로 붙인다.
        const formData = new FormData();
        formData.append('message', text);
        if (currentModel) formData.append('model', currentModel);
        if (currentSessionId) formData.append('session_id', currentSessionId);
        if (watchlist.length > 0) formData.append('watchlist', JSON.stringify(watchlist));
        if (persona) formData.append('persona', persona);
        attachedFiles.forEach(file => formData.append('file', file));

        res = await fetch('/api/kr/chatbot', {
          method: 'POST',
          headers,
          body: formData,
          signal: controller.signal,
        });
      } else {
        headers['Content-Type'] = 'application/json';
        res = await fetch('/api/kr/chatbot', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            message: text,
            model: currentModel,
            session_id: currentSessionId,
            watchlist,
            persona,
          }),
          signal: controller.signal,
        });
      }

      const contentType = (res.headers.get('content-type') || '').toLowerCase();

      if (contentType.includes('text/event-stream') && res.body) {
        setIsLoading(false);
        setMessages(prev => [...prev, { role: 'model', parts: [''], reasoning: '', isStreaming: true }]);

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let done = false;
        let buffer = '';

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (!value) continue;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n');
          buffer = frames.pop() || '';

          for (const frame of frames) {
            if (!frame.startsWith('data: ')) continue;
            const dataStr = frame.substring(6);
            if (!dataStr.trim()) continue;

            let data: StreamEvent;
            try {
              data = JSON.parse(dataStr);
            } catch {
              // 반쪽 청크는 다음 프레임에서 이어진다
              continue;
            }

            applyToLastMessage(data);

            // 서버는 모든 청크에 session_id 를 싣는다. 새 대화에서 첫 청크가 세션을
            // 배정한 뒤에도 갱신으로 판정되지 않도록 이 스트림의 세션을 갱신해 둔다.
            const sessionChanged = Boolean(data.session_id) && data.session_id !== streamSessionId;
            if (sessionChanged) {
              streamSessionId = data.session_id!;
              onSessionAssigned(data.session_id!);
            }
            if (sessionChanged || data.done) {
              onSessionsShouldRefresh();
            }
          }
        }

        // Safety net: if stream closed without explicit done event,
        // ensure the last placeholder message does not remain in streaming state.
        setMessages(prev => {
          if (prev.length === 0) return prev;
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === 'model' && last?.isStreaming) {
            next[next.length - 1] = { ...last, isStreaming: false };
          }
          return next;
        });
      } else {
        const data = await res.json();

        if (data.response) {
          if (data.session_id && data.session_id !== streamSessionId) {
            streamSessionId = data.session_id;
            onSessionAssigned(data.session_id);
          }
          onSessionsShouldRefresh();
          setMessages(prev => [...prev, { role: 'model', parts: [data.response] }]);
        } else if (data.error) {
          setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ 오류: ${data.error}`] }]);
        } else {
          setMessages(prev => [...prev, { role: 'model', parts: ['⚠️ 응답을 받아오지 못했습니다.'] }]);
        }
      }
    } catch (error: any) {
      if (error?.name === 'AbortError') {
        // Already handled in handleStop usually, but double check
        return;
      }
      const errorMessage = (error && typeof error.message === 'string' && error.message.trim().length > 0)
        ? `⚠️ 오류가 발생했습니다: ${error.message}`
        : '⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
      setMessages(prev => [...prev, { role: 'model', parts: [errorMessage] }]);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
      // Reset viewport for mobile keyboard fix
      if (window.innerWidth < 1024) {
        window.scrollTo(0, 0);
        document.body.scrollTop = 0;
      }
    }
  }, [
    attachedFiles,
    isLoading,
    isDisabled,
    currentSessionId,
    currentModel,
    persona,
    setMessages,
    onSendStart,
    applyToLastMessage,
    onSessionAssigned,
    onSessionsShouldRefresh,
  ]);

  return { isLoading, handleSend, handleStop };
}
