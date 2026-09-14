'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { fetchAPI } from '@/lib/api';

import Link from 'next/link';
import Sidebar from '../components/Sidebar';
import SettingsModal from '../components/SettingsModal';
import ConfirmationModal from '../components/ConfirmationModal';
import Modal from '../components/Modal';
import PaperTradingModal from '../components/PaperTradingModal';
import {
  DEFAULT_USER_PROFILE,
  getAuthHeaders,
  getStoredModel,
  saveUserProfile,
  resolveUserProfile,
  normalizeUserProfile,
  setStoredModel,
  shouldSendOnEnter,
} from '../components/chatHelpers';
import { useChatSessions } from './useChatSessions';
import { useChatStream } from './useChatStream';
import { useSpeechInput } from './useSpeechInput';
import { ChatMessage } from './ChatMessage';
import { getTurnIndicesFromMessage } from './chatMessageParser';

// Types
interface SuggestionCard {
  title: string;
  desc: string;
  icon: string;
  prompt: string;
}

const SUGGESTIONS: SuggestionCard[] = [
  { title: '시장 현황', desc: '마켓게이트 상태와 투자 전략', icon: 'fas fa-chart-pie', prompt: '오늘 마켓게이트 상태와 투자 전략 알려줘' },
  { title: 'VCP 추천', desc: 'AI 분석 기반 매수 추천 종목', icon: 'fas fa-search-dollar', prompt: 'VCP AI 분석 결과 매수 추천 종목 알려줘' },
  { title: '종가 베팅', desc: '오늘의 S/A급 종가베팅 추천', icon: 'fas fa-chess-knight', prompt: '오늘의 종가베팅 S급, A급 추천해줘' },
  { title: '뉴스 분석', desc: '최근 주요 뉴스와 시장 영향', icon: 'fas fa-newspaper', prompt: '최근 주요 뉴스와 시장 영향 분석해줘' },
  { title: '내 관심종목', desc: '관심종목 진단 및 리스크 점검', icon: 'fas fa-heart', prompt: '내 관심종목 리스트 기반으로 현재 상태 진단해줘' },
];

