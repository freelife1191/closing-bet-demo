'use client';

import { useState, useRef, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSession } from "next-auth/react";

interface Message {
  role: 'user' | 'model';
  parts: string[];
  timestamp?: string;
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

  // 1. Fix malformed bold with spaces: "** text **" -> "**text**"
  // Handles cases where AI adds spaces inside the markers
  processed = processed.replace(/\*\*\s+(.*?)\s*\*\*/g, '**$1**');

  // 2. Fix CJK boundary issues: "**Bold**Suffix" -> "**Bold** Suffix"
  // Insert generic space between bold/italic end and Korean particles
  processed = processed.replace(/(\*\*|__)(.*?)\1([가-힣])/g, '$1$2$1 $3');

  return processed;
};

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const [thinkingIndex, setThinkingIndex] = useState(0);
  const { data: session } = useSession();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  // Slash commands list
  const SLASH_COMMANDS = [
    { cmd: '/help', desc: '도움말 확인', auto: true },
    { cmd: '/status', desc: '현재 상태 확인', auto: true },
    { cmd: '/model', desc: '모델 변경/확인', auto: true },
    { cmd: '/memory view', desc: '메모리 보기', auto: false },
    { cmd: '/memory add', desc: '메모리 추가', auto: false },
    { cmd: '/clear', desc: '화면 청소', auto: true },
    { cmd: '/clear all', desc: '전체 데이터 초기화', auto: true },
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

  // [Fix] Re-render when API Key changes
  const [hasApiKey, setHasApiKey] = useState(false);
  useEffect(() => {
    const checkKey = () => {
      const k1 = localStorage.getItem('X-Gemini-Key');
      const k2 = localStorage.getItem('GOOGLE_API_KEY');
      const valid = (k1 && k1 !== 'null' && k1 !== 'undefined') || (k2 && k2 !== 'null' && k2 !== 'undefined');
      setHasApiKey(!!valid);
    };
    checkKey();
    window.addEventListener('api-key-updated', checkKey);
    const interval = setInterval(checkKey, 2000);
    return () => {
      window.removeEventListener('api-key-updated', checkKey);
      clearInterval(interval);
    };
  }, []);



  const handleSend = async (msgOverride?: string) => {
    const messageToSend = msgOverride || input;
    if (!messageToSend.trim() || isLoading) return;

    const userMsg: Message = {
      role: 'user',
      parts: [messageToSend],
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Get watchlist from localStorage
      const savedWatchlist = localStorage.getItem('watchlist');
      const watchlist = savedWatchlist ? JSON.parse(savedWatchlist) : [];

      // Auth Info Retrieval
      const userEmail = session?.user?.email || null;
      let apiKey = null;
      let sessionId = localStorage.getItem('browser_session_id');

      // 세션 ID가 없으면 생성
      if (!sessionId) {
        sessionId = 'anon_' + crypto.randomUUID();
        localStorage.setItem('browser_session_id', sessionId);
      }

      // [Fix] API Key Retrieval Logic Enhanced
      // 1. Try X-Gemini-Key
      // 2. Try GOOGLE_API_KEY
      // 3. Ensure not "null", "undefined", or empty string
      // Removed intermediate catch block to fix Syntax Error and Scope Issue

      let rawKey = localStorage.getItem('X-Gemini-Key');
      if (!rawKey || rawKey === 'null' || rawKey === 'undefined') {
        rawKey = localStorage.getItem('GOOGLE_API_KEY');
      }

      if (rawKey && rawKey !== 'null' && rawKey !== 'undefined' && rawKey.trim().length > 0) {
        apiKey = rawKey.trim();
      } else {
        apiKey = null;
      }

      const res = await fetch('/api/kr/chatbot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Email': userEmail || '',
          'X-Gemini-Key': apiKey || '',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify({ message: messageToSend, watchlist }),
      });
      const data = await res.json();

      if (res.status === 401 || res.status === 402) {
        setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ ${data.error}`] }]);
        setIsLoading(false);
        return;
      }

      if (data.response) {
        setMessages(prev => [...prev, { role: 'model', parts: [data.response] }]);
      } else if (data.error) {
        setMessages(prev => [...prev, { role: 'model', parts: [`⚠️ 오류: ${data.error}`] }]);
      } else {
        setMessages(prev => [...prev, { role: 'model', parts: ['⚠️ 응답을 받아오지 못했습니다.'] }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'model', parts: ['⚠️ 오류가 발생했습니다. 설정 > API Key가 정상적으로 등록되어 있는지 확인해주세요.'] }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = async () => {
    if (isLoading) return;

    // 1. Reset frontend
    setMessages([]);
    setInput('');

    // 2. Clear backend history
    try {
      await fetch('/api/kr/chatbot/history', { method: 'DELETE' });
    } catch (e) {
      console.error("Failed to clear history:", e);
    }
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
      }, 3000);
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
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Chat Window */}
      {isOpen && (
        <div className="mb-4 w-[430px] h-[730px] max-h-[80vh] bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-fade-in font-sans">

          {/* Header */}
          <div className="bg-[#2c2c2e] p-4 flex items-center justify-between border-b border-white/5 flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                <i className="fas fa-robot text-sm text-white"></i>
              </div>
              <div>
                <div className="font-bold text-white text-sm flex items-center gap-2">
                  스마트머니봇
                  {hasApiKey && (
                    <i className="fas fa-key text-[10px] text-yellow-500 animate-pulse" title="개인 API Key 사용 중 (무제한)"></i>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                  <span className="text-[10px] text-gray-400">보통 1초 내 답변</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleNewChat}
                className="p-2 text-gray-400 hover:text-white transition-colors"
                title="새 대화"
              >
                <i className="fas fa-eraser text-xs"></i>
              </button>
              <div className="w-[1px] h-4 bg-white/10 mx-1"></div>
              <button
                onClick={toggleChat}
                className="p-2 text-gray-400 hover:text-white transition-colors"
              >
                <i className="fas fa-times"></i>
              </button>
            </div>
          </div>


          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto bg-[#151517] relative custom-scrollbar">
            {messages.length === 0 ? (
              <div className="p-6 flex flex-col h-full animate-fade-in">
                <div className="flex-1 flex flex-col justify-center items-start space-y-6">
                  {/* Greeting */}
                  <div className="space-y-2">
                    <h2 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
                      안녕하세요, 투자자님! 👋
                    </h2>
                    <p className="text-gray-300 text-sm leading-relaxed">
                      <strong className="text-white">스마트머니봇</strong>에 오신 것을 환영합니다.<br />
                      VCP 패턴 분석과 시장 동향 예측을 도와드리는<br />
                      AI 투자 비서입니다.
                    </p>
                  </div>

                  {/* Status Info */}
                  <div className="bg-[#2c2c2e]/50 rounded-xl p-4 border border-white/5 w-full">
                    <div className="text-xs font-bold text-gray-400 mb-2 uppercase tracking-wider">Operating Status</div>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <i className="fas fa-check-circle text-green-500"></i>
                        <span>AI 분석 엔진: <span className="text-white font-medium">가동 중</span></span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-300">
                        <i className="fas fa-clock text-blue-500"></i>
                        <span>운영 시간: <span className="text-white font-medium">24시간 연중무휴</span></span>
                      </div>
                    </div>
                  </div>

                  {/* Suggestions */}
                  <div className="w-full space-y-3">
                    <div className="text-xs font-bold text-gray-400 uppercase tracking-wider">추천 질문</div>
                    <div className="flex flex-col gap-2">
                      {WELCOME_SUGGESTIONS.map((suggestion, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSuggestionClick(suggestion)}
                          className="w-full text-left bg-[#2c2c2e] hover:bg-[#3a3a3c] border border-white/5 hover:border-blue-500/30 p-3 rounded-xl transition-all duration-200 group flex items-center justify-between"
                        >
                          <span className="text-sm text-gray-200 group-hover:text-blue-300 transition-colors">{suggestion}</span>
                          <i className="fas fa-chevron-right text-[10px] text-gray-600 group-hover:text-blue-500 transition-colors opacity-0 group-hover:opacity-100 transform translate-x-[-5px] group-hover:translate-x-0"></i>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 space-y-4 pb-20">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed ${msg.role === 'user'
                      ? 'bg-blue-600 text-white whitespace-pre-wrap'
                      : 'bg-[#2c2c2e] text-gray-200'
                      }`}>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p({ children }) {
                            return <p className="mb-2 last:mb-0">{children}</p>
                          },
                          ul({ children }) {
                            return <ul className="list-disc pl-4 mb-2 last:mb-0 space-y-1">{children}</ul>
                          },
                          li({ children }) {
                            return <li>{children}</li>
                          },
                          code({ node, className, children, ...props }) {
                            return (
                              <code className="bg-black/30 px-1 rounded text-blue-300 font-mono" {...props}>{children}</code>
                            )
                          },
                          table({ children }) {
                            return <div className="overflow-x-auto my-2 border border-white/10 rounded"><table className="min-w-full divide-y divide-white/10">{children}</table></div>
                          },
                          th({ children }) {
                            return <th className="px-2 py-1 text-left text-xs font-semibold text-gray-400 bg-white/5">{children}</th>
                          },
                          td({ children }) {
                            return <td className="px-2 py-1 text-xs text-gray-300 border-t border-white/5">{children}</td>
                          },
                          a({ children, href }) {
                            return <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer">{children}</a>
                          },
                          strong({ children }) {
                            return <strong className="text-white font-bold">{children}</strong>
                          }
                        }}
                      >
                        {typeof msg.parts[0] === 'string'
                          ? preprocessMarkdown(msg.parts[0])
                          : preprocessMarkdown((msg.parts[0] as any).text)
                        }
                      </ReactMarkdown>
                    </div>
                    {/* Timestamp */}
                    <div className={`text-[10px] text-gray-500 mt-1 px-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                      {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-[#2c2c2e] rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-3">
                        <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin"></div>
                        <span className="text-xs text-gray-300 font-medium animate-pulse">
                          {THINKING_STEPS[thinkingIndex]}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}

          </div>

          {/* Command Suggestions Popup (Fixed Position relative to Input) */}
          {input.startsWith('/') && filteredCommands.length > 0 && (
            <div className="absolute bottom-[70px] left-2 right-2 bg-[#1c1c1e] border border-white/10 rounded-xl shadow-2xl overflow-hidden max-h-[200px] overflow-y-auto z-[60]">
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

          {/* Persistent Suggestions (When chat is active) - Moved to Bottom */}
          {messages.length > 0 && (
            <div className="bg-[#1c1c1e] border-t border-white/5 py-3 px-4 flex-shrink-0">
              <div className="flex gap-2 overflow-x-auto custom-scrollbar-hide">
                {WELCOME_SUGGESTIONS.map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="flex-shrink-0 px-3 py-1.5 bg-[#2c2c2e] hover:bg-blue-600 hover:text-white border border-white/5 rounded-full text-[11px] text-gray-400 hover:text-white transition-all whitespace-nowrap"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Area (Fixed at Bottom) */}
          <div className="p-3 bg-[#1c1c1e] border-t border-white/5 relative z-20 flex-shrink-0">
            <div className="flex items-end gap-2 bg-[#2c2c2e] rounded-xl p-2 relative transition-all ring-1 ring-white/5 focus-within:ring-blue-500/50">

              {/* Command Button */}
              <div className="relative flex-shrink-0 pb-[1px]">
                <button
                  onClick={() => setInput('/ ')}
                  className="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-blue-400 transition-colors"
                  title="명령어"
                >
                  <i className="fas fa-terminal text-xs"></i>
                </button>
              </div>

              {/* Textarea */}
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="메시지를 입력하세요..."
                className="flex-1 bg-transparent text-white text-sm placeholder-gray-500 resize-none focus:outline-none custom-scrollbar py-1.5 leading-relaxed max-h-[100px] min-h-[36px]"
                rows={1}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = `${Math.min(target.scrollHeight, 100)}px`;
                }}
              />

              {/* Send Button */}
              <div className="flex-shrink-0 pb-[1px]">
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || isLoading}
                  className="w-8 h-8 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 rounded-lg flex items-center justify-center text-white transition-all shadow-lg active:scale-95"
                >
                  {isLoading ? (
                    <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    <i className="fas fa-paper-plane text-xs"></i>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Floating Toggle Button Removed when Open to prevent overlap */}
        </div>
      )}

      {/* Toggle Button when Closed (Floating) - Just one button logic handled above? 
          Wait, the structure was: 
          Container (Fixed) -> {isOpen && Window} -> Toggle Button. 
          The previous code had the button OUTSIDE the window div.
          My new structure put the button INSIDE the window div but `fixed` class on button might save it? 
          Actually, the structure was:
          <div className="fixed bottom-6 right-6 ...">
             {isOpen && <Window ... />}
             <Button ... />
          </div>
          
          I should restore THAT structure to ensure the button is always visible.
      */}
      {/* Toggle Button (Always Visible) */}
      <button
        onClick={toggleChat}
        className={`w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 active:scale-95 group z-50 ${isOpen ? 'bg-[#2c2c2e] hover:bg-[#3a3a3c] text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
      >
        <div className="relative w-full h-full flex items-center justify-center">
          <i className={`fas fa-comment-dots text-2xl transition-all duration-300 absolute ${isOpen ? 'opacity-0 rotate-90 scale-50' : 'opacity-100 rotate-0 scale-100'}`}></i>
          <i className={`fas fa-times text-2xl transition-all duration-300 absolute ${isOpen ? 'opacity-100 rotate-0 scale-100' : 'opacity-0 -rotate-90 scale-50'}`}></i>
        </div>

        {!isOpen && messages.length === 0 && (
          <div className="absolute right-16 bg-white text-black px-4 py-2 rounded-xl shadow-lg whitespace-nowrap animate-fade-in origin-right">
            <div className="text-sm font-bold">궁금한 건 채팅으로 문의하세요</div>
            <div className="text-xs text-gray-500">대화 시작하기</div>
            <div className="absolute top-1/2 -right-1.5 w-3 h-3 bg-white transform -translate-y-1/2 rotate-45"></div>
          </div>
        )}
      </button>
    </div>
  );
}
