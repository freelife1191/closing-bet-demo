'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { fetchAPI } from '@/lib/api';

import remarkGfm from 'remark-gfm';
import Link from 'next/link';
import Sidebar from '../components/Sidebar';
import SettingsModal from '../components/SettingsModal';
import ConfirmationModal from '../components/ConfirmationModal';
import Modal from '../components/Modal';
import PaperTradingModal from '../components/PaperTradingModal';
import ThinkingProcess from '../components/ThinkingProcess';
import { getStoredModel, setStoredModel, shouldSendOnEnter } from '../components/chatHelpers';

// Types
interface Message {
  role: 'user' | 'model';
  parts: (string | { text: string })[];
  timestamp?: string;
  isStreaming?: boolean;
  reasoning?: string;
}

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
}

interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructorLike = new () => SpeechRecognitionLike;
type WindowWithSpeechRecognition = Window & {
  SpeechRecognition?: SpeechRecognitionConstructorLike;
  webkitSpeechRecognition?: SpeechRecognitionConstructorLike;
};

interface Session {
  id: string;
  title: string;
  updated_at: string;
  model?: string;
}

interface SuggestionCard {
  title: string;
  desc: string;
  icon: string;
  prompt: string;
}

const getTurnIndicesFromMessage = (messages: Message[], index: number): number[] => {
  const current = messages[index];
  if (!current) return [];

  const prev = messages[index - 1];
  const next = messages[index + 1];

  if (current.role === 'user' && next?.role === 'model') {
    return [index, index + 1];
  }

  if (current.role === 'model' && prev?.role === 'user') {
    return [index - 1, index];
  }

  // 비정상 히스토리 대비
  return [index];
};

const getMessagePartText = (part: Message['parts'][number] | undefined): string => {
  if (!part) return '';
  return typeof part === 'string' ? part : part.text;
};

const SUGGESTIONS: SuggestionCard[] = [
  { title: '시장 현황', desc: '마켓게이트 상태와 투자 전략', icon: 'fas fa-chart-pie', prompt: '오늘 마켓게이트 상태와 투자 전략 알려줘' },
  { title: 'VCP 추천', desc: 'AI 분석 기반 매수 추천 종목', icon: 'fas fa-search-dollar', prompt: 'VCP AI 분석 결과 매수 추천 종목 알려줘' },
  { title: '종가 베팅', desc: '오늘의 S/A급 종가베팅 추천', icon: 'fas fa-chess-knight', prompt: '오늘의 종가베팅 S급, A급 추천해줘' },
  { title: '뉴스 분석', desc: '최근 주요 뉴스와 시장 영향', icon: 'fas fa-newspaper', prompt: '최근 주요 뉴스와 시장 영향 분석해줘' },
  { title: '내 관심종목', desc: '관심종목 진단 및 리스크 점검', icon: 'fas fa-heart', prompt: '내 관심종목 리스트 기반으로 현재 상태 진단해줘' },
];