export default function ChatbotPage() {
  const { data: session, status } = useSession();
  const {
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
  } = useChatSessions();

  const [input, setInput] = useState('');
  const [models, setModels] = useState<string[]>([]);
  const [currentModel, setCurrentModelState] = useState<string>('');
  const setCurrentModel = useCallback((model: string) => {
    setCurrentModelState(model);
    setStoredModel(model);
  }, []);

  // Session State

  // Command State
  const [showCommands, setShowCommands] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);

  // File & Voice States
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);

  // User Profile State
  const [userProfile, setUserProfile] = useState(DEFAULT_USER_PROFILE);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false); // Mobile Sidebar State
  const [isMenuExpanded, setIsMenuExpanded] = useState(true); // Menu Parsing State
  const displayProfile = resolveUserProfile(
    userProfile,
    status === 'authenticated' ? session?.user : null,
  );

  // Delete Modal State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [sessionToDeleteId, setSessionToDeleteId] = useState<string | null>(null);
  const [isMessageDeleteModalOpen, setIsMessageDeleteModalOpen] = useState(false);
  const [messageToDeleteIndex, setMessageToDeleteIndex] = useState<number | null>(null);
  const [isTurnDeleteModalOpen, setIsTurnDeleteModalOpen] = useState(false);
  const [turnDeleteTargetIndex, setTurnDeleteTargetIndex] = useState<number | null>(null);

  // Alert Modal State
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    type: 'default' | 'success' | 'danger';
    title: string;
    content: string;
  }>({ isOpen: false, type: 'default', title: '', content: '' });

  // Paper Trading Modal State
  const [isPaperTradingOpen, setIsPaperTradingOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mobileMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const isComposing = useRef(false); // Track IME composition state

  // Loading Steps
  const [loadingStep, setLoadingStep] = useState(0);
  const LOADING_STEPS = [
    "질문을 분석하고 있습니다...",
    "시장 데이터를 조회 중입니다...",
    "과거 대화 내용을 참고하고 있습니다...",
    "답변을 생성하고 있습니다...",
    "내용을 정리하는 중입니다..."
  ];

  // Suggestions State
  const suggestions = SUGGESTIONS;

  // 전송이 시작될 때 입력 칸과 첨부 목록과 명령 목록을 비운다. 한글 조합 상태도 함께 푼다.
  const handleSendStart = useCallback(() => {
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'; // Reset height
    }
    // Korean IME fix: simpler reset
    setTimeout(() => {
      isComposing.current = false;
    }, 0);
    // 이미 비어 있으면 그대로 둔다. 새 빈 배열을 넣으면 attachedFiles 를 의존으로
    // 갖는 handleSend 가 새로 만들어져 ChatMessage 의 memo 가 전송마다 한 번 깨진다.
    setAttachedFiles(prev => (prev.length === 0 ? prev : []));
    setShowCommands(false);
  }, []);

  const handleSessionAssigned = useCallback((sessionId: string) => {
    markSessionAsCreated(); // Prevent history fetch overwriting optimistic state
    setCurrentSessionId(sessionId);
  }, [markSessionAsCreated, setCurrentSessionId]);

  const handleSessionsShouldRefresh = useCallback(() => {
    fetchSessions();
  }, [fetchSessions]);

  const { isLoading, handleSend, handleStop } = useChatStream({
    currentSessionId,
    currentModel,
    persona: userProfile.persona,
    attachedFiles,
    isDisabled: isHistoryLoading,
    setMessages,
    onSendStart: handleSendStart,
    onSessionAssigned: handleSessionAssigned,
    onSessionsShouldRefresh: handleSessionsShouldRefresh,
  });

  // 옮기기 전에는 전송과 히스토리 조회가 같은 상태 하나를 썼다. 화면과 가드가 보는 것을
  // 그때와 같게 두려고 둘을 합쳐 쓴다.
  const isBusy = isLoading || isHistoryLoading;

  const handleTranscript = useCallback((text: string) => {
    setInput(prev => prev + (prev ? ' ' : '') + text);
  }, []);

  const handleSpeechUnsupported = useCallback(() => {
    setAlertModal({
      isOpen: true,
      type: 'danger',
      title: '음성 인식 미지원',
      content: '이 브라우저는 음성 인식을 지원하지 않습니다.'
    });
  }, []);

  const { isRecording, toggleRecording } = useSpeechInput({
    onTranscript: handleTranscript,
    onUnsupported: handleSpeechUnsupported,
  });

  const hasOpenDialog = isSettingsOpen
    || isDeleteModalOpen
    || isMessageDeleteModalOpen
    || isTurnDeleteModalOpen
    || alertModal.isOpen
    || isPaperTradingOpen;

  const closeMobileSidebar = useCallback(() => {
    setIsMobileSidebarOpen(false);
    mobileMenuTriggerRef.current?.focus();
  }, []);

  useEffect(() => {
    const desktopMediaQuery = window.matchMedia('(min-width: 1024px)');
    const closeAtDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) {
        setIsMobileSidebarOpen(false);
      }
    };

    desktopMediaQuery.addEventListener('change', closeAtDesktop);
    return () => desktopMediaQuery.removeEventListener('change', closeAtDesktop);
  }, []);

  useEffect(() => {
    if (!isMobileSidebarOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !hasOpenDialog) closeMobileSidebar();
    };

    window.addEventListener('keydown', handleEscape, true);
    return () => window.removeEventListener('keydown', handleEscape, true);
  }, [closeMobileSidebar, hasOpenDialog, isMobileSidebarOpen]);

  /* 
  // [Optimization] 페이지 진입 시 알트(Alt) Gemini API 호출 중단 요청 반영
  // 사용자가 직접 요청하지 않았는데 불필요하게 Quota를 소모하는 문제 방지
  useEffect(() => {
    const fetchSuggestions = async () => {
      // ... (Removed auto-fetch logic) ...
    };
    // fetchSuggestions();
  }, [userProfile.persona]);
  */

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isBusy) {
      setLoadingStep(0);
      interval = setInterval(() => {
        setLoadingStep(prev => (prev < LOADING_STEPS.length - 1 ? prev + 1 : prev));
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isBusy]);

  // Commands Definition
  const COMMANDS = [
    { cmd: '/help', desc: '도움말 확인' },
    { cmd: '/status', desc: '현재 상태(모델, 메모리) 확인' },
    { cmd: '/memory view', desc: '저장된 메모리 보기' },
    { cmd: '/clear', desc: '현재 세션 메시지 삭제' },
    { cmd: '/clear all', desc: '내 대화와 메모리 프로필 삭제' },
  ];

  const filteredCommands = input.startsWith('/')
    ? COMMANDS.filter(c => c.cmd.toLowerCase().startsWith(input.toLowerCase()))
    : [];

  // Initialize
  useEffect(() => {
    // 1. Load Local Cache for Profile (Global Key)
    const loadProfile = () => {
      const cachedProfile = localStorage.getItem('user_profile');
      if (cachedProfile) {
        try {
          setUserProfile(normalizeUserProfile(JSON.parse(cachedProfile)));
        } catch (e) {
          console.error("Cache clean needed");
          setUserProfile(DEFAULT_USER_PROFILE);
        }
      } else {
        setUserProfile(DEFAULT_USER_PROFILE);
      }
    };
    loadProfile();

    // Listen for profile updates from Sidebar
    window.addEventListener('user-profile-updated', loadProfile);

    // 2. Load Local Cache for Session ID (Optimistic Restore)
    restoreLastSession();

    fetchModels();

    // Fetch sessions list (Logic separated from restoration to prevent race condition)
    fetchSessions();

    // We don't fetch user profile from backend here anymore to avoid overwriting sidebar settings
    // or we fetch it but save it to the global key? Better to rely on sidebar state as source of truth for now.

    return () => {
      window.removeEventListener('user-profile-updated', loadProfile);
    };
  }, []);

  // Update commands selection index when input changes
  useEffect(() => {
    setSelectedCommandIndex(0);
    if (input.startsWith('/')) {
      setShowCommands(true);
    } else {
      setShowCommands(false);
    }
  }, [input]);

  // Auto-scroll
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // ...

  // API Calls
  const fetchModels = async () => {
    interface ChatbotModelsResponse {
      models?: string[];
      current?: string;
    }
    try {
      const data = await fetchAPI<ChatbotModelsResponse>('/api/kr/chatbot/models');
      if (data.models) {
        setModels(data.models);
        if (!currentModel) {
          const stored = getStoredModel();
          const next = (stored && data.models.includes(stored))
            ? stored
            : (data.current || data.models[0]);
          setCurrentModel(next);
        }
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
    }
  };

  // Interaction Handlers
  const handleKeyDown = (e: React.KeyboardEvent) => {
    // IME Composition Check
    // We don't return early here anymore, but handle it specifically for Enter
    // to avoid losing the key event completely.

    if (showCommands && filteredCommands.length > 0) {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedCommandIndex(prev => (prev > 0 ? prev - 1 : filteredCommands.length - 1));
        return;
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedCommandIndex(prev => (prev < filteredCommands.length - 1 ? prev + 1 : 0));
        return;
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const selectedCmd = filteredCommands[selectedCommandIndex];
        if (selectedCmd) {
          setShowCommands(false);
          handleSend(selectedCmd.cmd);
        }
        return;
      }
    }

    const composing = e.nativeEvent.isComposing || isComposing.current;
    if (shouldSendOnEnter(e.key, e.shiftKey, composing)) {
      e.preventDefault();
      handleSend(input);
    }
  };


  // Helper Actions
  const handleNewChat = () => {
    startNewChat();
    setAttachedFiles([]);
    setInput('');
    inputRef.current?.focus();
  };

  const handleDeleteSession = (sessionId: string) => {
    setSessionToDeleteId(sessionId);
    setIsDeleteModalOpen(true);
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDeleteId) return;

    try {
      const headers = getAuthHeaders();
      await fetch(`/api/kr/chatbot/history?session_id=${sessionToDeleteId}`, {
        method: 'DELETE',
        headers // Add headers for delete as well
      });
      await fetchSessions();
      if (currentSessionId === sessionToDeleteId) {
        handleNewChat();
      }
    } catch (e) {
      console.error("Delete failed", e);
    } finally {
      setIsDeleteModalOpen(false);
      setSessionToDeleteId(null);
    }
  };

  const handleDeleteMessage = useCallback((e: React.MouseEvent, msgIndex: number) => {
    e.stopPropagation();
    if (isBusy) return;
    setMessageToDeleteIndex(msgIndex);
    setIsMessageDeleteModalOpen(true);
  }, [isBusy]);

  const confirmDeleteMessage = async () => {
    if (messageToDeleteIndex === null) return;

    const targetIndex = messageToDeleteIndex;
    const targetSessionId = currentSessionId;
    const previousMessages = messages;

    try {
      setMessages(prev => prev.filter((_, idx) => idx !== targetIndex));

      if (!targetSessionId) {
        throw new Error('NO_ACTIVE_SESSION');
      }

      const headers = getAuthHeaders();
      headers['Cache-Control'] = 'no-cache';

      const res = await fetch(
        `/api/kr/chatbot/history?session_id=${encodeURIComponent(targetSessionId)}&index=${targetIndex}&_t=${Date.now()}`,
        {
          method: 'DELETE',
          headers,
        }
      );

      if (!res.ok) {
        throw new Error(`Delete message failed: ${res.status}`);
      }

      await fetchHistory(targetSessionId);
      await fetchSessions();
    } catch (e) {
      console.error("Message delete failed", e);
      setMessages(previousMessages);
      setAlertModal({
        isOpen: true,
        type: 'danger',
        title: '메시지 삭제 실패',
        content: '메시지 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      });
    } finally {
      setIsMessageDeleteModalOpen(false);
      setMessageToDeleteIndex(null);
    }
  };

  // 짝이 되는 인덱스 계산을 확인 시점으로 미룬다. 여기서 messages 를 읽으면 이 콜백이
  // 청크마다 새로 만들어지고, 그러면 ChatMessage 의 memo 가 스트리밍 내내 무효가 된다.
  const handleDeleteTurn = useCallback((e: React.MouseEvent, msgIndex: number) => {
    e.stopPropagation();
    if (isBusy) return;

    setTurnDeleteTargetIndex(msgIndex);
    setIsTurnDeleteModalOpen(true);
  }, [isBusy]);

  const confirmDeleteTurn = async () => {
    if (turnDeleteTargetIndex === null) return;

    const targetIndices = getTurnIndicesFromMessage(messages, turnDeleteTargetIndex);
    if (targetIndices.length === 0) return;

    const targetSessionId = currentSessionId;
    const previousMessages = messages;

    try {
      const deleteSet = new Set(targetIndices);
      setMessages(prev => prev.filter((_, idx) => !deleteSet.has(idx)));

      if (!targetSessionId) {
        throw new Error('NO_ACTIVE_SESSION');
      }

      const headers = getAuthHeaders();
      headers['Cache-Control'] = 'no-cache';

      const sortedIndices = [...targetIndices].sort((a, b) => b - a);
      for (const idx of sortedIndices) {
        const res = await fetch(
          `/api/kr/chatbot/history?session_id=${encodeURIComponent(targetSessionId)}&index=${idx}&_t=${Date.now()}`,
          {
            method: 'DELETE',
            headers,
          }
        );
        if (!res.ok) {
          throw new Error(`Delete turn failed at index ${idx}: ${res.status}`);
        }
      }

      await fetchHistory(targetSessionId);
      await fetchSessions();
    } catch (e) {
      console.error("Turn delete failed", e);
      setMessages(previousMessages);
      setAlertModal({
        isOpen: true,
        type: 'danger',
        title: '질문/답변 삭제 실패',
        content: '질문과 답변 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
      });
    } finally {
      setIsTurnDeleteModalOpen(false);
      setTurnDeleteTargetIndex(null);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setAttachedFiles(prev => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  const removeFile = (idx: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== idx));
  };



  return (
    <div className="h-screen w-full flex bg-[#131314] text-white overflow-hidden">
      {/* Global Sidebar (Fixed) */}
      <Sidebar />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        profile={userProfile}
        onSave={saveUserProfile}
      />

      {/* Mobile Sidebar Overlay */}
      {isMobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={closeMobileSidebar}></div>
          <div className="relative w-[280px] bg-[#1e1f20] h-full shadow-2xl flex flex-col animate-slide-in-left border-r border-white/10">
            <div className="p-4 flex justify-between items-center border-b border-white/5 bg-[#131314]">
              <button className="flex items-center gap-2" aria-expanded={isMenuExpanded} onClick={() => setIsMenuExpanded(prev => !prev)}>
                <span className="font-bold text-gray-200 text-lg">메뉴</span>
                <i className={`fas fa-chevron-${isMenuExpanded ? 'up' : 'down'} text-xs text-gray-500 transition-transform duration-200`}></i>
              </button>
              <button onClick={closeMobileSidebar} aria-label="메뉴 닫기" className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
                <i className="fas fa-times"></i>
              </button>
            </div>

            {/* Navigation Section */}
            <div inert={!isMenuExpanded} className={`overflow-hidden transition-all duration-300 ease-in-out ${isMenuExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'}`}>
              <div className="p-2 space-y-1 border-b border-white/5 bg-[#18181b]">
                <Link href="/dashboard/kr" onClick={closeMobileSidebar} className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-home w-5 text-center text-gray-400"></i>
                  <span>대시보드 홈</span>
                </Link>
                <Link href="/dashboard/kr/vcp" onClick={closeMobileSidebar} className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-chart-line w-5 text-center text-blue-400"></i>
                  <span>VCP 스크리너</span>
                </Link>
                <Link href="/dashboard/kr/closing-bet" onClick={closeMobileSidebar} className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-chess-knight w-5 text-center text-purple-400"></i>
                  <span>종가베팅</span>
                </Link>
                <Link href="/dashboard/kr/cumulative" onClick={closeMobileSidebar} className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-chart-bar w-5 text-center text-yellow-500"></i>
                  <span>누적 성과</span>
                </Link>
                <Link href="/dashboard/data-status" onClick={closeMobileSidebar} className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-database w-5 text-center text-emerald-400"></i>
                  <span>데이터 관리</span>
                </Link>
                <button
                  onClick={() => {
                    setIsPaperTradingOpen(true);
                    closeMobileSidebar();
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors text-left"
                >
                  <i className="fas fa-wallet w-5 text-center text-emerald-400"></i>
                  <span>모의투자</span>
                </button>
              </div>
            </div>

            <div className="p-4 flex-shrink-0">
              <button
                onClick={() => {
                  handleNewChat();
                  closeMobileSidebar();
                }}
                className="w-full flex items-center gap-3 px-4 py-3 bg-[#2a2b2d] hover:bg-[#333537] text-gray-200 rounded-xl transition-all shadow-sm text-sm font-medium border border-white/5 active:scale-95"
              >
                <i className="fas fa-plus text-gray-400"></i>
                <span>새 채팅</span>
              </button>
            </div>

            <div className="px-4 pb-2 text-xs font-semibold text-gray-500 mt-2">최근 대화</div>
            <div className="flex-1 overflow-y-auto px-2 space-y-1 custom-scrollbar">
              {sessions.length > 0 ? (
                sessions.map(session => (
                  <div
                    key={session.id}
                    className={`group relative w-full rounded-lg text-sm transition-colors flex items-center ${currentSessionId === session.id
                      ? 'bg-[#004a77]/40 text-blue-100'
                      : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                      }`}
                  >
                    <button
                      onClick={() => {
                        setCurrentSessionId(session.id);
                        closeMobileSidebar();
                      }}
                      aria-current={currentSessionId === session.id ? 'true' : undefined}
                      className="flex-1 min-w-0 flex items-center gap-3 text-left px-3 py-3"
                    >
                      <i className={`far fa-comment-alt text-xs flex-shrink-0 ${currentSessionId === session.id ? 'text-blue-400' : 'text-gray-500'}`}></i>
                      <span className="truncate flex-1">{session.title}</span>
                    </button>
                    <button
                      onClick={() => handleDeleteSession(session.id)}
                      aria-label={`${session.title} 삭제`}
                      className="p-2 text-gray-500 hover:text-red-400 transition-colors"
                    >
                      <i className="fas fa-trash-alt text-xs"></i>
                    </button>
                  </div>
                ))
              ) : (
                <div className="px-3 py-10 text-center text-xs text-gray-600 flex flex-col items-center gap-2">
                  <i className="far fa-comment-dots text-2xl opacity-50"></i>
                  <p>저장된 대화가 없습니다.</p>
                </div>
              )}
            </div>

            {/* Mobile Sidebar Footer (Profile) */}
            <div className="p-4 border-t border-white/5 bg-[#131314]">
              <button onClick={() => { setIsSettingsOpen(true); closeMobileSidebar(); }} className="flex items-center gap-3 w-full text-left">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-xs ring-2 ring-[#131314] shadow-lg">
                  {displayProfile.name.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-gray-200 truncate">{displayProfile.name}</div>
                  <div className="text-xs text-gray-500 truncate">{displayProfile.email}</div>
                </div>
                <i className="fas fa-cog text-gray-500"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmationModal
        isOpen={isDeleteModalOpen}
        title="대화 삭제"
        message={`정말 이 대화를 삭제하시겠습니까?\n삭제된 대화는 복구할 수 없습니다.`}
        onConfirm={confirmDeleteSession}
        onCancel={() => setIsDeleteModalOpen(false)}
        confirmText="삭제"
        cancelText="취소"
      />

      <ConfirmationModal
        isOpen={isMessageDeleteModalOpen}
        title="메시지 삭제"
        message={`이 메시지를 삭제하시겠습니까?\n삭제된 메시지는 복구할 수 없습니다.`}
        onConfirm={confirmDeleteMessage}
        onCancel={() => {
          setIsMessageDeleteModalOpen(false);
          setMessageToDeleteIndex(null);
        }}
        confirmText="삭제"
        cancelText="취소"
      />

      <ConfirmationModal
        isOpen={isTurnDeleteModalOpen}
        title="질문/답변 삭제"
        message={`이 질문과 답변을 함께 삭제하시겠습니까?\n삭제된 내용은 복구할 수 없습니다.`}
        onConfirm={confirmDeleteTurn}
        onCancel={() => {
          setIsTurnDeleteModalOpen(false);
          setTurnDeleteTargetIndex(null);
        }}
        confirmText="삭제"
        cancelText="취소"
      />

      <Modal
        isOpen={alertModal.isOpen}
        onClose={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
        title={alertModal.title}
        type={alertModal.type}
        footer={
          <button
            onClick={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
            className={`px-4 py-2 rounded-lg text-sm font-bold text-white transition-colors ${alertModal.type === 'danger' ? 'bg-red-500 hover:bg-red-600' :
              alertModal.type === 'success' ? 'bg-emerald-500 hover:bg-emerald-600' :
                'bg-blue-500 hover:bg-blue-600'
              }`}
          >
            확인
          </button>
        }
      >
        <p>{alertModal.content}</p>
      </Modal>

      <PaperTradingModal
        isOpen={isPaperTradingOpen}
        onClose={() => setIsPaperTradingOpen(false)}
      />

      {/* Content Wrapper */}
      <div className="flex-1 flex pl-0 lg:pl-64 h-full">

        {/* Sessions Sidebar */}
        <div className="w-[260px] flex-shrink-0 flex flex-col bg-[#1e1f20] hidden lg:flex border-r border-white/5">
          <div className="p-4">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center gap-3 px-4 py-3 bg-[#2a2b2d] hover:bg-[#333537] text-gray-200 rounded-xl transition-all shadow-sm text-sm font-medium"
            >
              <i className="fas fa-plus text-gray-400"></i>
              <span>새 채팅</span>
            </button>
          </div>

          <div className="px-4 pb-2 text-xs font-semibold text-gray-500 mt-2">최근 대화</div>
          <div className="flex-1 overflow-y-auto px-2 space-y-1 custom-scrollbar">
            {sessions.length > 0 ? (
              sessions.map(session => (
                <div
                  key={session.id}
                  className={`group relative w-full rounded-lg text-sm transition-colors flex items-center ${currentSessionId === session.id
                    ? 'bg-[#004a77]/40 text-blue-100'
                    : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                    }`}
                >
                  <button
                    onClick={() => setCurrentSessionId(session.id)}
                    aria-current={currentSessionId === session.id ? 'true' : undefined}
                    className="flex-1 min-w-0 flex items-center gap-2 text-left px-3 py-2.5"
                  >
                    <i className={`far fa-comment-alt text-xs ${currentSessionId === session.id ? 'text-blue-400' : 'text-gray-500'}`}></i>
                    <span className="truncate flex-1">{session.title}</span>
                  </button>
                  <button
                    onClick={() => handleDeleteSession(session.id)}
                    aria-label={`${session.title} 삭제`}
                    className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 p-1 text-gray-500 hover:text-red-400 transition-opacity absolute right-2 bg-[#1e1f20]/80 rounded shadow-sm"
                  >
                    <i className="fas fa-trash-alt text-xs"></i>
                  </button>
                </div>
              ))
            ) : (
              <div className="px-3 py-4 text-center text-xs text-gray-600">
                <p>저장된 대화가 없습니다.</p>
              </div>
            )}
          </div>

          {/* Bottom Menu - Settings (Removed as requested) */}
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#000000] h-full overflow-hidden relative">

          {/* Top Bar */}
          <div className="h-14 flex items-center justify-between px-4 md:px-6 fixed top-0 left-0 right-0 lg:left-[calc(16rem+260px)] z-20 bg-[#000000]/80 backdrop-blur-sm border-b border-white/5 md:border-none transition-all">
            <div className="flex items-center gap-3 text-gray-200">
              {/* Hamburger Button (Mobile) */}
              <button
                ref={mobileMenuTriggerRef}
                onClick={() => setIsMobileSidebarOpen(true)}
                aria-label="메뉴 열기"
                className="lg:hidden w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 active:bg-white/20 transition-colors -ml-2"
              >
                <i className="fas fa-bars text-lg text-gray-300"></i>
              </button>

              <button className="flex items-center gap-2" aria-expanded={showCommands} onClick={() => setShowCommands(!showCommands)}>
                <span className="text-lg font-bold opacity-90 hover:opacity-100">스마트머니봇</span>
                {currentModel.includes("pro") && <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded font-bold">PRO</span>}
              </button>
            </div>
            <div className="flex items-center gap-3">
              {/* User Avatar - Initials */}
              <button
                className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-xs ring-2 ring-[#131314] shadow-lg"
                title={displayProfile.name}
                aria-label="프로필 설정 열기"
                onClick={() => setIsSettingsOpen(true)}
              >
                {displayProfile.name.slice(0, 2).toUpperCase()}
              </button>
            </div>
          </div>

          {/* Chat Content */}
          <main className="flex-1 overflow-y-auto relative custom-scrollbar pt-14">
            <div className="max-w-3xl mx-auto px-4 py-8 min-h-full flex flex-col">

              {/* Empty State */}
              {messages.length === 0 ? (
                <div className="flex-1 flex flex-col justify-center items-center space-y-6 md:space-y-8 mt-4 md:mt-20 animate-fade-in">
                  <div className="space-y-2 text-center px-4">
                    <h1 className="text-2xl md:text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-[#4285f4] via-[#9b72cb] to-[#d96570] animate-fade-in-up break-keep leading-tight">
                      안녕하세요, {displayProfile.name}님
                    </h1>
                    <h2 className="text-lg md:text-4xl font-bold text-[#444746] opacity-50 animate-fade-in-up delay-100 break-keep leading-tight">
                      무엇을 도와드릴까요?
                    </h2>
                  </div>

                  {/* Suggestions */}
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 md:gap-3 w-full max-w-4xl animate-fade-in-up delay-200 px-4 md:px-0">
                    {suggestions.slice(0, 4).map((card, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSend(card.prompt)}
                        className="bg-[#1e1f20] hover:bg-[#333537] p-3 md:p-4 rounded-2xl text-left transition-all h-32 md:h-48 flex flex-col justify-between group relative overflow-hidden border border-white/5 active:scale-95 duration-200"
                      >
                        {/* Background Icon - Reduced opacity and size for mobile */}
                        <div className="absolute top-0 right-0 p-2 md:p-3 opacity-5 md:opacity-10 group-hover:opacity-20 transition-opacity">
                          <i className={`${card.icon} text-2xl md:text-4xl`}></i>
                        </div>

                        <div className="text-[11px] md:text-sm text-gray-300 font-medium z-10 break-keep line-clamp-3 leading-relaxed">
                          {card.desc}
                        </div>

                        <div className="self-end w-6 h-6 md:w-8 md:h-8 rounded-full bg-black/20 group-hover:bg-white/20 flex items-center justify-center transition-colors z-10">
                          <i className={`${card.icon} text-[10px] md:text-xs text-gray-400 group-hover:text-white`}></i>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                /* Messages List */
                <div className="space-y-10">
                  {messages.map((msg, idx) => (
                    <ChatMessage
                      key={idx}
                      message={msg}
                      index={idx}
                      onDeleteTurn={handleDeleteTurn}
                      onDeleteMessage={handleDeleteMessage}
                      onSuggestionClick={handleSend}
                    />
                  ))}





                  {isBusy && (
                    <div className="flex gap-4 animate-fade-in">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex-shrink-0 flex items-center justify-center mt-1 animate-pulse">
                        <i className="fas fa-sparkles text-xs text-white"></i>
                      </div>
                      <div className="space-y-2 pt-2">
                        <div className="text-sm text-gray-400 font-medium flex items-center gap-2">
                          <i className="fas fa-circle-notch fa-spin text-blue-400"></i>
                          <span className="animate-pulse">{LOADING_STEPS[loadingStep]}</span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </main>

          {/* Footer (Input Area) */}
          <footer className="flex-shrink-0 p-4 bg-[#131314] border-t border-white/5 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
            <div className="max-w-3xl mx-auto">
              {showCommands && filteredCommands.length > 0 && (
                <div className="relative z-40 mb-4 w-full max-h-64 overflow-y-auto bg-[#1e1f20] border border-white/10 rounded-xl shadow-2xl animate-fade-in-up">
                  <div className="text-xs font-bold text-gray-400 px-4 py-2 border-b border-white/5 bg-black/20">사용 가능한 명령어</div>
                  {filteredCommands.map((c, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setShowCommands(false);
                        handleSend(c.cmd);
                        inputRef.current?.focus();
                      }}
                      className={`w-full text-left px-4 py-3 text-sm flex justify-between items-center transition-colors ${i === selectedCommandIndex
                        ? 'bg-blue-600/20 text-white'
                        : 'text-gray-200 hover:bg-white/5'
                        }`}
                    >
                      <span className={`font-mono font-bold ${i === selectedCommandIndex ? 'text-blue-300' : 'text-blue-400'}`}>
                        {c.cmd}
                      </span>
                      <span className="text-xs text-gray-500">{c.desc}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Floating Toolbar (Suggestions & Model Selector) */}
              <div className="mb-4 px-4 pointer-events-none flex flex-col items-center gap-3">
                {/* 1. Suggestions (Wrapped) */}
                {messages.length === 0 && (
                  <div className="flex flex-wrap justify-center gap-2 pointer-events-auto max-w-full">
                    {suggestions.map((card, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSend(card.prompt)}
                        className="px-3 py-1.5 bg-[#1e1f20]/90 backdrop-blur-md hover:bg-blue-600 hover:text-white border border-white/10 rounded-full text-[11px] text-gray-300 transition-all shadow-lg active:scale-95"
                      >
                        {card.title}
                      </button>
                    ))}
                  </div>
                )}

                {/* 2. Model Selector (Mobile Only - Moved from Input Bar) */}
                <div className="pointer-events-auto md:hidden relative group">
                  <button
                    className="flex items-center gap-2 px-3 py-1.5 bg-[#1e1f20]/90 backdrop-blur-md border border-white/10 rounded-full text-xs text-gray-300 shadow-lg"
                  >
                    <i className="fas fa-sparkles text-blue-400"></i>
                    <span>{currentModel.split('-').pop()?.toUpperCase() || 'MODEL'}</span>
                    <i className="fas fa-chevron-down text-[10px] text-gray-500"></i>
                  </button>
                  {/* Selector Dropup for Mobile */}
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-48 bg-[#2a2b2d] border border-white/10 rounded-xl shadow-xl overflow-hidden invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all z-40">
                    {models.map(m => (
                      <button
                        key={m}
                        onClick={() => setCurrentModel(m)}
                        className={`w-full text-left px-4 py-2.5 text-xs hover:bg-white/5 flex items-center justify-between ${currentModel === m ? 'text-blue-400' : 'text-gray-300'}`}
                      >
                        <span>{m}</span>
                        {currentModel === m && <i className="fas fa-check"></i>}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="relative bg-[#1e1f20] rounded-[28px] focus-within:bg-[#2a2b2d] focus-within:ring-1 focus-within:ring-white/20 transition-all shadow-lg">

                {/* Attached Files Preview */}
                {attachedFiles.length > 0 && (
                  <div className="px-4 pt-3 flex gap-2 overflow-x-auto custom-scrollbar">
                    {attachedFiles.map((file, idx) => (
                      <div key={idx} className="relative group shrink-0">
                        <div className="w-16 h-16 rounded-lg bg-black/40 border border-white/10 flex items-center justify-center overflow-hidden">
                          {file.type.startsWith('image/') ? (
                            <img src={URL.createObjectURL(file)} alt="preview" className="w-full h-full object-cover" />
                          ) : (
                            <i className="fas fa-file text-gray-400 text-xl"></i>
                          )}
                        </div>
                        <button
                          onClick={() => removeFile(idx)}
                          aria-label={`${file.name} 첨부 제거`}
                          className="absolute -top-1 -right-1 w-5 h-5 bg-gray-600 rounded-full flex items-center justify-center text-white text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <i className="fas fa-times"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex items-center pl-2 pr-2 py-2 gap-2">
                  {/* Plus Button */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex-shrink-0 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-colors"
                    title="파일 첨부"
                    aria-label="파일 첨부"
                  >
                    <i className="fas fa-plus-circle text-lg"></i>
                  </button>
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    multiple
                    onChange={handleFileSelect}
                    accept="image/*,.pdf,.csv,.xlsx,.xls,.txt"
                  />

                  {/* Tools / Model Selector (Desktop Only) */}
                  <div className="relative group flex-shrink-0 hidden md:block">
                    <button
                      className="flex items-center gap-2 px-3 py-1.5 bg-black/20 hover:bg-white/10 rounded-full text-xs text-gray-300 transition-colors border border-white/5 h-8"
                    >
                      <i className="fas fa-sparkles text-blue-400"></i>
                      <span>{currentModel.split('-').pop()?.toUpperCase() || 'MODEL'}</span>
                      <i className="fas fa-chevron-down text-[10px] text-gray-500"></i>
                    </button>
                    {/* Selector Dropup */}
                    <div className="absolute bottom-full left-0 mb-2 w-48 bg-[#2a2b2d] border border-white/10 rounded-xl shadow-xl overflow-hidden invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-all z-30">
                      {models.map(m => (
                        <button
                          key={m}
                          onClick={() => setCurrentModel(m)}
                          className={`w-full text-left px-4 py-2.5 text-xs hover:bg-white/5 flex items-center justify-between ${currentModel === m ? 'text-blue-400' : 'text-gray-300'}`}
                        >
                          <span>{m}</span>
                          {currentModel === m && <i className="fas fa-check"></i>}
                        </button>
                      ))}
                    </div>
                  </div>



                  {/* Textarea */}
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      // Auto-resize
                      e.target.style.height = 'auto';
                      e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
                    }}
                    onKeyDown={handleKeyDown}
                    onCompositionStart={() => { isComposing.current = true; }}
                    onCompositionEnd={() => { isComposing.current = false; }}
                    onBlur={() => {
                      if (window.innerWidth < 1024) {
                        window.scrollTo(0, 0);
                        document.body.scrollTop = 0;
                      }
                    }}
                    placeholder="메시지 입력..."
                    className="flex-1 bg-transparent text-white px-2 resize-none max-h-[200px] focus:outline-none custom-scrollbar leading-relaxed py-2"
                    style={{ height: 'auto', minHeight: '40px' }}
                    rows={1}
                  />

                  {/* Right Actions */}
                  <div className="flex items-center gap-1">
                    {/* Mic Button */}
                    <button
                      onClick={toggleRecording}
                      className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-colors ${isRecording ? 'text-red-500 bg-red-500/10 animate-pulse' : 'text-gray-400 hover:text-white hover:bg-white/10'}`}
                      title="음성 입력"
                      aria-label="음성 입력"
                    >
                      <i className={`fas fa-microphone ${isRecording ? 'fa-beat' : ''}`}></i>
                    </button>

                    {/* Send / Stop Button */}
                    <div className="relative">
                      {isBusy ? (
                        <button
                          onClick={handleStop}
                          className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white bg-gray-700 hover:bg-gray-600 transition-all shadow-lg animate-fade-in"
                          title="답변 중단"
                          aria-label="답변 중단"
                        >
                          <div className="w-3 h-3 bg-white rounded-sm"></div>
                        </button>
                      ) : (
                        (input.trim() || attachedFiles.length > 0) ? (
                          <button
                            onClick={() => handleSend(input)}
                            aria-label="보내기"
                            className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:hover:bg-blue-600 transition-all shadow-lg animate-fade-in"
                          >
                            <i className="fas fa-paper-plane text-xs"></i>
                          </button>
                        ) : null
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="text-center mt-2 text-[10px] text-gray-500">
                AI는 100% 정확하지 않을 수 있습니다.
              </div>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}
