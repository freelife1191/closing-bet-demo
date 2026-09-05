'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchAPI } from '@/lib/api';

import { getAuthHeaders } from '../components/chatHelpers';
import type { Message } from './chatMessageParser';

export interface Session {
  id: string;
  title: string;
  updated_at: string;
  model?: string;
}

const LAST_SESSION_KEY = 'chatbot_last_session_id';

// 세션과 메시지를 한 훅이 소유한다. 세션을 바꾸면 메시지가 통째로 바뀌므로, 둘을 나누면
// 두 상태가 서로 어긋난 채 렌더되는 순간이 생긴다.
export function useChatSessions() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  // 새 대화의 첫 청크가 세션을 배정했을 때 그것이 세션 전환으로 오판정되어 화면의
  // 낙관적 갱신을 히스토리로 덮어쓰지 않도록 막는 표시다. [CHAT-001] 이 만들었다.
  const isCreatingSessionRef = useRef(false);

  const fetchSessions = useCallback(async (): Promise<Session[]> => {
    try {
      const data: any = await fetchAPI('/api/kr/chatbot/sessions', {
        headers: getAuthHeaders(),
      });
      if (data.sessions) {
        setSessions(data.sessions);
        return data.sessions;
      }
    } catch (e) {
      console.error('Failed to fetch sessions', e);
    }
    return [];
  }, []);

  const fetchHistory = useCallback(async (sessionId: string) => {
    try {
      setIsHistoryLoading(true); // Show loading state
      const data: any = await fetchAPI(`/api/kr/chatbot/history?session_id=${sessionId}`, {
        headers: getAuthHeaders(),
      });
      if (data.history) {
        setMessages(data.history);
      } else {
        setMessages([]);
      }
    } catch (error) {
      // 404 는 「그 세션은 없거나 내 것이 아니다」라는 뜻이다. 소유자가 바뀌면(로그인,
      // 로그아웃, 브라우저 세션 ID 재발급) 저장해 둔 세션 ID 가 그대로 남아 이 응답을
      // 받는다. 오류 문구를 띄우고 멈추면 사용자는 새 대화조차 시작하지 못하므로,
      // 죽은 세션 ID 를 버리고 새 대화 상태로 넘어간다.
      if ((error as { status?: number }).status === 404) {
        localStorage.removeItem(LAST_SESSION_KEY);
        setCurrentSessionId(null);
        setMessages([]);
        return;
      }
      console.error('Failed to fetch history:', error);
      setMessages([{ role: 'model', parts: ['⚠️ 대화 기록을 불러오는데 실패했습니다.'] }]);
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  const markSessionAsCreated = useCallback(() => {
    isCreatingSessionRef.current = true;
  }, []);

  // 브라우저에 남겨 둔 마지막 세션으로 되돌린다. 첫 렌더에서 한 번만 부른다.
  const restoreLastSession = useCallback(() => {
    const cachedSessionId = localStorage.getItem(LAST_SESSION_KEY);
    if (cachedSessionId) {
      setCurrentSessionId(cachedSessionId);
    }
  }, []);

  const startNewChat = useCallback(() => {
    setCurrentSessionId(null);
    localStorage.removeItem(LAST_SESSION_KEY); // Clear cache
    setMessages([]);
  }, []);

  // Load History when Session Changes
  useEffect(() => {
    if (currentSessionId) {
      if (isCreatingSessionRef.current) {
        isCreatingSessionRef.current = false;
      } else {
        fetchHistory(currentSessionId);
      }
      localStorage.setItem(LAST_SESSION_KEY, currentSessionId);
    } else {
      setMessages([]); // New Chat
    }
  }, [currentSessionId, fetchHistory]);

  return {
    messages,
    setMessages,
    sessions,
    currentSessionId,
    setCurrentSessionId,
    isHistoryLoading,
    fetchSessions,
    fetchHistory,
    markSessionAsCreated,
    restoreLastSession,
    startNewChat,
  };
}
