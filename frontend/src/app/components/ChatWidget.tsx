'use client';

import { useState, useRef, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from "next-auth/react";
import ThinkingProcess from './ThinkingProcess';

interface Message {
  role: 'user' | 'model';
  parts: string[];
  timestamp?: string;
  isStreaming?: boolean;
  reasoning?: string;
}

const THINKING_STEPS = [
  "시장을 분석하고 있습니다...",
  "관련 데이터를 조회중입니다...",
  "답변을 생성하고 있습니다...",
  "잠시만 기다려주세요..."
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

const parseAIResponse = (text: string, isStreaming: boolean = false, streamReasoning?: string) => {
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
      .map(l => l.replace(/\*\*/g, ''));
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
        // Fallback if formatting is broken but stream is done
        reasoning = processed.substring(startMatch.index!);
        processed = processed.substring(0, startMatch.index!);
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
  processed = preprocessMarkdown(processed);

  const reasoningHeaderRegex = /^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\\?\[\s*추론\s*과정\s*\\?\](?:\*\*|__)?\s*\n?/i;
  let cleanReasoning = preprocessMarkdown(reasoning).replace(reasoningHeaderRegex, '').trim();

  // Cleanup trailing broken markdown
  if (isStreaming) {
    cleanReasoning = cleanReasoning.replace(/[\*\_\[\]]+$/, '');
  }

  // FORCE newlines before numbered lists inside dense text
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  processed = processed.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');

  // FORCE newlines before numbered lists inside dense text (e.g., "내용 2. ")
  // Safely avoids breaking bold markdown tags (e.g., "**1. 제목**")
  cleanReasoning = cleanReasoning.replace(/(?<=\S)\s+(?=(?:\*\*|__)?\d+\.\s)/g, '\n\n');

  return { cleanText: processed.trim(), suggestions, reasoning: cleanReasoning };
};

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [showTooltip, setShowTooltip] = useState(true);

  // Auto-hide tooltip
  useEffect(() => {
    const timer = setTimeout(() => setShowTooltip(false), 8000);
    return () => clearTimeout(timer);
  }, []);

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const [thinkingIndex, setThinkingIndex] = useState(0);
  const { data: session } = useSession();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null); // [Fix] IME 조합 초기화용
  const pathname = usePathname();

  const SLASH_COMMANDS = [
    { cmd: '/help', desc: '도움말 확인', auto: true },
    { cmd: '/status', desc: '현재 상태 확인', auto: true },
    { cmd: '/model', desc: '모델 변경/확인', auto: true },
    { cmd: '/memory view', desc: '메모리 보기', auto: false },
    { cmd: '/memory add', desc: '메모리 추가', auto: false },
    { cmd: '/clear', desc: '화면 청소', auto: true },
    { cmd: '/clear all', desc: '전체 데이터 초기화', auto: true },
  ];

  const DEFAULT_SUGGESTIONS = [
    { emoji: "📊", label: "시장 분석", text: "오늘 마켓게이트 상태 알려줘" },
    { emoji: "💎", label: "종목 추천", text: "VCP 매수 추천 종목 분석해줘" },
    { emoji: "📈", label: "종가 베팅", text: "오늘의 종가베팅 추천해줘" },
    { emoji: "📰", label: "뉴스 요약", text: "최근 주요 뉴스 정리해줘" }
  ];

  const WELCOME_SUGGESTIONS = [
    "오늘 마켓게이트 상태 알려줘",
    "VCP 매수 추천 종목 분석해줘",
    "오늘의 종가베팅 추천해줘",
    "최근 주요 뉴스 정리해줘"
  ];

  const toggleChat = () => setIsOpen(!isOpen);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) scrollToBottom();
  }, [messages, isOpen]);

  const handleSend = async (msgOverride?: string) => {
    const messageToSend = msgOverride || input;
    if (!messageToSend.trim() || isLoading) return;

    const userMsg: Message = {
      role: 'user',
      parts: [messageToSend],
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);

    // [Fix] 한글 IME 조합 강제 종료 후 입력창 초기화
    if (textareaRef.current) {
      textareaRef.current.blur();  // IME 조합 종료
      textareaRef.current.value = ''; // 직접 값 초기화
    }
    setInput('');
    setIsLoading(true);

    try {
      // Get watchlist from localStorage
      const savedWatchlist = localStorage.getItem('watchlist');
      const watchlist = savedWatchlist ? JSON.parse(savedWatchlist) : [];

      // Auth Info Retrieval
      const userEmail = session?.user?.email || null;
      let sessionId = localStorage.getItem('browser_session_id');

      if (!sessionId) {
        sessionId = 'anon_' + crypto.randomUUID();
        localStorage.setItem('browser_session_id', sessionId);
      }

      const res = await fetch('/api/kr/chatbot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Email': userEmail || '',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify({ message: messageToSend, watchlist }),
      });
      const contentType = (res.headers.get('content-type') || '').toLowerCase();

      if (contentType.includes('text/event-stream') && res.body) {
        setIsLoading(false); // Stop block indicator

        // Setup a new streaming message
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
                      newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], parts: [`⚠️ 오류: ${data.error}`], isStreaming: false };
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
                      newMsgs[newMsgs.length - 1] = {
                        ...lastMsg,
                        parts: [""]
                      };
                      return newMsgs;
                    });
                  }
                  if (data.reasoning_clear) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = {
                        ...lastMsg,
                        reasoning: ""
                      };
                      return newMsgs;
                    });
                  }

                  const answerDelta = typeof data.answer_chunk === 'string' ? data.answer_chunk : data.chunk;
                  if (typeof answerDelta === 'string' && answerDelta.length > 0) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = {
                        ...lastMsg,
                        parts: [(lastMsg.parts[0] as string) + answerDelta]
                      };
                      return newMsgs;
                    });
                  }
                  if (typeof data.reasoning_chunk === 'string' && data.reasoning_chunk.length > 0) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = {
                        ...lastMsg,
                        reasoning: (lastMsg.reasoning || "") + data.reasoning_chunk
                      };
                      return newMsgs;
                    });
                  }
                  if (data.done) {
                    setMessages(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = {
                        ...newMsgs[newMsgs.length - 1],
                        isStreaming: false
                      };
                      return newMsgs;
                    });
                    window.dispatchEvent(new CustomEvent('quota-updated'));
                  }
                } catch (e) {
                  console.error("SSE Parse logic error", e);
                }
              }
            }
          }
        }

        // Safety net: stream 종료 이벤트 누락 시에도 상태 복구
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

        if (res.status === 401 || res.status === 402) {
          setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ ${data.error}`] }]);
          setIsLoading(false);
          return;
        }

        if (data.response) {
          setMessages(prev => [...prev, { role: 'model', parts: [data.response] }]);
          // [Fix] 성공 응답 후 Sidebar quota 실시간 업데이트
          if (!data.response.startsWith('⚠️')) {
            window.dispatchEvent(new CustomEvent('quota-updated'));
          }
        } else if (data.error) {
          setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ 오류: ${data.error}`] }]);
        } else {
          setMessages(prev => [...prev, { role: 'model', parts: ['⚠️ 응답을 받아오지 못했습니다.'] }]);
        }
      }
    } catch (error: any) {
      const errorMessage = (error && typeof error.message === 'string' && error.message.trim().length > 0)
        ? `⚠️ 오류가 발생했습니다: ${error.message}`
        : '⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
      setMessages(prev => [...prev, { role: 'model', parts: [errorMessage] }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = async () => {
    if (isLoading) return;

    // 1. Reset frontend
    setMessages([]);
    setInput('');
  };

  const handleSuggestionClick = (text: string) => {
    handleSend(text);
  };

  useEffect(() => {
    setSelectedCommandIndex(0);
  }, [input]);

  useEffect(() => {
    if (isLoading) {
      const interval = setInterval(() => {
        setThinkingIndex((prev) => (prev + 1) % THINKING_STEPS.length);
      }, 3500);
      return () => clearInterval(interval);
    } else {
      setThinkingIndex(0);
    }
  }, [isLoading]);

  const filteredCommands = input.startsWith('/')
    ? SLASH_COMMANDS.filter(c => c.cmd.toLowerCase().startsWith(input.toLowerCase()))
    : [];

  const handleCommandClick = (cmd: string) => {
    handleSend(cmd);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (input.startsWith('/') && filteredCommands.length > 0) {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedCommandIndex(prev => (prev > 0 ? prev - 1 : filteredCommands.length - 1));
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedCommandIndex(prev => (prev < filteredCommands.length - 1 ? prev + 1 : 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const selectedCmd = filteredCommands[selectedCommandIndex];
        if (selectedCmd) {
          handleSend(selectedCmd.cmd);
        }
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (pathname === '/chatbot') return null;

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-[110] w-full h-[100dvh] md:fixed md:inset-auto md:bottom-24 md:right-6 md:w-[430px] md:h-[730px] md:max-h-[80vh] bg-[#1c1c1e] md:border border-white/10 md:rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-fade-in font-sans md:z-[110]">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#252529] flex-shrink-0 safe-top">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <i className="fas fa-robot text-white text-lg"></i>
              </div>
              <div>
                <h3 className="font-bold text-white text-lg">스마트 머니 봇</h3>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                  <span className="text-xs text-blue-400 font-medium">Online</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleNewChat}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                title="New Chat"
              >
                <i className="fas fa-redo-alt"></i>
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors md:hidden"
              >
                <i className="fas fa-times"></i>
              </button>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth bg-[#18181b] relative">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-6 animate-fade-in p-4">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-600/20 flex items-center justify-center mb-2">
                  <i className="fas fa-robot text-4xl text-blue-400"></i>
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">무엇을 도와드릴까요?</h3>
                  <p className="text-sm text-gray-400 max-w-[240px] mx-auto leading-relaxed">
                    시장 분석, 종목 진단, 매매 전략 등<br />
                    궁금한 점을 자유롭게 물어보세요.
                  </p>
                </div>

                <div className="grid grid-cols-1 w-full gap-2 px-4">
                  {DEFAULT_SUGGESTIONS.map((suggestion, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSuggestionClick(suggestion.text)}
                      className="flex items-center gap-3 p-3 text-left bg-[#252529] hover:bg-[#2c2c30] border border-white/5 hover:border-blue-500/30 rounded-xl transition-all group"
                    >
                      <span className="w-8 h-8 rounded-lg bg-black/20 flex items-center justify-center text-lg group-hover:scale-110 transition-transform">
                        {suggestion.emoji}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-200 truncate group-hover:text-blue-400 transition-colors">
                          {suggestion.label}
                        </div>
                        <div className="text-xs text-gray-500 truncate">
                          {suggestion.text}
                        </div>
                      </div>
                      <i className="fas fa-chevron-right text-xs text-gray-600 group-hover:text-blue-400 transition-colors"></i>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-none'
                        : 'bg-[#252529] text-gray-200 border border-white/10 rounded-bl-none'
                        }`}
                    >
                      {msg.role === 'model' ? (
                        (() => {
                          const { cleanText, suggestions, reasoning } = parseAIResponse(msg.parts[0] || '', msg.isStreaming, msg.reasoning);
                          return (
                            <div className="flex flex-col gap-2 relative z-10">
                              {msg.role === 'model' && (
                                <ThinkingProcess
                                  reasoning={reasoning}
                                  isStreaming={!!msg.isStreaming}
                                  className="text-white"
                                />
                              )}

                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                  p({ children }) { return <p className="mb-2 last:mb-0">{children}</p> },
                                  ul({ children }) { return <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-1">{children}</ul> },
                                  ol({ children }) { return <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-1">{children}</ol> },
                                  li({ children }) { return <li className="mb-1 leading-relaxed">{children}</li> },
                                  code({ node, className, children, ...props }) {
                                    return <code className="bg-black/30 px-1 rounded text-blue-300 font-mono" {...props}>{children}</code>
                                  },
                                  table({ children }) {
                                    return <div className="overflow-x-auto my-2 border border-white/10 rounded"><table className="min-w-full divide-y divide-white/10">{children}</table></div>
                                  },
                                  th({ children }) { return <th className="px-2 py-1 text-left text-xs font-semibold text-gray-400 bg-white/5">{children}</th> },
                                  td({ children }) { return <td className="px-2 py-1 text-xs text-gray-300 border-t border-white/5">{children}</td> },
                                  a({ children, href }) { return <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer">{children}</a> },
                                  strong({ children }) { return <strong className="text-white font-bold">{children}</strong> }
                                }}
                              >
                                {cleanText}
                              </ReactMarkdown>

                              {suggestions.length > 0 && (
                                <div className="flex flex-col gap-1.5 mt-2 pt-3 border-t border-white/10">
                                  <span className="text-[10px] font-bold text-gray-500 mb-0.5"><i className="fas fa-lightbulb text-yellow-500 mr-1"></i>추천 질문</span>
                                  {suggestions.map((sug, i) => (
                                    <button
                                      key={i}
                                      onClick={() => handleSend(sug)}
                                      className="px-3 py-2 bg-blue-500/10 hover:bg-blue-600 text-blue-300 hover:text-white rounded-lg text-xs transition-colors border border-blue-500/20 text-left shadow-sm hover:shadow-md"
                                    >
                                      {sug}
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })()
                      ) : (
                        msg.parts[0]
                      )}
                    </div>
                    <div className={`text-[10px] text-gray-500 mt-1 px-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                      {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="flex justify-start animate-fade-in">
                    <div className="bg-[#252529] border border-white/10 rounded-2xl rounded-bl-none px-4 py-3 shadow-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                        <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                        <div className="w-2 h-2 bg-rose-500 rounded-full animate-bounce"></div>
                        <span className="text-xs text-gray-400 ml-2 font-medium animate-pulse">Thinking...</span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}

            {/* Command Suggestions Popup */}
            {input.startsWith('/') && filteredCommands.length > 0 && (
              <div className="absolute bottom-4 left-4 right-4 bg-[#1c1c1e] border border-white/10 rounded-xl shadow-2xl overflow-hidden max-h-[200px] overflow-y-auto z-[60]">
                <div className="px-3 py-2 bg-[#2c2c2e] border-b border-white/5 text-[10px] font-bold text-gray-400">
                  사용 가능한 명령어
                </div>
                {filteredCommands.map((cmd, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleCommandClick(cmd.cmd)}
                    className={`w-full text-left px-4 py-2 text-xs flex justify-between items-center transition-colors group ${idx === selectedCommandIndex
                      ? 'bg-blue-600/20 text-white'
                      : 'text-gray-200 hover:bg-blue-600/20 hover:text-white'
                      }`}
                  >
                    <span className={`font-mono font-bold ${idx === selectedCommandIndex ? 'text-blue-300' : 'text-blue-400'}`}>{cmd.cmd}</span>
                    <span className="text-gray-500 group-hover:text-gray-300">{cmd.desc}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="p-4 bg-[#252529] border-t border-white/10 safe-bottom">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="relative flex items-center"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isLoading ? "답변을 기다리고 있습니다..." : "메시지를 입력하세요... (슬래시 커맨드 '/' 사용 가능)"}
                disabled={isLoading}
                className="w-full bg-[#18181b] text-white text-sm rounded-xl pl-4 pr-12 py-3.5 focus:outline-none focus:ring-2 focus:ring-blue-500/50 border border-white/5 placeholder-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:bg-gray-700 transition-all shadow-lg shadow-blue-500/20"
              >
                {isLoading ? (
                  <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                ) : (
                  <i className="fas fa-paper-plane text-xs"></i>
                )}
              </button>
            </form>
            <div className="text-[10px] text-center text-gray-600 mt-2 font-medium">
              AI can make mistakes. Please check important info.
            </div>
          </div>
        </div>
      )}

      {/* Toggle Button (Always Visible) */}
      <div className="fixed bottom-3 right-3 md:bottom-6 md:right-6 z-[120] flex flex-col items-end">
        <button
          onClick={toggleChat}
          className={`w-11 h-11 md:w-14 md:h-14 rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 active:scale-95 group ${isOpen ? 'bg-[#2c2c2e] hover:bg-[#3a3a3c] text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
        >
          <div className="relative w-full h-full flex items-center justify-center">
            <i className={`fas fa-comment-dots text-lg md:text-2xl transition-all duration-300 absolute ${isOpen ? 'opacity-0 rotate-90 scale-50' : 'opacity-100 rotate-0 scale-100'}`}></i>
            <i className={`fas fa-times text-lg md:text-2xl transition-all duration-300 absolute ${isOpen ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'}`}></i>
          </div>
        </button>

        {!isOpen && messages.length === 0 && showTooltip && (
          <div className="absolute right-16 top-1/2 -translate-y-1/2 bg-white text-black px-4 py-2 rounded-xl shadow-lg whitespace-nowrap animate-fade-in origin-right z-50">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowTooltip(false);
              }}
              className="absolute -top-2 -left-2 w-5 h-5 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center text-gray-600 shadow-sm transition-colors z-10"
            >
              <i className="fas fa-times text-[10px]"></i>
            </button>
            <div className="text-sm font-bold">궁금한 건 채팅으로 문의하세요</div>
            <div className="text-xs text-gray-500">대화 시작하기</div>
            <div className="absolute top-1/2 -right-1.5 w-3 h-3 bg-white transform -translate-y-1/2 rotate-45"></div>
          </div>
        )}
      </div>
    </>
  );
}
