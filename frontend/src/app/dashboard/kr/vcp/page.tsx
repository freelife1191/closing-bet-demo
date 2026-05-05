'use client';

import { useEffect, useRef, useState } from 'react';
import { krAPI, KRSignal, KRAIAnalysis, KRMarketGate, AIRecommendation } from '@/lib/api';
import StockChart from './StockChart';
import BuyStockModal from '@/app/components/BuyStockModal';
import ConfirmationModal from '@/app/components/ConfirmationModal';
import Modal from '@/app/components/Modal';
import VCPCriteriaModal from '@/app/components/VCPCriteriaModal'; // [NEW] Import
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAdmin } from '@/hooks/useAdmin';
import ThinkingProcess from '@/app/components/ThinkingProcess';

// Simple Tooltip Component
// Simple Tooltip Component
const SimpleTooltip = ({
  text,
  children,
  align = 'center',
  position = 'bottom'
}: {
  text: string;
  children: React.ReactNode;
  align?: 'left' | 'center' | 'right';
  position?: 'top' | 'bottom';
}) => {
  let positionClass = 'left-1/2 -translate-x-1/2';
  let arrowClass = 'left-1/2 -translate-x-1/2';

  if (align === 'right') {
    positionClass = 'right-0 translate-x-0';
    arrowClass = 'right-4 translate-x-0';
  } else if (align === 'left') {
    positionClass = 'left-0 translate-x-0';
    arrowClass = 'left-4 translate-x-0';
  }

  return (
    <div className="group relative flex items-center justify-center gap-1 cursor-help">
      {children}
      <div className={`absolute ${position === 'top' ? 'bottom-full mb-2' : 'top-full mt-2'} hidden group-hover:block min-w-[120px] w-max max-w-[180px] p-2 bg-gray-900 text-white text-[10px] rounded shadow-lg z-[100] text-center border border-white/10 pointer-events-none whitespace-normal break-keep ${positionClass}`}>
        {text}
        <div className={`absolute border-4 border-transparent ${position === 'top' ? 'top-full border-t-gray-900' : 'bottom-full border-b-gray-900'} ${arrowClass}`}></div>
      </div>
    </div>
  );
};

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

  // 6. Normalize quoted emphasis wrappers: **"텍스트"** / **'텍스트'** -> **텍스트**
  processed = processed.replace(/\*\*\s*['"“”‘’]\s*([^*\n]+?)\s*['"“”‘’]\s*\*\*/g, '**$1**');
  processed = processed.replace(/__\s*['"“”‘’]\s*([^_\n]+?)\s*['"“”‘’]\s*__/g, '__$1__');

  // 7. Ensure spacing after closing emphasis marker when attached to text.
  processed = processed.replace(/(?<=\S)(\*\*|__)(?=[가-힣A-Za-z0-9])/g, '$1 ');

  // 8. Remove trailing unmatched emphasis marker in a line.
  processed = processed
    .split('\n')
    .map((line) => {
      const balancedAsterisk = removeLastUnmatchedMarker(line, /(?<!\*)\*\*(?!\*)/g, 2);
      return removeLastUnmatchedMarker(balancedAsterisk, /(?<!_)__(?!_)/g, 2);
    })
    .join('\n');

  // 9. Fix CJK boundary issues: "**Bold**Suffix" -> "**Bold** Suffix"
  processed = processed.replace(/\*\*([A-Za-z0-9가-힣(][^*\n]*?)\*\*([가-힣])/g, '**$1** $2');
  processed = processed.replace(/__([A-Za-z0-9가-힣(][^_\n]*?)__([가-힣])/g, '__$1__ $2');

  return processed;
};

const parseAIResponse = (text: string, isStreaming: boolean = false, streamReasoning?: string) => {
  let processed = text;
  let suggestions: string[] = [];
  const hasStreamReasoning = typeof streamReasoning === 'string' && streamReasoning.length > 0;
  let reasoning = hasStreamReasoning ? streamReasoning : "";

  const suggestionMatch = processed.match(/(?:^|\n)\s*(?:#{1,6}\s*)?(?:\*\*|__)?\\?\[?\s*추천\s*질문\s*\]?(?:\*\*|__)?\s*\n[\s\S]*$/i);
  if (suggestionMatch) {
    const sugText = suggestionMatch[0];
    processed = processed.replace(sugText, '');

    const lines = sugText.split('\n');
    suggestions = lines
      .map(l => l.replace(/^(?:\d+\.|\-|\*)\s*/, '').trim())
      .filter(l => {
        if (l.length === 0) return false;
        const normalized = l.replace(/\*/g, '').replace(/\s/g, '').replace(/[\[\]]/g, '');
        return !normalized.includes('추천질문');
      })
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

  return { cleanText: processed.trim(), suggestions, reasoning: cleanReasoning };
};

const getVcpWelcomeMessage = (stockName?: string) => `👋 안녕하세요! **VCP 전문가 챗봇**입니다.\n\n**${stockName || '선택 종목'}** 종목의 VCP 패턴, 수급 현황, 그리고 AI 투자 의견에 대해 무엇이든 물어보세요.\n\n명령어 예시:\n* \`/status\` - 현재 상태 확인\n* \`/help\` - 도움말`;

export default function VCPSignalsPage() {
  const [signals, setSignals] = useState<KRSignal[]>([]);
  const [aiData, setAiData] = useState<KRAIAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [scannedCount, setScannedCount] = useState<number>(0);
  const [signalDate, setSignalDate] = useState<string>('');

  // Market Gate State
  const [marketGate, setMarketGate] = useState<KRMarketGate | null>(null);

  // Chatbot State
  const [chatHistory, setChatHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string; reasoning?: string; isStreaming?: boolean }>>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Chart Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [chartData, setChartData] = useState<any[]>([]);
  const [selectedStock, setSelectedStock] = useState<{ name: string; ticker: string } | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartPeriod, setChartPeriod] = useState<'1M' | '3M' | '6M' | '1Y'>('3M');
  const [showVcpRange, setShowVcpRange] = useState(true); // VCP 범위 표시 상태

  // ADMIN 권한 체크
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();

  // Permission denied modal
  const [permissionModal, setPermissionModal] = useState(false);

  const [screenerRunning, setScreenerRunning] = useState(false);
  const [reanalyzingFailedAI, setReanalyzingFailedAI] = useState(false);
  const [stoppingReanalysis, setStoppingReanalysis] = useState(false);
  const [reanalysisMode, setReanalysisMode] = useState<'failed' | 'gemini' | 'second'>('failed');
  const [screenerMessage, setScreenerMessage] = useState<string | null>(null);
  const reanalysisPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Slash Command State for Embedded Chat
  const [showCommands, setShowCommands] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);

  // Buy Modal State
  const [isBuyModalOpen, setIsBuyModalOpen] = useState(false);
  const [buyingStock, setBuyingStock] = useState<{ ticker: string; name: string; price: number } | null>(null);
  const [isBulkBuyingVCP, setIsBulkBuyingVCP] = useState(false);
  const [isVCPCriteriaModalOpen, setIsVCPCriteriaModalOpen] = useState(false); // [NEW] State

  // Alert Modal State
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    type: 'default' | 'success' | 'danger';
    title: string;
    content: string;
  }>({ isOpen: false, type: 'default', title: '', content: '' });
  const [deleteConfirmModal, setDeleteConfirmModal] = useState<{
    isOpen: boolean;
    mode: 'clear_all' | 'single_message' | null;
    msgIndex: number | null;
  }>({ isOpen: false, mode: null, msgIndex: null });

  const SLASH_COMMANDS = [
    { cmd: '/help', desc: '도움말 확인' },
    { cmd: '/status', desc: '현재 상태 확인' },
    { cmd: '/model', desc: '모델 변경/확인' },
    { cmd: '/memory view', desc: '메모리 보기' },
    { cmd: '/clear', desc: '대화 내역 초기화' },
  ];

  const filteredCommands = chatInput.startsWith('/')
    ? SLASH_COMMANDS.filter(c => c.cmd.toLowerCase().startsWith(chatInput.toLowerCase()))
    : [];
  const VCP_FALLBACK_SUGGESTIONS = [
    "이 종목 VCP 패턴 분석해줘",
    "수급(기관/외국인) 상황 어때?",
    "진입가와 손절가 추천해줘",
  ];

  const openDeleteConfirmModal = (mode: 'clear_all' | 'single_message', msgIndex: number | null = null) => {
    setDeleteConfirmModal({ isOpen: true, mode, msgIndex });
  };

  const closeDeleteConfirmModal = () => {
    setDeleteConfirmModal({ isOpen: false, mode: null, msgIndex: null });
  };

  const handleConfirmDeleteChatHistory = async () => {
    try {
      if (deleteConfirmModal.mode === 'clear_all') {
        const stockTicker = selectedStock?.ticker || 'default';
        const sessionKey = `vcp_chat_session_id_${stockTicker}`;
        const sessionId = localStorage.getItem(sessionKey);

        if (sessionId) {
          await fetch(`/api/kr/chatbot/history?session_id=${sessionId}`, { method: 'DELETE' });
        }

        setChatHistory([{
          role: 'assistant',
          content: getVcpWelcomeMessage(selectedStock?.name)
        }]);
        return;
      }

      if (deleteConfirmModal.mode === 'single_message' && deleteConfirmModal.msgIndex !== null) {
        const msgIndex = deleteConfirmModal.msgIndex;
        const newHistory = [...chatHistory];
        newHistory.splice(msgIndex, 1);

        // UI 즉시 반영
        setChatHistory(newHistory);

        try {
          const stockTicker = selectedStock?.ticker || 'default';
          const sessionKey = `vcp_chat_session_id_${stockTicker}`;
          const sessionId = localStorage.getItem(sessionKey);
          if (sessionId) {
            await fetch(`/api/kr/chatbot/history?session_id=${sessionId}&index=${msgIndex}`, { method: 'DELETE' });
            console.log("Deleted message at index", msgIndex);
          }
        } catch (e) {
          console.error("Failed to sync partial deletion with DB", e);
        }
      }
    } catch (e) {
      console.error("Failed to delete VCP chat history", e);
    } finally {
      closeDeleteConfirmModal();
    }
  };

  useEffect(() => {
    setSelectedCommandIndex(0);
  }, [chatInput]);

  // On ticker change, load chat history from backend DB
  useEffect(() => {
    let isMounted = true;

    const loadHistory = async () => {
      if (!selectedStock?.ticker || !isModalOpen) return;

      setChatLoading(true);
      try {
        const stockTicker = selectedStock.ticker;
        const sessionKey = `vcp_chat_session_id_${stockTicker}`;
        let sessionId = localStorage.getItem(sessionKey);

        if (!sessionId) {
          // No session yet, just show welcome message
          setChatHistory([{
            role: 'assistant',
            content: getVcpWelcomeMessage(selectedStock.name)
          }]);
          setChatLoading(false);
          return;
        }

        // Fetch from backend
        const headers: Record<string, string> = {
          'Cache-Control': 'no-cache'
        };
        const email = localStorage.getItem('user_email');
        if (email) headers['X-User-Email'] = email;

        const res = await fetch(`/api/kr/chatbot/history?session_id=${sessionId}&_t=${Date.now()}`, {
          headers,
          cache: 'no-store'
        });

        if (res.ok) {
          const data = await res.json();
          if (data.history && data.history.length > 0) {
            const mappedHistory = data.history.map((msg: any) => {
              let textContent = '';
              if (msg.content) {
                textContent = msg.content;
              } else if (msg.parts && Array.isArray(msg.parts)) {
                textContent = msg.parts.map((p: any) => typeof p === 'string' ? p : p.text).join('');
              }
              return {
                role: msg.role === 'model' ? 'assistant' : msg.role,
                content: textContent
              };
            });
            if (isMounted) setChatHistory(mappedHistory);
          } else {
            if (isMounted) setChatHistory([{
              role: 'assistant',
              content: getVcpWelcomeMessage(selectedStock.name)
            }]);
          }
        }
      } catch (e) {
        console.error('Failed to parse VCP chat history from DB', e);
      } finally {
        if (isMounted) setChatLoading(false);
      }
    };

    loadHistory();

    return () => { isMounted = false; };
  }, [selectedStock?.ticker, isModalOpen]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showCommands && filteredCommands.length > 0) {
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
          setShowCommands(false);
          handleVCPChatSend(selectedCmd.cmd); // 선택 즉시 전송
        }
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleVCPChatSend();
    }
  };

  // AI 탭 상태 (GPT vs Gemini vs Perplexity)
  const [activeAiTab, setActiveAiTab] = useState<'gpt' | 'gemini' | 'perplexity'>('gemini');

  // Determine Primary AI (GPT or Perplexity) based on data availability
  // If GPT data exists and NO Perplexity data exists, use GPT (Legacy support)
  // Otherwise default to Perplexity (assuming current config)
  const hasPerplexity = signals.some(s => s.perplexity_recommendation) || aiData?.signals?.some(s => s.perplexity_recommendation);
  const hasGpt = signals.some(s => s.gpt_recommendation) || aiData?.signals?.some(s => s.gpt_recommendation);
  const primaryAI = (hasGpt && !hasPerplexity) ? 'gpt' : 'perplexity';

  // 선택된 종목 변경 시 AI 탭 자동 조정
  useEffect(() => {
    if (!selectedStock) return;

    // Prefer merged signal logic
    const signal = signals.find(s => s.ticker === selectedStock.ticker);
    const stock = aiData?.signals?.find(s => s.ticker === selectedStock.ticker);

    // Helper to check existence
    const hasData = (type: 'gpt' | 'gemini' | 'perplexity') => {
      if (type === 'gpt') return !!(signal?.gpt_recommendation || stock?.gpt_recommendation);
      if (type === 'perplexity') return !!(signal?.perplexity_recommendation || stock?.perplexity_recommendation);
      return !!(signal?.gemini_recommendation || stock?.gemini_recommendation);
    };

    // 현재 탭에 데이터가 없으면 다른 탭으로 자동 전환
    if (activeAiTab === 'gpt' && !hasData('gpt')) {
      if (hasData('perplexity')) setActiveAiTab('perplexity');
      else if (hasData('gemini')) setActiveAiTab('gemini');
    } else if (activeAiTab === 'perplexity' && !hasData('perplexity')) {
      if (hasData('gpt')) setActiveAiTab('gpt');
      else if (hasData('gemini')) setActiveAiTab('gemini');
    }
  }, [selectedStock, aiData, signals, activeAiTab]);

  // 날짜 선택 상태
  const [activeDateTab, setActiveDateTab] = useState<'latest' | 'history'>('latest');
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyDates, setHistoryDates] = useState<string[]>([]);
  const [selectedHistoryDate, setSelectedHistoryDate] = useState<string | null>(null);

  const clearReanalysisPolling = () => {
    if (reanalysisPollRef.current) {
      clearInterval(reanalysisPollRef.current);
      reanalysisPollRef.current = null;
    }
  };

  const isFailedAIReanalysisRunning = (status: any): boolean => {
    const taskType = String(status?.task_type || '').toLowerCase();
    if (Boolean(status?.running) && taskType === 'reanalysis_failed_ai') {
      return true;
    }
    const msg = String(status?.message || '');
    return Boolean(status?.running) && msg.includes('재분석');
  };

  const startReanalysisPolling = (targetDate?: string) => {
    clearReanalysisPolling();
    reanalysisPollRef.current = setInterval(async () => {
      try {
        const status = await krAPI.getVCPStatus();
        if (isFailedAIReanalysisRunning(status)) {
          const progress = status.progress || 0;
          setReanalyzingFailedAI(true);
          setStoppingReanalysis(Boolean(status.cancel_requested));
          setScreenerMessage(`🤖 ${status.message || '실패 AI 재분석 진행 중...'} (${progress}%)`);
          return;
        }

        clearReanalysisPolling();
        setReanalyzingFailedAI(false);
        setStoppingReanalysis(false);

        if (status.status === 'success' || status.status === 'cancelled' || status.status === 'error') {
          await loadSignals(targetDate);
          const prefix = status.status === 'success' ? '✅' : status.status === 'cancelled' ? '🛑' : '❌';
          setScreenerMessage(`${prefix} ${status.message || '실패 AI 재분석 종료'}`);
          setTimeout(() => setScreenerMessage(null), 5000);
        }
      } catch (e) {
        console.error('Failed to poll failed-ai reanalysis status:', e);
      }
    }, 2000);
  };

  useEffect(() => {
    return () => {
      clearReanalysisPolling();
    };
  }, []);

  useEffect(() => {
    loadSignals();
    loadMarketGate();
    checkRunningStatus();
  }, []);

  // 새로고침/재방문 시 실행 상태 복구
  const checkRunningStatus = async () => {
    try {
      const status = await krAPI.getVCPStatus();
      if (status.running) {
        if (isFailedAIReanalysisRunning(status)) {
          setReanalyzingFailedAI(true);
          setStoppingReanalysis(Boolean(status.cancel_requested));
          setScreenerRunning(false);
          setScreenerMessage(`🤖 ${status.message} (재개됨)`);
          startReanalysisPolling(activeDateTab === 'history' ? (selectedHistoryDate || undefined) : undefined);
          return;
        }

        setScreenerRunning(true);
        setScreenerMessage(`🔄 ${status.message} (재개됨)`);

        // 폴링 재시작
        const pollInterval = setInterval(async () => {
          try {
            const s = await krAPI.getVCPStatus();
            if (s.running) {
              setScreenerMessage(`🔄 ${s.message} (${s.progress || 0}%)`);
            } else {
              clearInterval(pollInterval);
              setScreenerMessage('✅ 업데이트 완료! 데이터 로딩...');
              await loadSignals();
              await loadMarketGate();
              setScreenerRunning(false);
              setTimeout(() => setScreenerMessage(null), 3500);
            }
          } catch (e) {
            console.error(e);
          }
        }, 2000);
      }
    } catch (e) {
      console.error("Failed to check status:", e);
    }
  };

  const loadMarketGate = async () => {
    try {
      const gateData = await krAPI.getMarketGate();
      setMarketGate(gateData);
    } catch (e) {
      console.error('Failed to load market gate:', e);
    }
  };

  useEffect(() => {
    if (loading || signals.length === 0) return;

    const updatePrices = async () => {
      try {
        const tickers = signals.map(s => s.ticker);
        if (tickers.length === 0) return;

        const res = await fetch('/api/kr/realtime-prices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tickers })
        });
        const prices = await res.json();

        if (Object.keys(prices).length > 0) {
          setSignals(prev => prev.map(s => {
            if (prices[s.ticker]) {
              const current = prices[s.ticker];
              const entry = s.entry_price || 0;
              let ret = s.return_pct || 0;
              if (entry > 0) {
                ret = ((current - entry) / entry) * 100;
              }
              return { ...s, current_price: current, return_pct: ret };
            }
            return s;
          }));
          setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
        }
      } catch (e) {
        console.error('Price update failed:', e);
      }
    };

    // 페이지 로드 직후 즉시 현재가 업데이트 호출
    updatePrices();

    // 이후 1분 간격으로 업데이트
    const interval = setInterval(updatePrices, 60000);
    return () => clearInterval(interval);
  }, [signals.length, loading]);

  const loadHistoryDates = async () => {
    try {
      const dates = await krAPI.getSignalDates();
      setHistoryDates(dates);
    } catch (e) {
      console.error('Failed to load history dates:', e);
    }
  };

  const loadSignals = async (date?: string) => {
    setLoading(true);

    // 1. Signals 데이터 로드 (Critical Path)
    try {
      const signalsRes = await krAPI.getSignals(date || undefined);
      const loadedSignals = signalsRes.signals || [];
      setSignals(loadedSignals);
      setScannedCount(signalsRes.total_scanned ?? loadedSignals.length);

      // 날짜 설정
      if (date) {
        setSignalDate(new Date(date).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }));
      } else {
        const genAt = signalsRes.generated_at;
        if (genAt) {
          const d = new Date(genAt);
          setSignalDate(d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }));
        }
      }

      setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
    } catch (error) {
      console.error('Failed to load signals:', error);
      setSignals([]);
    } finally {
      // Signals 로드 완료 즉시 로딩 해제 (AI 데이터 기다리지 않음)
      setLoading(false);
    }

    // 2. AI 데이터 로드 (Background / Non-blocking)
    try {
      const aiRes = await krAPI.getAIAnalysis(date);
      setAiData(aiRes);
    } catch (aiError) {
      console.error('Failed to load AI data:', aiError);
    }
  };

  const handleDateSelect = (date: string) => {
    setSelectedHistoryDate(date);
    setActiveDateTab('history');
    setIsHistoryOpen(false);
    loadSignals(date);
  };

  const handleLoadLatest = () => {
    setSelectedHistoryDate(null);
    setActiveDateTab('latest');
    loadSignals();
  };

  const handleReanalyzeFailedAI = async () => {
    if (!isAdmin) {
      setPermissionModal(true);
      return;
    }

    if (reanalyzingFailedAI) {
      if (stoppingReanalysis) return;
      try {
        setStoppingReanalysis(true);
        await krAPI.stopVCPFailedAIReanalysis();
        setScreenerMessage('🛑 실패 AI 재분석 중지 요청을 전송했습니다...');
      } catch (e: any) {
        setStoppingReanalysis(false);
        setScreenerMessage(`❌ ${e?.message || '재분석 중지 요청 실패'}`);
        setTimeout(() => setScreenerMessage(null), 5000);
      }
      return;
    }

    if (screenerRunning) return;

    const targetDate = activeDateTab === 'history' ? (selectedHistoryDate || undefined) : undefined;
    const forceProvider = reanalysisMode === 'failed' ? undefined : reanalysisMode;
    const modeLabel = reanalysisMode === 'gemini' ? 'Gemini 강제' : reanalysisMode === 'second' ? 'Second 강제' : '실패/누락';
    setReanalyzingFailedAI(true);
    setStoppingReanalysis(false);
    setScreenerMessage(`🤖 ${modeLabel} 재분석 시작 요청 중...`);
    try {
      const res: any = await krAPI.reanalyzeVCPFailedAI(targetDate, true, forceProvider);
      setScreenerMessage(`🤖 ${res?.message || '실패 AI 재분석 시작됨'}`);
      startReanalysisPolling(targetDate);
    } catch (e: any) {
      clearReanalysisPolling();
      setScreenerMessage(`❌ ${e?.message || '실패 AI 재분석 실패'}`);
      setTimeout(() => setScreenerMessage(null), 7000);
      setReanalyzingFailedAI(false);
      setStoppingReanalysis(false);
    }
  };

  const getKstDateKey = (value?: string | null): string | null => {
    if (!value) return null;
    const directMatch = value.match(/^(\d{4}-\d{2}-\d{2})/);
    if (directMatch) return directMatch[1];
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;
    return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(parsed);
  };

  const handleBulkBuyVCP = async () => {
    if (isBulkBuyingVCP) return;

    if (activeDateTab !== 'latest') {
      setAlertModal({
        isOpen: true,
        type: 'default',
        title: '오늘 데이터만 가능',
        content: '최신(오늘) VCP 시그널 탭에서만 일괄 매수를 실행할 수 있습니다.'
      });
      return;
    }

    if (!signals.length) {
      setAlertModal({
        isOpen: true,
        type: 'default',
        title: '매수 대상 없음',
        content: '오늘 VCP 시그널 종목이 없습니다.'
      });
      return;
    }

    const todayKst = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date());
    const parsedSignalDates = signals
      .map((signal) => getKstDateKey(signal.signal_date))
      .filter((date): date is string => Boolean(date));
    const hasTodaySignal = parsedSignalDates.length === 0 || parsedSignalDates.some((date) => date === todayKst);

    if (!hasTodaySignal) {
      setAlertModal({
        isOpen: true,
        type: 'default',
        title: '오늘 데이터 아님',
        content: '현재 로딩된 VCP 시그널 날짜가 오늘이 아닙니다. 최신 데이터를 먼저 불러와 주세요.'
      });
      return;
    }

    const uniqueTargets = new Map<string, { ticker: string; name: string; price: number }>();
    signals.forEach((signal) => {
      if (!signal.ticker || uniqueTargets.has(signal.ticker)) return;
      uniqueTargets.set(signal.ticker, {
        ticker: signal.ticker,
        name: signal.name,
        price: signal.current_price || signal.entry_price || 0
      });
    });

    setIsBulkBuyingVCP(true);
    let successCount = 0;
    let failCount = 0;
    let skippedCount = 0;
    const failedItems: string[] = [];

    try {
      const buyOrders: Array<{ ticker: string; name: string; price: number; quantity: number }> = [];
      for (const target of uniqueTargets.values()) {
        if (!Number.isFinite(target.price) || target.price <= 0) {
          skippedCount += 1;
          failedItems.push(`${target.name}(가격 정보 없음)`);
          continue;
        }
        buyOrders.push({
          ticker: target.ticker,
          name: target.name,
          price: target.price,
          quantity: 10
        });
      }

      if (buyOrders.length > 0) {
        try {
          const res = await fetch('/api/portfolio/buy/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orders: buyOrders })
          });
          const result = await res.json();
          const resultRows = Array.isArray(result?.results) ? result.results : [];

          if (resultRows.length > 0) {
            resultRows.forEach((row: any) => {
              const rowName = row?.name || row?.ticker || '종목';
              if (row?.status === 'success') {
                successCount += 1;
              } else {
                failCount += 1;
                failedItems.push(`${rowName}(${row?.message || '매수 실패'})`);
              }
            });
          } else if (result?.status === 'success') {
            successCount += buyOrders.length;
          } else {
            failCount += buyOrders.length;
            failedItems.push(`일괄 매수(${result?.message || '매수 실패'})`);
          }
        } catch (error) {
          console.error('[VCP Bulk Buy] bulk buy failed:', error);
          failCount += buyOrders.length;
          failedItems.push(`일괄 매수(요청 오류)`);
        }
      }

      const summary: string[] = [`성공 ${successCount}건`];
      if (failCount > 0) summary.push(`실패 ${failCount}건`);
      if (skippedCount > 0) summary.push(`스킵 ${skippedCount}건`);
      const failedPreview = failedItems.slice(0, 3).join(', ');
      const failedSuffix = failedItems.length > 3 ? ' 외' : '';
      const resultType: 'default' | 'success' | 'danger' =
        failCount > 0 ? (successCount > 0 ? 'default' : 'danger') : (successCount > 0 ? 'success' : 'default');

      setAlertModal({
        isOpen: true,
        type: resultType,
        title: 'VCP 일괄 매수 결과',
        content: `오늘 VCP 시그널 종목 10주씩 매수 완료\n${summary.join(' / ')}${failedPreview ? `\n실패/스킵: ${failedPreview}${failedSuffix}` : ''}`
      });
    } finally {
      setIsBulkBuyingVCP(false);
    }
  };

  const openChart = async (ticker: string, name: string, period?: string) => {
    setSelectedStock({ name, ticker });
    setIsModalOpen(true);
    setChartLoading(true);
    try {
      const res = await krAPI.getStockChart(ticker, period || chartPeriod.toLowerCase());
      if (res && res.data) {
        setChartData(res.data);
      }
    } catch (e) {
      console.error('Failed to load chart:', e);
    } finally {
      setChartLoading(false);
    }
  };

  const changeChartPeriod = (period: '1M' | '3M' | '6M' | '1Y') => {
    setChartPeriod(period);
    if (selectedStock) {
      openChart(selectedStock.ticker, selectedStock.name, period.toLowerCase());
    }
  };

  const closeChart = () => {
    setIsModalOpen(false);
    setChartData([]);
    setSelectedStock(null);
  };

  const isBulkBuyVCPDisabled =
    isBulkBuyingVCP ||
    loading ||
    !signals.length ||
    activeDateTab !== 'latest';

  const bulkBuyVCPDisabledReason = (() => {
    if (isBulkBuyingVCP) return 'VCP 일괄 매수를 진행 중입니다.';
    if (loading) return 'VCP 시그널 데이터를 불러오는 중입니다.';
    if (activeDateTab !== 'latest') return '최신(오늘) VCP 시그널 탭에서만 일괄 매수를 실행할 수 있습니다.';
    if (!signals.length) return '오늘 VCP 시그널 매수 대상 종목이 없습니다.';
    return '';
  })();

  const bulkBuyVCPTooltip = bulkBuyVCPDisabledReason || '오늘 VCP 시그널 전체를 10주씩 매수합니다.';

  const formatFlow = (value: number | undefined) => {
    if (value === undefined || value === null) return '-';
    const absValue = Math.abs(value);
    const sign = value < 0 ? '-' : '';

    if (absValue >= 10000000000000000) { // 1경 (10^16)
      return `${sign}${(absValue / 10000000000000000).toFixed(1)}경`;
    } else if (absValue >= 1000000000000) { // 1조 (10^12)
      const jo = Math.floor(absValue / 1000000000000);
      const uk = Math.floor((absValue % 1000000000000) / 100000000);
      return uk > 0 ? `${sign}${jo}조${uk}억` : `${sign}${jo}조`;
    } else if (absValue >= 100000000) { // 1억 (10^8)
      return `${sign}${Math.floor(absValue / 100000000)}억`;
    } else if (absValue >= 10000) { // 1만 (10^4)
      return `${sign}${Math.floor(absValue / 10000)}만`;
    }
    return `${sign}${Math.floor(absValue).toLocaleString()}`;
  };

  const getAIBadge = (signal: KRSignal, model: 'gpt' | 'gemini' | 'perplexity') => {
    let rec;
    // 1. Try merged signal data first
    if (model === 'gpt') rec = signal.gpt_recommendation;
    else if (model === 'perplexity') rec = signal.perplexity_recommendation;
    else rec = signal.gemini_recommendation;

    // 2. Fallback to aiData (legacy/separate load)
    if (!rec && aiData) {
      const stock = aiData.signals?.find((s) => s.ticker === signal.ticker);
      if (stock) {
        if (model === 'gpt') rec = stock.gpt_recommendation;
        else if (model === 'perplexity') rec = stock.perplexity_recommendation;
        else rec = stock.gemini_recommendation;
      }
    }

    if (!rec) return <span className="text-gray-500 text-[10px]">-</span>;

    const action = rec.action?.toUpperCase();
    let bgClass = 'bg-yellow-500/20 text-yellow-400';
    let icon = '■';
    let label = '관망';

    if (action === 'BUY') {
      bgClass = 'bg-green-500/20 text-green-400';
      icon = '▲';
      label = '매수';
    } else if (action === 'SELL') {
      bgClass = 'bg-red-500/20 text-red-400';
      icon = '▼';
      label = '매도';
    }

    return (
      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${bgClass} border border-current/30 whitespace-nowrap`} title={rec.reason}>
        {icon} {label}
      </span>
    );
  };



  const handleVCPChatSend = async (msgFromCommand?: string) => {
    // 인자로 받은 메시지가 있으면 그것을 사용, 없으면 입력창 값 사용
    const message = msgFromCommand || chatInput;

    if (!message.trim() || chatLoading) return;

    if (message.trim().toLowerCase() === '/clear') {
      const stockTicker = selectedStock?.ticker || 'default';
      const sessionKey = `vcp_chat_session_id_${stockTicker}`;
      let sessionId = localStorage.getItem(sessionKey);
      if (sessionId) {
        try {
          await fetch(`/api/kr/chatbot/history?session_id=${sessionId}`, { method: 'DELETE' });
        } catch (e) {
          console.error("Failed to clear VCP chat history on server", e);
        }
      }
      setChatHistory([]); // The useEffect will handle injecting the welcome message
      setChatInput('');
      setSelectedCommandIndex(0);
      return;
    }

    // 슬래시 커맨드인 경우 종목 컨텍스트를 붙이지 않음
    const isCommand = message.startsWith('/');
    const stockContext = (selectedStock && !isCommand) ? `[${selectedStock.name}(${selectedStock.ticker})] ` : '';
    const fullMessage = stockContext + message;

    setChatHistory(prev => [...prev, { role: 'user', content: message }]);
    setChatInput(''); // 입력창 즉시 초기화
    setChatLoading(true);

    try {
      // Get auth
      const userEmail = localStorage.getItem('user_email') || '';
      const stockTicker = selectedStock?.ticker || 'default';
      const sessionKey = `vcp_chat_session_id_${stockTicker}`;
      let sessionId = localStorage.getItem(sessionKey);
      if (!sessionId) {
        sessionId = `vcp_${stockTicker}_` + crypto.randomUUID();
        localStorage.setItem(sessionKey, sessionId);
      }

      const res = await fetch('/api/kr/chatbot', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Email': userEmail || '',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify({
          message: fullMessage,
          persona: 'vcp'
        }),
      });

      if (!res.ok || res.status === 401 || res.status === 402 || res.status === 400) {
        let errStr = "서버 통신 오류가 발생했습니다.";
        try {
          const errData = await res.json();
          if (errData.error) errStr = errData.error;
        } catch (e) { }
        setChatHistory(prev => [...prev, { role: 'assistant', content: `⚠️ ${errStr}` }]);
        setChatLoading(false);
        return;
      }

      if (res.body) {
        setChatLoading(false);

        // Setup a new streaming message
        setChatHistory(prev => [...prev, { role: 'assistant', content: "", reasoning: "", isStreaming: true }]);

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
                    setChatHistory(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], content: data.error, isStreaming: false };
                      return newMsgs;
                    });
                  }
                  if (data.clear) {
                    setChatHistory(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = {
                        ...newMsgs[newMsgs.length - 1],
                        content: "",
                        reasoning: ""
                      };
                      return newMsgs;
                    });
                  }
                  if (data.answer_clear) {
                    setChatHistory(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = {
                        ...lastMsg,
                        content: ""
                      };
                      return newMsgs;
                    });
                  }
                  if (data.reasoning_clear) {
                    setChatHistory(prev => {
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
                    setChatHistory(prev => {
                      const newMsgs = [...prev];
                      const lastMsg = newMsgs[newMsgs.length - 1];
                      newMsgs[newMsgs.length - 1] = {
                        ...lastMsg,
                        content: lastMsg.content + answerDelta
                      };
                      return newMsgs;
                    });
                  }
                  if (typeof data.reasoning_chunk === 'string' && data.reasoning_chunk.length > 0) {
                    setChatHistory(prev => {
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
                    setChatHistory(prev => {
                      const newMsgs = [...prev];
                      newMsgs[newMsgs.length - 1] = {
                        ...newMsgs[newMsgs.length - 1],
                        isStreaming: false
                      };
                      return newMsgs;
                    });
                  }
                } catch (e) {
                  console.error("SSE Parse logic error", e);
                }
              }
            }
          }
        }
      }
    } catch (e) {
      setChatHistory(prev => [...prev, { role: 'assistant', content: '⚠️ 서버와 통신이 원활하지 않습니다. 잠시 후 다시 시도해주세요.', isStreaming: false }]);
      setChatLoading(false);
    }
  };

  // ... (Slash Command Logic Update)
  // Deleted duplicate handleKeyDown


  return (
    <div className="space-y-6 md:space-y-8 pb-20 md:pb-0">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-blue-500/20 bg-blue-500/5 text-xs text-blue-400 font-medium mb-2 md:mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping"></span>
            VCP 패턴 스캐너
          </div>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
            VCP <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">시그널</span>
          </h2>
          <p className="text-gray-400 text-sm md:text-lg">Volatility Contraction Pattern + 기관/외국인 수급</p>
        </div>

        {/* 리프레쉬 버튼 */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          {screenerMessage && (
            <span className={`text-xs px-3 py-1 rounded-full whitespace-nowrap ${screenerMessage.includes('성공') || screenerMessage.includes('완료') ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
              {screenerMessage}
            </span>
          )}
          {/* [MOVED] VCP 기준표 버튼 removed from here */}
          <select
            value={reanalysisMode}
            onChange={(e) => setReanalysisMode(e.target.value as 'failed' | 'gemini' | 'second')}
            disabled={screenerRunning || reanalyzingFailedAI}
            className="px-3 py-2.5 md:py-2 rounded-xl bg-white/5 border border-white/10 text-gray-200 text-xs font-semibold disabled:opacity-60"
            title="재분석 실행 모드 선택"
          >
            <option value="failed">실패/누락만</option>
            <option value="gemini">Gemini 강제</option>
            <option value="second">Second 강제</option>
          </select>

          <button
            onClick={handleReanalyzeFailedAI}
            disabled={screenerRunning}
            className={`flex-1 md:flex-none justify-center px-4 py-3 md:py-2.5 rounded-xl font-bold text-sm flex items-center gap-2 transition-all ${reanalyzingFailedAI
              ? 'bg-red-600/80 hover:bg-red-500 text-white'
              : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg hover:shadow-indigo-500/25'
              }`}
          >
            {reanalyzingFailedAI ? (
              <>
                <i className={`fas ${stoppingReanalysis ? 'fa-circle-notch fa-spin' : 'fa-stop-circle'} text-lg`}></i>
                <span>{stoppingReanalysis ? '중지 요청 중...' : '재분석 중지'}</span>
              </>
            ) : (
              <>
                <i className="fas fa-brain"></i>
                <span>실패 AI 재분석</span>
              </>
            )}
          </button>

          <button
            onClick={async () => {
              // ADMIN 권한 체크
              if (!isAdmin) {
                setPermissionModal(true);
                return;
              }
              if (screenerRunning || reanalyzingFailedAI) return;
              setScreenerRunning(true);
              // 1. 실행 요청
              setScreenerMessage('분석 요청 중...');

              try {
                await krAPI.runVCPScreener();
                setScreenerMessage('🔄 분석 시작...');

                // [ROBUST FIX] 백엔드가 /signals/run 응답 전에 status='running'으로 설정하므로
                // sawRunning을 즉시 true로 설정 (이전 stale 상태 구분 불필요)
                let sawRunning = true;
                let pollCount = 0;
                const MAX_POLLS = 150; // 5분 (2초 * 150 = 300초) 안전 타임아웃

                const pollInterval = setInterval(async () => {
                  pollCount++;

                  // 안전 타임아웃: 5분 초과 시 강제 종료
                  if (pollCount > MAX_POLLS) {
                    clearInterval(pollInterval);
                    setScreenerMessage('⏰ 시간 초과 - 백그라운드에서 계속 진행 중일 수 있습니다.');
                    setScreenerRunning(false);
                    setTimeout(() => setScreenerMessage(null), 7000);
                    return;
                  }

                  try {
                    const status = await krAPI.getVCPStatus();

                    if (status.status === 'running' || status.running) {
                      setScreenerMessage(`🔄 ${status.message} (${status.progress || 0}%)`);
                    } else if (status.status === 'success') {
                      clearInterval(pollInterval);
                      setScreenerMessage('✅ 데이터 로딩 중...');

                      // 데이터 새로고침
                      try {
                        await loadSignals();
                        await loadMarketGate();
                      } catch (loadErr) {
                        console.error("Data load error:", loadErr);
                      }

                      setScreenerMessage('✅ 업데이트 완료!');
                      setScreenerRunning(false);
                      setTimeout(() => setScreenerMessage(null), 5000);
                    } else if (status.status === 'error') {
                      clearInterval(pollInterval);
                      setScreenerMessage(`❌ 오류: ${status.message}`);
                      setScreenerRunning(false);
                      setTimeout(() => setScreenerMessage(null), 7000);
                    } else {
                      // IDLE 등 예외적 상태
                      if (!status.running && sawRunning) {
                        clearInterval(pollInterval);
                        setScreenerRunning(false);
                        setScreenerMessage(null);
                      }
                    }
                  } catch (err) {
                    console.error("Polling error:", err);
                    // 네트워크 에러가 반복되면 종료
                    if (pollCount > 5) {
                      // 5회 이상 연속 에러 시에만 카운트 (일시적 에러는 무시)
                    }
                  }
                }, 2000); // 2초마다 확인

              } catch (e: any) {
                setScreenerMessage(`❌ 오류: ${e.message || '요청 실패'}`);
                setScreenerRunning(false);
                setTimeout(() => setScreenerMessage(null), 5000);
              }
            }}
            disabled={screenerRunning || reanalyzingFailedAI}
            className={`flex-1 md:flex-none justify-center px-4 py-3 md:py-2.5 rounded-xl font-bold text-sm flex items-center gap-2 transition-all ${screenerRunning
              ? 'bg-gradient-to-r from-rose-600/80 to-purple-600/80 text-white/80 cursor-wait'
              : 'bg-gradient-to-r from-rose-600 to-purple-600 hover:from-rose-500 hover:to-purple-500 text-white shadow-lg hover:shadow-rose-500/25'
              }`}
          >
            {screenerRunning ? (
              <>
                <i className="fas fa-circle-notch fa-spin text-lg"></i>
                <span>Updating...</span>
              </>
            ) : (
              <>
                <i className="fas fa-sync-alt"></i>
                <span>Refresh VCP</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Inline Chart + AI Analysis Grid (BLUEPRINT Layout) */}


      {/* 실시간 VCP 시그널 테이블 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <span className="w-1 h-5 bg-blue-500 rounded-full"></span>
            실시간 VCP 시그널
          </h3>
          <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs font-bold rounded-full whitespace-nowrap">
            TOP {signals.length}
          </span>
          {/* 스캔 수 표시 */}
          <span className="text-xs text-gray-500 ml-2 whitespace-nowrap">
            (Scanned: {scannedCount})
          </span>
        </div>

        <div className="flex items-center gap-2 relative self-end md:self-auto">
          <SimpleTooltip text={bulkBuyVCPTooltip} align="right" position="top">
            <span className="inline-flex">
              <button
                onClick={handleBulkBuyVCP}
                disabled={isBulkBuyVCPDisabled}
                className="px-3 py-1.5 bg-amber-500/15 hover:bg-amber-500/30 text-amber-300 hover:text-amber-200 rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5 border border-amber-400/30 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                title={bulkBuyVCPTooltip}
              >
                <i className={`fas ${isBulkBuyingVCP ? 'fa-circle-notch fa-spin' : 'fa-cart-shopping'}`}></i>
                <span>{isBulkBuyingVCP ? '일괄 매수 중...' : 'VCP 전체 10주 매수'}</span>
              </button>
            </span>
          </SimpleTooltip>

          {/* [NEW] VCP 기준표 버튼 (Moved here) */}
          <button
            onClick={() => setIsVCPCriteriaModalOpen(true)}
            className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 border border-white/10"
          >
            <i className="fas fa-table"></i>
            <span>VCP 기준표</span>
          </button>

          <button
            onClick={handleLoadLatest}
            disabled={loading}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all disabled:opacity-50 whitespace-nowrap ${activeDateTab === 'latest'
              ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-900/20'
              : 'bg-white/5 hover:bg-white/10 text-gray-400 border border-white/10'
              }`}
          >
            최신
          </button>

          <div className="relative">
            <button
              onClick={() => {
                if (!isHistoryOpen) loadHistoryDates();
                setIsHistoryOpen(!isHistoryOpen);
              }}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all border flex items-center gap-2 whitespace-nowrap ${activeDateTab === 'history'
                ? 'bg-white/10 text-white border-white/20'
                : 'bg-white/5 hover:bg-white/10 text-gray-400 border-white/10'
                }`}
            >
              <i className="fas fa-calendar"></i>
              {selectedHistoryDate || '과거'}
            </button>


            {isHistoryOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setIsHistoryOpen(false)}
                />
                <div className="absolute right-0 top-full mt-2 w-48 bg-[#1c1c1e] border border-white/10 rounded-xl shadow-2xl z-20 py-1 max-h-60 overflow-y-auto custom-scrollbar">
                  {historyDates.length > 0 ? (
                    historyDates.map((date) => (
                      <button
                        key={date}
                        onClick={() => handleDateSelect(date)}
                        className={`w-full text-left px-4 py-2 text-xs hover:bg-white/5 transition-colors ${selectedHistoryDate === date ? 'text-blue-400 font-bold bg-blue-500/10' : 'text-gray-400'
                          }`}
                      >
                        {date}
                      </button>
                    ))
                  ) : (
                    <div className="px-4 py-3 text-xs text-gray-500 text-center">
                      데이터 파일 없음
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl bg-[#1c1c1e] border border-white/10 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1000px]">
            <thead className="bg-black/20">
              <tr className="text-[10px] text-gray-500 border-b border-white/5 uppercase tracking-wider">
                <th className="px-4 py-3 font-semibold min-w-[120px]">Stock</th>
                <th className="px-4 py-3 font-semibold whitespace-nowrap">Date</th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap min-w-[100px] w-[100px]">
                  <SimpleTooltip text="외국인 5일 연속 순매수 금액">외국인 5D</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap min-w-[100px] w-[100px]">
                  <SimpleTooltip text="기관 5일 연속 순매수 금액">기관 5D</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
                  <SimpleTooltip text="클릭하여 모의 투자 계좌로 매수 주문을 실행할 수 있습니다.">Buy</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
                  <SimpleTooltip text="VCP(60%) + 수급(40%) 합산 점수 (높을수록 좋음)">Score</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
                  <SimpleTooltip text="변동성 수축 비율 (0.9 미만 권장, 낮을수록 에너지 응축)">Cont.</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                  <SimpleTooltip text="시그널 발생 당시 진입 추천가">Entry</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                  <SimpleTooltip text="손절가 (현재가 -3%)">Stop</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                  <SimpleTooltip text="목표가 (현재가 +5%)">Target</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                  <SimpleTooltip text="현재 주가 (실시간 업데이트 아님)">Current</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                  <SimpleTooltip text="진입가 대비 현재 수익률 (%)">Return</SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
                  <SimpleTooltip text="Second AI 기반 매매 의견">
                    {/* Priority check for Perplexity if available in any signal, or default to Perplexity */}
                    {primaryAI === 'perplexity' ? 'Perplexity' : 'GPT'}
                  </SimpleTooltip>
                </th>
                <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
                  <SimpleTooltip text="Gemini Pro 기반 매매 의견" align="right">Gemini</SimpleTooltip>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-sm">
              {loading ? (
                <tr>
                  <td colSpan={13} className="p-8 text-center text-gray-500">
                    <i className="fas fa-spinner fa-spin text-2xl text-blue-500/50 mb-3"></i>
                    <p className="text-xs">Loading signals...</p>
                  </td>
                </tr>
              ) : signals.length === 0 ? (
                <tr>
                  <td colSpan={13} className="p-8 text-center text-gray-500">
                    <p>No signals found.</p>
                  </td>
                </tr>
              ) : (
                signals.map((signal) => (
                  <tr
                    key={signal.ticker}
                    onClick={() => openChart(signal.ticker, signal.name)}
                    className="hover:bg-white/5 transition-colors cursor-pointer group"
                  >
                    <td className="px-4 py-3">
                      <div className="flex flex-col whitespace-nowrap">
                        <span className="font-bold text-white group-hover:text-blue-400 transition-colors">
                          {signal.name}
                        </span>
                        <span className="text-[10px] text-gray-500">{signal.ticker}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{signal.signal_date || signalDate || '-'}</td>
                    <td className={`px-4 py-3 text-right font-mono text-xs min-w-[100px] w-[100px] ${signal.foreign_5d > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      <div className="flex items-center justify-end gap-1">
                        {signal.foreign_5d > 0 ? <i className="fas fa-arrow-up text-[8px]"></i> : signal.foreign_5d < 0 ? <i className="fas fa-arrow-down text-[8px]"></i> : null}
                        {formatFlow(signal.foreign_5d)}
                      </div>
                    </td>
                    <td className={`px-4 py-3 text-right font-mono text-xs min-w-[100px] w-[100px] ${signal.inst_5d > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      <div className="flex items-center justify-end gap-1">
                        {signal.inst_5d > 0 ? <i className="fas fa-arrow-up text-[8px]"></i> : signal.inst_5d < 0 ? <i className="fas fa-arrow-down text-[8px]"></i> : null}
                        {formatFlow(signal.inst_5d)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                      <SimpleTooltip text="모의 계좌로 매수 주문을 실행합니다.">
                        <button
                          onClick={() => {
                            setBuyingStock({ ticker: signal.ticker, name: signal.name, price: signal.current_price || signal.entry_price || 0 });
                            setIsBuyModalOpen(true);
                          }}
                          className="w-8 h-8 rounded-full bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white transition-all flex items-center justify-center"
                        >
                          <i className="fas fa-shopping-cart text-xs"></i>
                        </button>
                      </SimpleTooltip>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                        {signal.score ? Math.round(signal.score) : '-'}
                      </span>
                    </td>
                    <td className={`px-4 py-3 text-center font-mono text-xs ${signal.contraction_ratio && signal.contraction_ratio <= 0.6 ? 'text-emerald-400' : 'text-purple-400'
                      }`}>
                      {signal.contraction_ratio?.toFixed(2) ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-gray-400">
                      ₩{signal.entry_price?.toLocaleString() ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-rose-400">
                      {/* 손절가: 현재가 기준 -3% (0.97) */}
                      {(() => {
                        const price = signal.current_price || signal.entry_price || 0;
                        const stop = Math.floor(price * 0.97);
                        return price > 0 ? `₩${stop.toLocaleString()}` : '-';
                      })()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-green-400">
                      {/* 목표가: 현재가 기준 +5% (1.05) */}
                      {(() => {
                        const price = signal.current_price || signal.entry_price || 0;
                        const target = Math.floor(price * 1.05);
                        return price > 0 ? `₩${target.toLocaleString()}` : '-';
                      })()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-white">
                      ₩{signal.current_price?.toLocaleString() ?? '-'}
                    </td>
                    <td className={`px-4 py-3 text-right font-mono text-xs font-bold ${(signal.return_pct && Math.abs(signal.return_pct) >= 0.01)
                      ? (signal.return_pct >= 0 ? 'text-green-400' : 'text-red-400')
                      : 'text-gray-500'
                      }`}>
                      {signal.return_pct !== undefined
                        ? (Math.abs(signal.return_pct) < 0.01 ? <span className="text-gray-600 font-normal">0.0%</span> : `${signal.return_pct >= 0 ? '+' : ''}${signal.return_pct.toFixed(1)}%`)
                        : '-'}
                    </td>

                    <td className="px-4 py-3 text-center">
                      {primaryAI === 'perplexity'
                        ? getAIBadge(signal, 'perplexity')
                        : getAIBadge(signal, 'gpt')}
                    </td>
                    <td className="px-4 py-3 text-center">{getAIBadge(signal, 'gemini')}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-center text-xs text-gray-500">
        Last updated: {lastUpdated || '-'}
      </div>

      {/* Chart Modal with AI Analysis Panel */}
      {isModalOpen && selectedStock && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={closeChart}>
          <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl w-full max-w-[95vw] h-[90vh] overflow-hidden shadow-2xl flex flex-col lg:flex-row" onClick={e => e.stopPropagation()}>
            {/* Left: Chart Section */}
            <div className="flex-none lg:flex-1 flex flex-col h-[45vh] lg:h-auto border-b lg:border-b-0 lg:border-r border-white/10">
              <div className="flex justify-between items-center p-4 border-b border-white/5">
                <h3 className="text-lg font-bold text-white">
                  {selectedStock.name} <span className="text-sm text-gray-500">({selectedStock.ticker})</span>
                </h3>
                <button onClick={closeChart} className="text-gray-400 hover:text-white transition-colors lg:hidden">
                  <i className="fas fa-times text-xl"></i>
                </button>
              </div>
              <div className="flex-1 p-2 lg:p-4 lg:min-h-[400px]">
                {chartLoading ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400">
                    <i className="fas fa-spinner fa-spin text-3xl mb-3"></i>
                    <p>Loading chart data...</p>
                  </div>
                ) : chartData.length > 0 ? (
                  (() => {
                    const signal = signals.find(s => s.ticker === selectedStock.ticker);
                    // VCP 범위 계산: 차트 데이터에서 직접 계산
                    const validData = chartData.filter(d => d.close > 0 && d.high > 0);
                    const recentData = validData.slice(-30); // 최근 30일
                    const last10Days = validData.slice(-10); // 최근 10일
                    const firstHalfHigh = recentData.length > 0 ? Math.max(...recentData.map(d => d.high)) : 0; // 전반부: 30일 고점
                    const secondHalfLow = last10Days.length > 0 ? Math.min(...last10Days.map(d => d.low)) : 0; // 후반부: 10일 저점

                    return (
                      <StockChart
                        data={chartData}
                        ticker={selectedStock.ticker}
                        name={selectedStock.name}
                        vcpRange={{
                          enabled: showVcpRange,
                          firstHalf: firstHalfHigh,
                          secondHalf: secondHalfLow
                        }}
                      />
                    );
                  })()
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500">
                    <i className="fas fa-exclamation-circle text-3xl mb-3"></i>
                    <p>No chart data available.</p>
                  </div>
                )}
              </div>
              {/* VCP Info Bar */}
              {(() => {
                const signal = signals.find(s => s.ticker === selectedStock.ticker);
                if (!signal || chartData.length === 0) return null;

                // VCP 범위 계산: 차트 데이터에서 직접 계산
                const validData = chartData.filter(d => d.close > 0 && d.high > 0);
                const recentData = validData.slice(-30);
                const last10Days = validData.slice(-10);
                const firstHalfHigh = recentData.length > 0 ? Math.max(...recentData.map(d => d.high)) : 0;
                const secondHalfLow = last10Days.length > 0 ? Math.min(...last10Days.map(d => d.low)) : 0;
                const vcpRatio = firstHalfHigh > 0 ? (secondHalfLow / firstHalfHigh).toFixed(2) : '-';

                return (
                  <div className="relative auto-cols-min grid grid-cols-2 lg:flex lg:items-center lg:justify-start lg:gap-8 px-4 py-3 bg-black/30 border-t border-white/5 text-xs text-gray-300">

                    {/* VCP Checkbox */}
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500 font-bold whitespace-nowrap">VCP 패턴</span>
                      <label className="flex items-center gap-1.5 cursor-pointer ml-2">
                        <input
                          type="checkbox"
                          className="w-3 h-3 rounded border-white/20 bg-white/5 text-rose-500 focus:ring-rose-500/30"
                          checked={showVcpRange}
                          onChange={(e) => setShowVcpRange(e.target.checked)}
                        />
                        <span className="text-rose-400 font-medium whitespace-nowrap">범위 표시</span>
                      </label>
                    </div>

                    {/* Ratio */}
                    <div className="flex items-center gap-2 font-mono justify-end lg:justify-start">
                      <span className="text-gray-500">Ratio:</span>
                      <span className={`font-bold ${parseFloat(vcpRatio) <= 0.6 ? 'text-emerald-400' : 'text-cyan-400'}`}>{vcpRatio}</span>
                    </div>

                    {/* First Half */}
                    <div className="flex items-center gap-2 font-mono mt-1 lg:mt-0">
                      <span className="text-gray-500">전반부:</span>
                      <span className="text-white font-bold">₩{firstHalfHigh.toLocaleString()}</span>
                    </div>

                    {/* Second Half */}
                    <div className="flex items-center gap-2 font-mono mt-1 lg:mt-0 justify-end lg:justify-start">
                      <span className="text-gray-500">후반부:</span>
                      <span className="text-white font-bold">₩{secondHalfLow.toLocaleString()}</span>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Right: AI Analysis Panel */}
            <div className="flex-1 lg:flex-none w-full lg:w-[500px] flex flex-col bg-[#131722] min-h-0">
              <div className="flex items-center justify-between p-4 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-blue-500 rounded-full"></span>
                  <span className="text-sm font-bold text-white">AI 상세 분석</span>
                </div>
                <button onClick={closeChart} className="text-gray-400 hover:text-white transition-colors hidden lg:block">
                  <i className="fas fa-times"></i>
                </button>
              </div>

              {/* AI Tabs */}
              {(() => {
                // Use merged signal (signals array) as primary source, fallback to aiData (stock)
                const signal = signals.find(s => s.ticker === selectedStock.ticker);
                const stock = aiData?.signals?.find(s => s.ticker === selectedStock.ticker);

                // Helper to get rec from either source (Explicit access to avoid TS index errors)
                const getRec = (type: 'gpt' | 'gemini' | 'perplexity'): AIRecommendation | undefined => {
                  if (type === 'gpt') return signal?.gpt_recommendation || stock?.gpt_recommendation;
                  if (type === 'perplexity') return signal?.perplexity_recommendation || stock?.perplexity_recommendation;
                  return signal?.gemini_recommendation || stock?.gemini_recommendation;
                };

                let rec;
                if (activeAiTab === 'gpt') rec = getRec('gpt');
                else if (activeAiTab === 'perplexity') rec = getRec('perplexity');
                else rec = getRec('gemini');

                // logic moved to top level effect

                const confidence = rec?.confidence ?? 0;

                return (
                  <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
                    {/* Content Area: Scrollable */}
                    <div className="flex-1 overflow-y-auto">
                      {/* Tab Buttons */}
                      <div className="flex border-b border-white/5 sticky top-0 bg-[#131722] z-20">
                        {getRec('gpt') && (
                          <button
                            onClick={() => setActiveAiTab('gpt')}
                            className={`flex-1 py-3 text-xs font-bold transition-colors ${activeAiTab === 'gpt' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-gray-500 hover:text-gray-300'}`}
                          >
                            <i className="fas fa-robot mr-1"></i> GPT
                          </button>
                        )}
                        {getRec('perplexity') && (
                          <button
                            onClick={() => setActiveAiTab('perplexity')}
                            className={`flex-1 py-3 text-xs font-bold transition-colors ${activeAiTab === 'perplexity' ? 'text-emerald-400 border-b-2 border-emerald-400' : 'text-gray-500 hover:text-gray-300'}`}
                          >
                            <i className="fas fa-search mr-1"></i> Perplexity
                          </button>
                        )}
                        <button
                          onClick={() => setActiveAiTab('gemini')}
                          className={`flex-1 py-3 text-xs font-bold transition-colors ${activeAiTab === 'gemini' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}
                        >
                          <i className="fas fa-gem mr-1"></i> Gemini
                        </button>
                      </div>

                      {/* Confidence Score */}
                      <div className="p-4 flex items-center gap-4">
                        <div className="relative w-14 h-14 shrink-0">
                          <svg className="w-full h-full -rotate-90">
                            <circle cx="28" cy="28" r="24" stroke="currentColor" strokeWidth="4" fill="transparent" className="text-white/10" />
                            <circle
                              cx="28" cy="28" r="24"
                              stroke="currentColor"
                              strokeWidth="4"
                              fill="transparent"
                              strokeDasharray={`${(confidence / 100) * 150.8} 150.8`}
                              className={confidence >= 70 ? 'text-emerald-500' : confidence >= 50 ? 'text-yellow-500' : 'text-red-500'}
                            />
                          </svg>
                          <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm">{confidence}%</span>
                        </div>
                        <div className="flex-1">
                          {rec ? (
                            <div className="bg-black/30 rounded-lg p-3 text-xs text-gray-300 leading-relaxed border border-white/5">
                              "{rec.reason || 'No analysis available.'}"
                            </div>
                          ) : (
                            <div className="text-gray-500 text-xs">AI 분석 데이터 없음</div>
                          )}
                        </div>
                      </div>

                      {/* VCP Score & Stats */}
                      <div className="px-4 pb-4 space-y-3">
                        <div className="bg-black/30 rounded-lg p-3 border border-white/5">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] text-gray-500 uppercase tracking-wider">VCP Score</span>
                            <span className="text-lg font-bold text-blue-400">{signal?.score?.toFixed(1) ?? '-'}</span>
                          </div>
                          <div className="text-xs text-gray-400 leading-relaxed">
                            수축비율 {signal?.contraction_ratio?.toFixed(2) ?? '-'}로 기술적 압축이 양호하고,
                            외국인 5일 순매수 {formatFlow(signal?.foreign_5d)}주(강한 수급)가 기관 매도를
                            압도해 추세 지속 가능성이 높음
                          </div>
                        </div>
                      </div>

                      {/* News Section */}
                      <div className="px-4 pb-4">
                        <div className="flex items-center gap-2 mb-3">
                          <i className="fas fa-newspaper text-gray-500 text-xs"></i>
                          <span className="text-xs font-bold text-gray-400">주요 뉴스</span>
                        </div>
                        <div className="space-y-2">
                          {stock?.news && stock.news.length > 0 ? (
                            stock.news.slice(0, 4).map((news, i) => (
                              <a
                                key={i}
                                href={news.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block text-xs text-gray-400 hover:text-blue-400 transition-colors truncate"
                              >
                                • {news.title}
                              </a>
                            ))
                          ) : (
                            <div className="text-xs text-gray-600">관련 뉴스 없음</div>
                          )}
                        </div>
                      </div>

                      {/* AI Chatbot Section */}
                      <div className="px-4 pb-4 border-t border-white/5 pt-4">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <i className="fas fa-robot text-blue-400 text-xs"></i>
                            <span className="text-xs font-bold text-gray-400">AI 상담 (VCP 전문가)</span>
                          </div>
                          <div className="flex items-center gap-3">
                            {chatHistory.length > 0 && (
                              <button
                                onClick={() => openDeleteConfirmModal('clear_all')}
                                className="text-gray-500 hover:text-red-400 transition-colors cursor-pointer"
                                title="대화 내역 비우기"
                              >
                                <i className="fas fa-trash-alt text-xs"></i>
                              </button>
                            )}
                            <div className="relative group">
                              <i className="fas fa-question-circle text-gray-500 hover:text-gray-300 text-xs cursor-help"></i>
                              <div className="absolute right-0 top-full mt-2 w-56 bg-[#1c1c1e] border border-white/10 rounded-xl p-3 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                                <div className="text-xs font-bold text-gray-200 mb-2">💡 사용법</div>
                                <div className="text-[10px] text-gray-500 space-y-1">
                                  <div>🤖 "이 종목 VCP 패턴 맞아?"</div>
                                  <div>📊 "수급 상황 분석해줘"</div>
                                  <div>💰 "손절가랑 목표가 알려줘"</div>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Chat History */}
                        <div className="space-y-4 mb-3 custom-scrollbar px-1 pb-4">
                          {chatHistory.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-10 text-gray-500 text-xs">
                              <div className="w-12 h-12 bg-white/5 rounded-full flex items-center justify-center mb-3">
                                <i className="fas fa-comment-dots text-xl text-gray-600"></i>
                              </div>
                              <p>"{selectedStock?.name}"에 대해 질문해보세요</p>
                            </div>
                          ) : (
                            <>
                              {chatHistory.map((msg, i) => {
                                const isUser = msg.role === 'user';
                                let displayContent = msg.content;
                                let extractedSuggestions: string[] = [];

                                // 개별 메시지 삭제 로직
                                const handleDeleteMessage = (msgIndex: number) => {
                                  openDeleteConfirmModal('single_message', msgIndex);
                                };

                                if (!isUser) {
                                  const { cleanText, suggestions, reasoning } = parseAIResponse(msg.content, msg.isStreaming, msg.reasoning);
                                  displayContent = cleanText;
                                  extractedSuggestions = suggestions;
                                  const suggestionButtons = extractedSuggestions.length > 0
                                    ? extractedSuggestions
                                    : (!msg.isStreaming && i === chatHistory.length - 1 ? VCP_FALLBACK_SUGGESTIONS : []);

                                  return (
                                    <div key={i} className="flex justify-start relative group">
                                      <div className="flex flex-col gap-2 relative z-10 w-full overflow-hidden inline-block px-3 py-2.5 rounded-2xl text-xs max-w-[90%] leading-relaxed bg-[#2c2c2e] text-gray-200 rounded-bl-none border border-white/5">
                                        <button
                                          onClick={() => handleDeleteMessage(i)}
                                          className="absolute top-2 right-2 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity bg-[#1c1c1e]/80 p-1.5 rounded-full z-20"
                                          title="이 답변 지우기"
                                        >
                                          <i className="fas fa-trash-alt text-[10px]"></i>
                                        </button>

                                        {msg.role === 'assistant' && (
                                          <ThinkingProcess
                                            reasoning={reasoning}
                                            isStreaming={!!msg.isStreaming}
                                            className="mb-2"
                                          />
                                        )}
                                        <ReactMarkdown
                                          remarkPlugins={[remarkGfm]}
                                          components={{
                                            h1: ({ children }) => <h1 className="text-[16px] font-bold text-blue-400 mt-4 mb-2">{children}</h1>,
                                            h2: ({ children }) => <h2 className="text-[14px] font-bold text-blue-300 mt-3 mb-1.5 border-b border-blue-500/20 pb-1">{children}</h2>,
                                            h3: ({ children }) => <h3 className="text-[13px] font-bold text-blue-300 mt-2 mb-1">{children}</h3>,
                                            p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                                            strong: ({ children }) => <span className="font-bold text-blue-300 bg-blue-500/10 px-1 rounded mx-0.5">{children}</span>,
                                            ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 my-1">{children}</ul>,
                                            ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 my-1">{children}</ol>,
                                            li: ({ children }) => <li className="text-gray-300 mb-1 leading-relaxed">{children}</li>,
                                            code: ({ children }) => <code className="font-mono bg-black/30 px-1 rounded text-orange-400">{children}</code>
                                          }}
                                        >
                                          {displayContent}
                                        </ReactMarkdown>

                                        {!isUser && suggestionButtons.length > 0 && (
                                          <div className="flex flex-col gap-1.5 mt-2 pt-3 border-t border-white/10">
                                            <span className="text-[10px] font-bold text-gray-500 mb-0.5"><i className="fas fa-lightbulb text-yellow-500 mr-1"></i>추천 질문</span>
                                            {suggestionButtons.map((sug, idx) => (
                                              <button
                                                key={idx}
                                                onClick={() => handleVCPChatSend(sug)}
                                                className="px-3 py-2 bg-blue-500/10 hover:bg-blue-600 text-blue-300 hover:text-white rounded-lg text-xs transition-colors border border-blue-500/20 text-left shadow-sm hover:shadow-md"
                                              >
                                                {sug}
                                              </button>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  );
                                } else {
                                  // User Message
                                  return (
                                    <div key={i} className="flex justify-end relative group">
                                      <div className="relative inline-block max-w-[90%]">
                                        <button
                                          onClick={() => handleDeleteMessage(i)}
                                          className="absolute top-1 left-[-24px] text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity p-1 z-20"
                                          title="이 질문 지우기"
                                        >
                                          <i className="fas fa-trash-alt text-[10px]"></i>
                                        </button>

                                        <div className="inline-block px-3 py-2.5 rounded-2xl text-xs max-w-full leading-relaxed bg-blue-600 text-white rounded-br-none">
                                          <ReactMarkdown
                                            remarkPlugins={[remarkGfm]}
                                            components={{
                                              h3: ({ children }) => <h3 className="text-[13px] font-bold text-white mt-2 mb-1">{children}</h3>,
                                              p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                                              strong: ({ children }) => <span className="font-bold text-blue-200 bg-blue-500/20 px-1 rounded mx-0.5">{children}</span>,
                                              ul: ({ children }) => <ul className="list-disc pl-5 space-y-1 my-1">{children}</ul>,
                                              ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1 my-1">{children}</ol>,
                                              li: ({ children }) => <li className="text-gray-100 mb-1 leading-relaxed">{children}</li>,
                                              code: ({ children }) => <code className="font-mono bg-black/20 px-1 rounded text-orange-300">{children}</code>
                                            }}
                                          >
                                            {displayContent}
                                          </ReactMarkdown>
                                        </div>
                                      </div>
                                    </div>
                                  );
                                }
                              })}

                            </>
                          )}
                          {chatLoading && (
                            <div className="flex justify-start">
                              <div className="bg-[#2c2c2e] rounded-2xl rounded-bl-none px-4 py-3 border border-white/5">
                                <div className="flex gap-1">
                                  <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"></div>
                                  <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-75"></div>
                                  <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce delay-150"></div>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Fixed Bottom Input Area */}
                    <div className="p-4 border-t border-white/5 bg-[#131722] shrink-0">
                      <div className="relative">
                        {/* Slash Command Popup */}
                        {chatInput.startsWith('/') && filteredCommands.length > 0 && (
                          <div className="absolute bottom-full left-0 w-full mb-1 bg-[#2c2c2e] border border-white/10 rounded-lg shadow-xl overflow-hidden z-50">
                            {filteredCommands.map((cmd, i) => (
                              <button
                                key={i}
                                onClick={() => {
                                  setShowCommands(false);
                                  handleVCPChatSend(cmd.cmd);
                                }}
                                className={`w-full text-left px-3 py-2 text-xs flex justify-between transition-colors ${i === selectedCommandIndex
                                  ? 'bg-blue-500/20 text-white'
                                  : 'text-gray-300 hover:bg-white/5'
                                  }`}
                              >
                                <span className={`font-mono ${i === selectedCommandIndex ? 'text-blue-300' : 'text-blue-400'}`}>{cmd.cmd}</span>
                                <span className="text-gray-500">{cmd.desc}</span>
                              </button>
                            ))}
                          </div>
                        )}

                        <div className="relative">
                          <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => {
                              setChatInput(e.target.value);
                              setShowCommands(e.target.value.startsWith('/'));
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder="AI에게 질문하기... (/ 명령어)"
                            className="w-full pl-4 pr-10 py-3 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 transition-colors"
                          />
                          <button
                            onClick={() => handleVCPChatSend()}
                            disabled={!chatInput.trim() || chatLoading}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 bg-blue-500 rounded-lg flex items-center justify-center text-white hover:bg-blue-600 disabled:opacity-50 disabled:hover:bg-blue-500 transition-colors"
                          >
                            <i className="fas fa-paper-plane text-xs"></i>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );

              })()}
            </div>
          </div>
        </div>
      )}
      {/* Buy Stock Modal */}
      <BuyStockModal
        isOpen={isBuyModalOpen}
        onClose={() => setIsBuyModalOpen(false)}
        stock={buyingStock}
        onBuy={async (ticker, name, price, quantity) => {
          try {
            const res = await fetch('/api/portfolio/buy', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ticker, name, price, quantity })
            });
            const data = await res.json();
            if (data.status === 'success') {
              setAlertModal({
                isOpen: true,
                type: 'success',
                title: '매수 완료',
                content: `${name} ${quantity}주 매수 완료!`
              });
              return true;
            } else {
              setAlertModal({
                isOpen: true,
                type: 'danger',
                title: '매수 실패',
                content: `매수 실패: ${data.message}`
              });
              return false;
            }
          } catch (e) {
            setAlertModal({
              isOpen: true,
              type: 'danger',
              title: '오류 발생',
              content: '매수 요청 중 오류 발생'
            });
            return false;
          }
        }}
      />
      <ConfirmationModal
        isOpen={deleteConfirmModal.isOpen}
        title={deleteConfirmModal.mode === 'clear_all' ? '대화 내역 삭제' : '메시지 삭제'}
        message={deleteConfirmModal.mode === 'clear_all'
          ? '현재 종목의 모든 VCP AI 상담 내역을 삭제하시겠습니까?'
          : '이 메시지를 삭제하시겠습니까?\n삭제하면 이후 대화 문맥이 끊어질 수 있습니다.'}
        onConfirm={handleConfirmDeleteChatHistory}
        onCancel={closeDeleteConfirmModal}
        confirmText="삭제"
        cancelText="취소"
      />
      {/* Alert Modal */}
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

      {/* Permission Denied Modal */}
      <Modal
        isOpen={permissionModal}
        onClose={() => setPermissionModal(false)}
        title="권한 없음"
        type="danger"
        footer={
          <button
            onClick={() => setPermissionModal(false)}
            className="px-4 py-2 rounded-lg text-sm font-bold text-white bg-red-500 hover:bg-red-600 transition-colors"
          >
            확인
          </button>
        }
      >
        <p>관리자만 VCP 스크리너를 실행할 수 있습니다.</p>
        <p className="text-sm text-gray-400 mt-2">관리자 계정으로 로그인해 주세요.</p>
      </Modal>

      {/* VCP Criteria Modal */}
      <VCPCriteriaModal
        isOpen={isVCPCriteriaModalOpen}
        onClose={() => setIsVCPCriteriaModalOpen(false)}
      />
    </div>
  );
}