// Helper to fix CJK markdown issues and malformed AI output
const preprocessMarkdown = (text: string) => {
  let processed = text;
  const removeLastUnmatchedMarker = (line: string, markerRegex: RegExp, markerLength: number): string => {
    const matches = [...line.matchAll(markerRegex)];
    if (matches.length % 2 === 1) {
      const idx = matches[matches.length - 1].index;
      if (typeof idx === 'number') {
        return line.slice(0, idx) + line.slice(idx + markerLength);
      }
    }
    return line;
  };

  // 1. Remove stray emphasis markers before ordered list starts (e.g. "****1. ")
  processed = processed.replace(/^\s*\*{3,}(?=\d+[.)]\s)/gm, '');

  // 2. Split section labels and first ordered item when they are stuck together.
  processed = processed.replace(/((?:\*\*|__)?\[[^\]\n]{1,20}\](?:\*\*|__)?)\s*(?=[1-9]\d?[.)])/g, '$1\n');

  // 3. Ensure space after ordered-list marker (e.g. "1.조선", "1.**제목**" -> "1. 조선", "1. **제목**")
  processed = processed.replace(/(?<!\d)([1-9]\d?[.)])(?=\*\*|__|[가-힣A-Za-z(])/g, '$1 ');

  // 4. Ensure emphasis opening marker is separated from previous word (opening marker only).
  // Avoid touching closing markers before punctuation (e.g. "**텍스트**:")
  processed = processed.replace(/([가-힣A-Za-z0-9])(?=(\*\*|__)\s*[가-힣A-Za-z0-9(])/g, '$1 ');

  // 5. Trim inner spaces in emphasis markers (covers both-sided or one-sided spaces).
  processed = processed.replace(/\*\*([^*\n]+)\*\*/g, (m, inner: string) => {
    const trimmed = inner.trim();
    return trimmed ? `**${trimmed}**` : m;
  });
  processed = processed.replace(/__([^_\n]+)__/g, (m, inner: string) => {
    const trimmed = inner.trim();
    return trimmed ? `__${trimmed}__` : m;
  });

  // 5-1. Remove trailing unmatched emphasis marker in a line.
  processed = processed
    .split('\n')
    .map((line) => {
      const balancedAsterisk = removeLastUnmatchedMarker(line, /(?<!\*)\*\*(?!\*)/g, 2);
      return removeLastUnmatchedMarker(balancedAsterisk, /(?<!_)__(?!_)/g, 2);
    })
    .join('\n');

  // 6. Normalize quoted emphasis wrappers: **"텍스트"** / **'텍스트'** -> **텍스트**
  processed = processed.replace(/\*\*\s*['"“”‘’]\s*([^*\n]+?)\s*['"“”‘’]\s*\*\*/g, '**$1**');
  processed = processed.replace(/__\s*['"“”‘’]\s*([^_\n]+?)\s*['"“”‘’]\s*__/g, '__$1__');

  // 7. Ensure spacing after closing emphasis marker when attached to text.
  processed = processed.replace(/(?<=\S)(\*\*|__)(?=[가-힣A-Za-z0-9])/g, '$1 ');

  // 8. Fix CJK boundary issues: "**Bold**Suffix" -> "**Bold** Suffix"
  processed = processed.replace(/\*\*([A-Za-z0-9가-힣(][^*\n]*?)\*\*([가-힣])/g, '**$1** $2');
  processed = processed.replace(/__([A-Za-z0-9가-힣(][^_\n]*?)__([가-힣])/g, '__$1__ $2');

  return processed;
};

const extractSuggestions = (text: string, isStreaming: boolean = false, streamReasoning?: string) => {
  let processed = text;
  let suggestions: string[] = [];
  const hasStreamReasoning = typeof streamReasoning === 'string' && streamReasoning.length > 0;
  let reasoning = hasStreamReasoning ? streamReasoning : "";

  const suggestionMatch = processed.match(/(?:\*\*|__)?\\*\[\s*추천\s*질문\s*\\*\](?:\*\*|__)?[\s\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');

    const lines = sugText.split('\n');
    suggestions = lines
      .map(l => l.replace(/^(?:\d+\.|\-|\*)\s*/, '').trim())
      .filter(l => l.length > 0 && !l.replace(/\*/g, '').includes('[추천 질문]'))
      .map(l => l.replace(/\*\*/g, '')); // 별표 제거
  }

  const reasonStartRegex = /(?:\*\*|__)?\**\[\s*추론\s*과정\s*\]\**(?:\*\*|__)?/i;
  const reasonEndRegex = /(?:---|___|\*\*\*|)\s*(?:\n)*\s*(?:\*\*|__)?\**\[\s*답변\s*\]\**(?:\*\*|__)?/i;

  if (!hasStreamReasoning) {
    // Fallback parser for legacy/history messages where reasoning and answer are mixed in one text.
    const startMatch = processed.match(reasonStartRegex);
    const endMatch = processed.match(reasonEndRegex);

    if (startMatch) {
      if (endMatch) {
        // Both start and end exist (fully generated or streaming past reasoning)
        const reasoningBlock = processed.substring(startMatch.index!, endMatch.index!);
        reasoning = reasoningBlock;
        processed = processed.substring(0, startMatch.index!) + processed.substring(endMatch.index!); // Remove the reasoning block from the visible chat
      } else if (isStreaming) {
        // Stream is active, and only start tag exists. Everything after start is reasoning.
        reasoning = processed.substring(startMatch.index!);
        processed = processed.substring(0, startMatch.index!); // The visible text is empty (or whatever was before the reasoning)
      } else {
        // Non-streaming fallback:
        // If [답변] header is missing, do not hide the whole body as reasoning-only.
        // Keep full text in answer area to prevent empty final answer.
        reasoning = "";
      }
    } else if (isStreaming) {
      // FALLBACK: Aggressively match incomplete reasoning tags during early streaming
      if (!endMatch && processed.trim().length > 0 && processed.trim().length < 50) {
        // If the stream just started and starts with typical tag characters
        if (processed.trim().startsWith('*') || processed.trim().startsWith('[')) {
          reasoning = processed;
          processed = '';
        }
      }
    }
  }

  // Strip '[답변]' markers and horizontal rules just before it
  processed = processed.replace(reasonEndRegex, '');

  // FORCE newlines before numbered lists inside dense text
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  processed = processed.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');

  const reasoningHeaderRegex = /^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|__)?\s*\n?/i;
  let cleanReasoning = preprocessMarkdown(reasoning).replace(reasoningHeaderRegex, '').trim();

  // Cleanup trailing broken markdown
  if (isStreaming) {
    cleanReasoning = cleanReasoning.replace(/[\*\_\[\]]+$/, '');
  }

  // FORCE newlines before numbered lists inside dense text (e.g., "내용 2. ")
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  cleanReasoning = cleanReasoning.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');

  return { content: processed.trim(), suggestions, reasoning: cleanReasoning };
};

export default function ChatbotPage() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [currentModel, setCurrentModelState] = useState<string>('');
  const setCurrentModel = useCallback((model: string) => {
    setCurrentModelState(model);
    setStoredModel(model);
  }, []);

  // Session State
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  // Command State
  const [showCommands, setShowCommands] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);

  // File & Voice States
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null); // To control recognition instance

  // User Profile State
  const [userProfile, setUserProfile] = useState<{ name: string; email: string; persona: string } | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false); // Mobile Sidebar State
  const [isMenuExpanded, setIsMenuExpanded] = useState(true); // Menu Parsing State

  // Delete Modal State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [sessionToDeleteId, setSessionToDeleteId] = useState<string | null>(null);
  const [isMessageDeleteModalOpen, setIsMessageDeleteModalOpen] = useState(false);
  const [messageToDeleteIndex, setMessageToDeleteIndex] = useState<number | null>(null);
  const [isTurnDeleteModalOpen, setIsTurnDeleteModalOpen] = useState(false);
  const [turnDeleteIndices, setTurnDeleteIndices] = useState<number[]>([]);

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
  const isComposing = useRef(false); // Track IME composition state
  const isCreatingSessionRef = useRef(false); // To prevent history fetch on new session creation

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
  const [suggestions, setSuggestions] = useState<SuggestionCard[]>(SUGGESTIONS);

  /* 
  // [Optimization] 페이지 진입 시 알트(Alt) Gemini API 호출 중단 요청 반영
  // 사용자가 직접 요청하지 않았는데 불필요하게 Quota를 소모하는 문제 방지
  useEffect(() => {
    const fetchSuggestions = async () => {
      // ... (Removed auto-fetch logic) ...
    };
    // fetchSuggestions();
  }, [userProfile?.persona]);
  */

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoading) {
      setLoadingStep(0);
      interval = setInterval(() => {
        setLoadingStep(prev => (prev < LOADING_STEPS.length - 1 ? prev + 1 : prev));
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  // Commands Definition
  const COMMANDS = [
    { cmd: '/help', desc: '도움말 확인' },
    { cmd: '/status', desc: '현재 상태(모델, 메모리) 확인' },
    { cmd: '/memory view', desc: '저장된 메모리 보기' },
    { cmd: '/clear', desc: '현재 대화 초기화' },
    { cmd: '/clear all', desc: '모든 대화 및 메모리 초기화' },
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
          setUserProfile(JSON.parse(cachedProfile));
        } catch (e) { console.error("Cache clean needed"); }
      } else {
        // Default fallback if no cache
        setUserProfile({ name: '흑기사', email: 'user@example.com', persona: '' });
      }
    };
    loadProfile();

    // Listen for profile updates from Sidebar
    window.addEventListener('user-profile-updated', loadProfile);

    // 2. Load Local Cache for Session ID (Optimistic Restore)
    const cachedSessionId = localStorage.getItem('chatbot_last_session_id');
    if (cachedSessionId) {
      setCurrentSessionId(cachedSessionId);
    }

    fetchModels();

    // Fetch sessions list (Logic separated from restoration to prevent race condition)
    fetchSessions();

    // We don't fetch user profile from backend here anymore to avoid overwriting sidebar settings
    // or we fetch it but save it to the global key? Better to rely on sidebar state as source of truth for now.

    return () => {
      window.removeEventListener('user-profile-updated', loadProfile);
    };
  }, []);

  // UseEffect for cleanup voice
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    }
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

  // Load History when Session Changes
  useEffect(() => {
    if (currentSessionId) {
      if (isCreatingSessionRef.current) {
        isCreatingSessionRef.current = false;
      } else {
        fetchHistory(currentSessionId);
      }
      localStorage.setItem('chatbot_last_session_id', currentSessionId);
    } else {
      setMessages([]); // New Chat
    }
  }, [currentSessionId]);

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

  // Helper: Get Auth Headers
  const getAuthHeaders = () => {
    let sessionId = localStorage.getItem('browser_session_id');
    if (!sessionId) {
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        sessionId = 'anon_' + crypto.randomUUID();
      } else {
        // Fallback for non-secure contexts or older browsers
        sessionId = 'anon_' + Math.random().toString(36).substring(2) + Date.now().toString(36);
      }
      localStorage.setItem('browser_session_id', sessionId);
    }

    const headers: Record<string, string> = {
      'X-Session-Id': sessionId
    };

    // User Profile Email
    const savedProfile = localStorage.getItem('user_profile');
    if (savedProfile) {
      try {
        const p = JSON.parse(savedProfile);
        if (p.email && p.email !== 'user@example.com') {
          headers['X-User-Email'] = p.email;
        }
      } catch (e) { }
    }

    return headers;
  };

  const fetchSessions = async (): Promise<Session[]> => {
    try {
      const headers = getAuthHeaders();
      const data: any = await fetchAPI('/api/kr/chatbot/sessions', {
        headers
      });
      if (data.sessions) {
        setSessions(data.sessions);
        return data.sessions;
      }
    } catch (e) {
      console.error("Failed to fetch sessions", e);
    }
    return [];
  };

  const fetchHistory = async (sessionId: string) => {
    try {
      setIsLoading(true); // Show loading state
      const headers = getAuthHeaders();
      const data: any = await fetchAPI(`/api/kr/chatbot/history?session_id=${sessionId}`, {
        headers
      });
      if (data.history) {
        setMessages(data.history);
      } else {
        setMessages([]);
      }
    } catch (error) {
      console.error('Failed to fetch history:', error);
      setMessages([{ role: 'model', parts: ['⚠️ 대화 기록을 불러오는데 실패했습니다.'] }]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUserProfile = async () => {
    try {
      const data: any = await fetchAPI('/api/kr/chatbot/profile');
      if (data.profile) {
        setUserProfile(data.profile);
        // Update Cache
        localStorage.setItem('chatbot_user_profile', JSON.stringify(data.profile));
      }
    } catch (e) {
      console.error("Failed to fetch profile", e);
    }
  };

  const updateUserProfile = async (name: string, email: string, persona: string) => {
    try {
      // Optimistic UI
      const newProfile = { name, email, persona };
      setUserProfile(newProfile);
      localStorage.setItem('user_profile', JSON.stringify(newProfile));
      window.dispatchEvent(new Event('user-profile-updated'));

      const res = await fetch('/api/kr/chatbot/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, persona })
      });
      const data = await res.json();
    } catch (e) {
      console.error("Failed to update profile", e);
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
      handleSend();
    }
  };

  const abortControllerRef = useRef<AbortController | null>(null);

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
      setMessages(prev => [...prev, { role: 'model', parts: ['🛑 답변 생성이 중단되었습니다.'] }]);
    }
  };

  const handleSend = async (text: string = input) => {
    if ((!text.trim() && attachedFiles.length === 0) || isLoading) return;

    // Display User Message locally first
    const displayMsg = text + (attachedFiles.length > 0 ? `\n[파일 ${attachedFiles.length}개 첨부]` : '');
    const userMsg: Message = {
      role: 'user',
      parts: [displayMsg],
      timestamp: new Date().toISOString()
    };

    // Optimistic update
    setMessages(prev => [...prev, userMsg]);

    // Korean IME fix: simpler reset
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'; // Reset height
    }
    setTimeout(() => {
      isComposing.current = false;
    }, 0);

    setAttachedFiles([]);
    setShowCommands(false);
    setIsLoading(true);

    // Create new AbortController
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let res;
      const savedWatchlist = localStorage.getItem('watchlist');
      const watchlist = savedWatchlist ? JSON.parse(savedWatchlist) : [];

      // Auth Headers
      const headers = getAuthHeaders();

      // Prepare Request
      if (attachedFiles.length > 0) {
        const formData = new FormData();
        formData.append('message', text);
        if (currentModel) formData.append('model', currentModel);
        if (currentSessionId) formData.append('session_id', currentSessionId);
        if (watchlist.length > 0) formData.append('watchlist', JSON.stringify(watchlist));
        if (userProfile?.persona) formData.append('persona', userProfile.persona);

        attachedFiles.forEach(file => {
          formData.append('file', file);
        });

        // Add headers to fetch options. 
        // Note: For FormData, Content-Type is auto-set.
        // But our getAuthHeaders might not set Content-Type (which is good).

        res = await fetch('/api/kr/chatbot', {
          method: 'POST',
          headers: headers, // Pass auth headers
          body: formData,
          signal: controller.signal
        });
      } else {
        // For JSON, we need Content-Type
        headers['Content-Type'] = 'application/json';

        res = await fetch('/api/kr/chatbot', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({
            message: text,
            model: currentModel,
            session_id: currentSessionId,
            watchlist: watchlist,
            persona: userProfile?.persona
          }),
          signal: controller.signal
        });
      }

      const contentType = (res.headers.get('content-type') || '').toLowerCase();

      if (contentType.includes('text/event-stream') && res.body) {
        setIsLoading(false);
        setMessages(prev => [...prev, { role: 'model', parts: [""], reasoning: "", isStreaming: true }]);

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let done = false;
        let buffer = "";

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (value) {
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
              if (part.startsWith("data: ")) {
                const dataStr = part.substring(6);
                if (!dataStr.trim()) continue;
                try {
                  const data = JSON.parse(dataStr);
                  if (data.error) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], parts: [data.error], isStreaming: false };
                      return newMsgs;
                    });
                  }
                  if (data.clear) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = {
                        ...newMsgs[newMsgs.length - 1],
                        parts: [""],
                        reasoning: ""
                      };
                      return newMsgs;
                    });
                  }
                  if (data.answer_clear) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = { ...lastMsg, parts: [""] };
                      return newMsgs;
                    });
                  }
                  if (data.reasoning_clear) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = { ...lastMsg, reasoning: "" };
                      return newMsgs;
                    });
                  }

                  const answerDelta = typeof data.answer_chunk === 'string' ? data.answer_chunk : data.chunk;
                  if (typeof answerDelta === 'string' && answerDelta.length > 0) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      const currentText = getMessagePartText(lastMsg.parts[0]);
                      newMsgs[newMsgs.length - 1] = { ...lastMsg, parts: [currentText + answerDelta] };
                      return newMsgs;
                    });
                  }
                  if (typeof data.reasoning_chunk === 'string' && data.reasoning_chunk.length > 0) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      const currentReasoning = lastMsg.reasoning || "";
                      newMsgs[newMsgs.length - 1] = { ...lastMsg, reasoning: currentReasoning + data.reasoning_chunk };
                      return newMsgs;
                    });
                  }
                  if (data.session_id && data.session_id !== currentSessionId) {
                    isCreatingSessionRef.current = true;
                    setCurrentSessionId(data.session_id);
                    fetchSessions();
                  } else if (data.done) {
                    fetchSessions();
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], isStreaming: false };
                      return newMsgs;
                    });
                  }
                } catch (e) {
                  // ignore JSON parse error for partial chunks
                }
              }
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
          // If it's a new session, update state
          if (data.session_id && data.session_id !== currentSessionId) {
            isCreatingSessionRef.current = true; // Prevent history fetch overwriting optimistic state
            setCurrentSessionId(data.session_id);
            fetchSessions();
          } else {
            fetchSessions();
          }

          setMessages(prev => [...prev, { role: 'model', parts: [data.response] }]);
        } else if (data.error) {
          setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ 오류: ${data.error}`] }]);
        } else {
          setMessages(prev => [...prev, { role: 'model', parts: ['⚠️ 응답을 받아오지 못했습니다.'] }]);
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError') {
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
  };

  // Helper Actions
  const handleNewChat = () => {
    setCurrentSessionId(null);
    localStorage.removeItem('chatbot_last_session_id'); // Clear cache
    setMessages([]);
    setAttachedFiles([]);
    setInput('');
    inputRef.current?.focus();
  };

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
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

  const handleDeleteMessage = (e: React.MouseEvent, msgIndex: number) => {
    e.stopPropagation();
    if (isLoading) return;
    setMessageToDeleteIndex(msgIndex);
    setIsMessageDeleteModalOpen(true);
  };

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

  const handleDeleteTurn = (e: React.MouseEvent, msgIndex: number) => {
    e.stopPropagation();
    if (isLoading) return;

    const indices = getTurnIndicesFromMessage(messages, msgIndex);
    if (indices.length === 0) return;

    setTurnDeleteIndices(indices);
    setIsTurnDeleteModalOpen(true);
  };

  const confirmDeleteTurn = async () => {
    if (turnDeleteIndices.length === 0) return;

    const targetSessionId = currentSessionId;
    const targetIndices = [...turnDeleteIndices];
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
      setTurnDeleteIndices([]);
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

  const toggleRecording = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setAlertModal({
        isOpen: true,
        type: 'danger',
        title: '음성 인식 미지원',
        content: '이 브라우저는 음성 인식을 지원하지 않습니다.'
      });
      return;
    }

    if (isRecording) {
      // STOP
      setIsRecording(false);
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    } else {
      // START
      setIsRecording(true);
      const speechWindow = window as WindowWithSpeechRecognition;
      const SpeechRecognitionCtor =
        speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
      if (!SpeechRecognitionCtor) {
        setIsRecording(false);
        return;
      }
      const recognition = new SpeechRecognitionCtor();
      recognition.lang = 'ko-KR';
      recognition.interimResults = false;
      recognition.continuous = true;
      recognition.maxAlternatives = 1;

      recognition.onresult = (event: SpeechRecognitionEventLike) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setInput(prev => prev + (prev ? ' ' : '') + finalTranscript);
        }
      };

      recognition.onerror = (event: unknown) => {
        console.error("Speech error", event);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognition.start();
      recognitionRef.current = recognition;
    }
  };


  return (
    <div className="h-screen w-full flex bg-[#131314] text-white overflow-hidden">
      {/* Global Sidebar (Fixed) */}
      <Sidebar />

      {userProfile && (
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          profile={userProfile}
          onSave={updateUserProfile}
        />
      )}

      {/* Mobile Sidebar Overlay */}
      {isMobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={() => setIsMobileSidebarOpen(false)}></div>
          <div className="relative w-[280px] bg-[#1e1f20] h-full shadow-2xl flex flex-col animate-slide-in-left border-r border-white/10">
            <div className="p-4 flex justify-between items-center border-b border-white/5 bg-[#131314]">
              <div className="flex items-center gap-2 cursor-pointer" onClick={() => setIsMenuExpanded(!isMenuExpanded)}>
                <span className="font-bold text-gray-200 text-lg">메뉴</span>
                <i className={`fas fa-chevron-${isMenuExpanded ? 'up' : 'down'} text-xs text-gray-500 transition-transform duration-200`}></i>
              </div>
              <button onClick={() => setIsMobileSidebarOpen(false)} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
                <i className="fas fa-times"></i>
              </button>
            </div>

            {/* Navigation Section */}
            <div className={`overflow-hidden transition-all duration-300 ease-in-out ${isMenuExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'}`}>
              <div className="p-2 space-y-1 border-b border-white/5 bg-[#18181b]">
                <Link href="/dashboard/kr" className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-home w-5 text-center text-gray-400"></i>
                  <span>대시보드 홈</span>
                </Link>
                <Link href="/dashboard/kr/vcp" className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-chart-line w-5 text-center text-blue-400"></i>
                  <span>VCP 스크리너</span>
                </Link>
                <Link href="/dashboard/kr/closing-bet" className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-chess-knight w-5 text-center text-purple-400"></i>
                  <span>종가베팅</span>
                </Link>
                <Link href="/dashboard/kr/cumulative" className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-chart-bar w-5 text-center text-yellow-500"></i>
                  <span>누적 성과</span>
                </Link>
                <Link href="/dashboard/data-status" className="flex items-center gap-3 px-3 py-2.5 text-gray-300 hover:bg-white/5 rounded-lg text-sm transition-colors">
                  <i className="fas fa-database w-5 text-center text-emerald-400"></i>
                  <span>데이터 관리</span>
                </Link>
                <button
                  onClick={() => {
                    setIsPaperTradingOpen(true);
                    setIsMobileSidebarOpen(false);
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
                  setIsMobileSidebarOpen(false);
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
                    onClick={() => {
                      setCurrentSessionId(session.id);
                      setIsMobileSidebarOpen(false);
                    }}
                    className={`group relative w-full text-left px-3 py-3 rounded-lg text-sm transition-colors cursor-pointer flex items-center gap-3 ${currentSessionId === session.id
                      ? 'bg-[#004a77]/40 text-blue-100'
                      : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                      }`}
                  >
                    <i className={`far fa-comment-alt text-xs flex-shrink-0 ${currentSessionId === session.id ? 'text-blue-400' : 'text-gray-500'}`}></i>
                    <span className="truncate flex-1">{session.title}</span>

                    <button
                      onClick={(e) => handleDeleteSession(e, session.id)}
                      className="p-2 text-gray-500 hover:text-red-400 transition-colors z-10"
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
              <button onClick={() => { setIsSettingsOpen(true); setIsMobileSidebarOpen(false); }} className="flex items-center gap-3 w-full text-left">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-xs ring-2 ring-[#131314] shadow-lg">
                  {userProfile?.name.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-gray-200 truncate">{userProfile?.name}</div>
                  <div className="text-xs text-gray-500 truncate">{userProfile?.email}</div>
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
          setTurnDeleteIndices([]);
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
                  onClick={() => setCurrentSessionId(session.id)}
                  className={`group relative w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors cursor-pointer flex items-center gap-2 ${currentSessionId === session.id
                    ? 'bg-[#004a77]/40 text-blue-100'
                    : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                    }`}
                >
                  <i className={`far fa-comment-alt text-xs ${currentSessionId === session.id ? 'text-blue-400' : 'text-gray-500'}`}></i>
                  <span className="truncate flex-1">{session.title}</span>

                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-red-400 transition-opacity absolute right-2 bg-[#1e1f20]/80 rounded shadow-sm"
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
                onClick={() => setIsMobileSidebarOpen(true)}
                className="lg:hidden w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10 active:bg-white/20 transition-colors -ml-2"
              >
                <i className="fas fa-bars text-lg text-gray-300"></i>
              </button>

              <div className="flex items-center gap-2 cursor-pointer" onClick={() => setShowCommands(!showCommands)}>
                <span className="text-lg font-bold opacity-90 hover:opacity-100">스마트머니봇</span>
                {currentModel.includes("pro") && <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded font-bold">PRO</span>}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {/* User Avatar - Initials */}
              {userProfile && (
                <div
                  className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-xs ring-2 ring-[#131314] shadow-lg cursor-pointer"
                  title={userProfile.name}
                  onClick={() => setIsSettingsOpen(true)}
                >
                  {userProfile.name.slice(0, 2).toUpperCase()}
                </div>
              )}
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
                      안녕하세요, {userProfile?.name}님
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
                  {messages.map((msg, idx) => {
                    const rawText = getMessagePartText(msg.parts[0]);

                    const { content, suggestions, reasoning } = msg.role === 'model'
                      ? extractSuggestions(rawText, !!msg.isStreaming, msg.reasoning)
                      : { content: rawText, suggestions: [], reasoning: "" };

                    return (
                      <div key={idx} className="flex gap-4 group">
                        <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-1 ${msg.role === 'user'
                          ? 'bg-gray-700 hidden'
                          : 'bg-gradient-to-tr from-blue-500 to-purple-500 shadow-lg shadow-purple-500/20'
                          }`}>
                          {msg.role === 'model' && <i className="fas fa-sparkles text-xs text-white"></i>}
                        </div>

                        <div className="flex-1 space-y-1 overflow-hidden">
                          <div className="text-sm font-bold text-gray-400 mb-1 flex items-center gap-2">
                            {msg.role === 'model' && '스마트머니봇'}
                            <span className="text-[10px] text-gray-500 font-normal ml-2">
                              {msg.timestamp ? new Date(msg.timestamp).toLocaleString('ko-KR', {
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                                hour12: true
                              }) : ''}
                            </span>
                            {!msg.isStreaming && (
                              <span className="ml-1 inline-flex items-center gap-1">
                                <button
                                  onClick={(e) => handleDeleteTurn(e, idx)}
                                  className="h-6 px-2 rounded-full text-[10px] font-bold text-gray-500 hover:text-amber-300 hover:bg-amber-500/10 transition-colors opacity-70 hover:opacity-100"
                                  title="이 질문과 답변 함께 삭제"
                                  aria-label="이 질문과 답변 함께 삭제"
                                >
                                  질문/답변
                                </button>
                                <button
                                  onClick={(e) => handleDeleteMessage(e, idx)}
                                  className="w-6 h-6 rounded-full text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-70 hover:opacity-100"
                                  title="이 메시지 삭제"
                                  aria-label="이 메시지 삭제"
                                >
                                  <i className="fas fa-trash-alt text-[11px]"></i>
                                </button>
                              </span>
                            )}
                          </div>
                          <div className={`prose prose-sm prose-invert max-w-none leading-relaxed space-y-4 ${msg.role === 'user' ? 'text-lg text-gray-100 font-medium' : 'text-gray-300'
                            }`}>
                            {msg.role === 'model' && (
                              <ThinkingProcess
                                reasoning={reasoning}
                                isStreaming={!!msg.isStreaming}
                              />
                            )}
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                ul({ children }) { return <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-1">{children}</ul> },
                                ol({ children }) { return <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-1">{children}</ol> },
                                li({ children }) { return <li className="mb-1 leading-relaxed">{children}</li> },
                                code({ node, className, children, ...props }) {
                                  const match = /language-(\w+)/.exec(className || '')
                                  return match ? (
                                    <div className="relative bg-[#1e1f20] rounded-lg overflow-hidden border border-white/5 my-2 shadow-inner">
                                      <div className="px-4 py-1.5 bg-black/20 text-[10px] text-gray-500 font-mono border-b border-white/5 flex justify-between">
                                        <span>{match[1]}</span>
                                        <span className="cursor-pointer hover:text-white"><i className="far fa-copy"></i></span>
                                      </div>
                                      <pre className="p-4 overflow-x-auto m-0 !bg-transparent">
                                        <code className={className} {...props}>{children}</code>
                                      </pre>
                                    </div>
                                  ) : (
                                    <code className="bg-white/10 px-1.5 py-0.5 rounded text-blue-300 font-mono text-sm" {...props}>
                                      {children}
                                    </code>
                                  )
                                },
                                table({ children }) {
                                  return <div className="overflow-x-auto my-4 border border-white/10 rounded-lg"><table className="min-w-full divide-y divide-white/10">{children}</table></div>
                                },
                                thead({ children }) {
                                  return <thead className="bg-white/5">{children}</thead>
                                },
                                th({ children }) {
                                  return <th className="px-4 py-2 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">{children}</th>
                                },
                                td({ children }) {
                                  return <td className="px-4 py-2 text-sm text-gray-400 whitespace-nowrap border-t border-white/5">{children}</td>
                                },
                                a({ children, href }) {
                                  return <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer">{children}</a>
                                },
                                strong({ children }) {
                                  return <strong className="text-white font-bold">{children}</strong>
                                }
                              }}
                            >
                              {preprocessMarkdown(content)}
                            </ReactMarkdown>

                            {/* Render Extracted Suggestions */}
                            {suggestions.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-4 pt-2 border-t border-white/5">
                                {suggestions.map((s, i) => (
                                  <button
                                    key={i}
                                    onClick={() => handleSend(s)}
                                    className="px-3 py-1.5 bg-[#1e1f20] hover:bg-blue-600/20 hover:text-blue-300 hover:border-blue-500/30 border border-white/10 rounded-full text-xs text-gray-300 transition-all text-left shadow-sm"
                                  >
                                    {s}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}





                  {isLoading && (
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
            <div className="max-w-3xl mx-auto relative">
              {showCommands && filteredCommands.length > 0 && (
                <div className="absolute bottom-full left-0 mb-4 w-[300px] bg-[#1e1f20] border border-white/10 rounded-xl shadow-2xl overflow-hidden z-20 animate-fade-in-up">
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
              <div className="absolute bottom-full left-0 right-0 mb-4 px-4 pointer-events-none z-30 flex flex-col items-center gap-3">
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
                    >
                      <i className={`fas fa-microphone ${isRecording ? 'fa-beat' : ''}`}></i>
                    </button>

                    {/* Send / Stop Button */}
                    <div className="relative">
                      {isLoading ? (
                        <button
                          onClick={handleStop}
                          className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white bg-gray-700 hover:bg-gray-600 transition-all shadow-lg animate-fade-in"
                          title="답변 중단"
                        >
                          <div className="w-3 h-3 bg-white rounded-sm"></div>
                        </button>
                      ) : (
                        (input.trim() || attachedFiles.length > 0) ? (
                          <button
                            onClick={() => handleSend()}
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
