'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import Modal from '@/app/components/Modal';
import { fetchAPI } from '@/lib/api';
import { useAdmin } from '@/hooks/useAdmin';

// Tooltip 컴포넌트
function Tooltip({ children, content, className = "", position = "top", align = "center", wide = false }: {
  children: React.ReactNode,
  content: string,
  className?: string,
  position?: 'top' | 'bottom',
  align?: 'left' | 'center' | 'right',
  wide?: boolean
}) {
  const positionClass = position === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2';
  const arrowClass = position === 'bottom' ? 'bottom-full border-b-gray-900/95 -mb-1' : 'top-full border-t-gray-900/95 -mt-1';
  const widthClass = wide ? 'w-64 max-w-[280px]' : 'w-52 max-w-[220px]';

  let alignClass = 'left-1/2 -translate-x-1/2';
  let arrowAlignClass = 'left-1/2 -translate-x-1/2';

  if (align === 'left') {
    alignClass = 'left-0';
    arrowAlignClass = 'left-4';
  } else if (align === 'right') {
    alignClass = 'right-0';
    arrowAlignClass = 'right-4';
  }

  return (
    <span className={`relative group/tooltip inline-flex items-center ${className}`}>
      {children}
      <div className={`absolute ${alignClass} ${positionClass} ${widthClass} px-3 py-2 bg-gray-900/95 text-gray-200 text-[10px] font-medium rounded-lg opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-[100] border border-white/10 shadow-xl backdrop-blur-sm text-center leading-relaxed whitespace-normal`}>
        {content}
        <div className={`absolute ${arrowAlignClass} border-4 border-transparent ${arrowClass}`}></div>
      </div>
    </span>
  );
}

interface FileStatus {
  name: string;
  path: string;
  exists: boolean;
  lastModified: string;
  size: string;
  rowCount: number | null;
  link: string;
  menu: string;
}

interface DataStatusResponse {
  files: FileStatus[];
  update_status: {
    isRunning: boolean;
    lastRun: string;
    progress: string;
  };
}

interface UpdateItem {
  name: string;
  status: 'pending' | 'running' | 'done' | 'error';
}

interface UpdateStatusResponse {
  isRunning: boolean;
  startTime: string | null;
  currentItem: string | null;
  items: UpdateItem[];
}

// getLastBusinessDay helper function
function getLastBusinessDay(): string {
  const today = new Date();
  let date = new Date(today);
  date.setDate(date.getDate() - 1);

  // 주말 건너뛰기
  while (date.getDay() === 0 || date.getDay() === 6) {
    date.setDate(date.getDate() - 1);
  }
  return date.toISOString().split('T')[0];
}

export default function DataStatusPage() {
  const fileDescriptions: Record<string, string> = {
    'Daily Prices': 'KOSPI, KOSDAQ 전 종목의 최근 60일간 일별 시세(OHLCV) 데이터입니다.',
    'Institutional Trend': '전 종목의 최근 30일간 외국인/기관 순매수 수급 동향 데이터입니다.',
    'VCP Signals': '가격 변동성 축소(VCP)와 수급 패턴을 분석하여 포착된 급등 예상 종목 리스트입니다.',
    'AI Analysis': '기본적인 마켓 데이터와 지표를 바탕으로 생성된 1차 AI 시장 분석 리포트입니다.',
    'AI Jongga V2': '실시간 Toss 증권 데이터, 뉴스, 재무제표를 Gemini 3.0이 심층 분석한 종가베팅 추천 종목입니다.',
    'Market Gate': 'KOSPI, KOSDAQ 지수 및 주요 섹터별 등락률을 포함한 시장 전체 현황 데이터입니다.' // 표시용만 유지, 수집 대상 X
  };

  const [data, setData] = useState<DataStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [updateItems, setUpdateItems] = useState<UpdateItem[]>([]);
  const [updateProgress, setUpdateProgress] = useState<string>('');
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // ADMIN 권한 체크
  const { isAdmin, isLoading: isAdminLoading } = useAdmin();

  // 날짜 선택 state (기본값: 오늘 - 실시간)
  const [targetDate, setTargetDate] = useState<string>('');
  const [useTodayMode, setUseTodayMode] = useState(true);

  // 데이터 로드 (전체)
  const loadData = useCallback(async () => {
    // Safety Force Stop
    const timer = setTimeout(() => {
      setLoading(prev => prev ? false : prev);
    }, 10000);

    try {
      const data: DataStatusResponse = await fetchAPI('/api/system/data-status');
      setData(data);
    } catch (error) {
      console.error('Failed to load data status:', error);
    } finally {
      clearTimeout(timer);
    }
  }, []);

  // 업데이트 상태만 폴링 (가벼움)
  const pollUpdateStatus = useCallback(async () => {
    try {
      const status: UpdateStatusResponse = await fetchAPI('/api/system/update-status');

      // 로컬 updating 상태를 우선시하되, 백엔드가 실행 중이고 로컬이 아니면 동기화 (선택적)
      // 여기서는 handleUpdateAll이 클라이언트 주도이므로 백엔드 isRunning을 강제로 반영하지 않음
      // 다만 개별 업데이트나 다른 세션에서의 업데이트 감지를 위해 참고할 수는 있음.
      // 하지만 현재 문제 해결을 위해 handleUpdateAll 실행 중에는 백엔드 상태에 의해 updating이 덮어써지지 않도록 주의.

      // 로컬에서 updating 중이라도 백엔드 상태와 동기화


      setUpdating(status.isRunning);

      // 상태가 있으면 무조건 표시 (완료 후에도 결과 확인 가능하도록)
      if (status.items && status.items.length > 0) {
        setUpdateItems(status.items);
      }

      setUpdateProgress(status.isRunning && status.currentItem ? `${status.currentItem} 업데이트 중...` : '');

      // 완료되면 폴링 중지 및 데이터 새로고침
      if (!status.isRunning && pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;

        // 백엔드 파일 시스템 저장이 완료될 때까지 약간의 지연 시간을 둠 (정합성 보장)
        setTimeout(async () => {
          await loadData();
          setUpdating(false);
          setUpdatingItem(null);
        }, 1000);
      } else if (status.isRunning && !pollingRef.current) {
        // 실행 중인데 폴링이 없으면 시작 (페이지 마운트 대응)
        startPolling();
      }

    } catch (error) {
      console.error('Failed to poll update status:', error);
    }
  }, [loadData, updating, updateItems.length]);

  // 폴링 시작
  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    pollingRef.current = setInterval(pollUpdateStatus, 500);
  }, [pollUpdateStatus]);

  useEffect(() => {
    setLoading(true);
    loadData().finally(() => setLoading(false));

    // 페이지 로드 시 업데이트 상태 확인
    pollUpdateStatus();

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 마운트 시 한 번만 실행 (의존성 배열 비움)

  const [modal, setModal] = useState<{
    isOpen: boolean;
    type: 'default' | 'danger' | 'success';
    title: string;
    content: string;
    onConfirm?: () => void;
    showCancel?: boolean;
  }>({
    isOpen: false, // Start closed
    type: 'default',
    title: '',
    content: '',
    showCancel: false
  });

  const [updatingItem, setUpdatingItem] = useState<string | null>(null);

  // 페이지 로드 시 진행 중인 백그라운드 작업 확인
  useEffect(() => {
    const checkRunningStatus = async () => {
      try {
        const data: any = await fetchAPI('/api/kr/jongga-v2/status');

        // 백엔드에서 실행 중이면 스피너 복구 및 폴링 시작
        if (data.isRunning) {
          setUpdatingItem('AI Jongga V2');

          // 폴링 재개 로직
          const poll = async () => {
            let completed = false;
            while (!completed) {
              await new Promise(r => setTimeout(r, 2000));
              try {
                const statusData: any = await fetchAPI('/api/kr/jongga-v2/status');
                if (!statusData.isRunning) {
                  completed = true;
                  setUpdatingItem(null);
                  await loadData();
                }
              } catch (e) { console.error("Poll fail", e); completed = true; }
            }
          };
          poll();
        }

      } catch (e) {
        console.error("Failed to check running status:", e);
      }
    };

    checkRunningStatus();
  }, [loadData]);

  // VCP Status Check added to checkRunningStatus logic (merged for better readability if needed, but separate is fine)
  useEffect(() => {
    const checkVcpStatus = async () => {
      try {
        const status: any = await fetchAPI('/api/kr/signals/status');
        if (status.running) {
          setUpdatingItem('VCP Signals');

          // Poll VCP
          const poll = async () => {
            let running = true;
            while (running) {
              await new Promise(r => setTimeout(r, 2000));
              try {
                const newStatus: any = await fetchAPI('/api/kr/signals/status');
                if (!newStatus.running) {
                  running = false;
                  setUpdatingItem(null);
                  await loadData();
                }
              } catch (e) {
                console.error("Poll VCP fail", e);
                running = false;
              }
            }
          };
          poll();
        }
      } catch (e) {
        console.error("Failed to check VCP status:", e);
      }
    };

    // Only run if not already updating something
    if (!updatingItem) {
      checkVcpStatus();
    }
  }, []); // Run once on mount

  // 현재 선택된 날짜 (실시간 모드면 빈 문자열, 아니면 선택된 날짜)
  const getEffectiveTargetDate = () => {
    return useTodayMode ? null : targetDate;
  };

  // 개별 업데이트 로직 분리 (재사용 위해)
  const performUpdate = async (fileName: string, effectiveDate: string | null) => {
    try {
      // Single item update using global system (Unified Async Update)
      await fetchAPI('/api/system/start-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: [fileName], target_date: effectiveDate, force: true })
      });

      // Trigger polling immediately to catch the 'running' status
      startPolling();

    } catch (e: any) {
      if (e.status === 409) {
        setModal({
          isOpen: true,
          type: 'default',
          title: '업데이트 중복',
          content: '⚠️ 이미 다른 업데이트가 진행 중입니다. 잠시 후 다시 시도해주세요.',
          showCancel: false
        });
      } else {
        throw e;
      }
    }
  };

  const handleUpdate = async (fileName: string) => {
    if (updatingItem) return;

    // ADMIN 권한 체크
    if (!isAdmin) {
      setModal({
        isOpen: true,
        type: 'danger',
        title: '권한 없음',
        content: '관리자만 데이터 업데이트를 수행할 수 있습니다.\n\n관리자 계정으로 로그인해 주세요.',
        showCancel: false
      });
      return;
    }

    setUpdatingItem(fileName);
    const effectiveDate = getEffectiveTargetDate();

    try {
      await performUpdate(fileName, effectiveDate);
    } catch (error) {
      console.error(`Update failed for ${fileName}:`, error);
    } finally {
      setUpdatingItem(null);
    }
  };

  const handleUpdateAll = async () => {
    if (updating) return;

    // ADMIN 권한 체크
    if (!isAdmin) {
      setModal({
        isOpen: true,
        type: 'danger',
        title: '권한 없음',
        content: '관리자만 데이터 업데이트를 수행할 수 있습니다.\n\n관리자 계정으로 로그인해 주세요.',
        showCancel: false
      });
      return;
    }

    const effectiveDate = getEffectiveTargetDate();
    const itemsToUpdate = ['Daily Prices', 'Institutional Trend', 'VCP Signals', 'AI Analysis', 'AI Jongga V2', 'Market Gate'];

    setUpdating(true);
    setUpdateItems([]);

    try {
      // 순차적으로 업데이트 실행 (Backend Orchestration)
      await fetchAPI('/api/system/start-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: itemsToUpdate, target_date: effectiveDate, force: true })
      });

      setUpdateProgress('업데이트 시작 요청 완료...');
      // Polling start immediately
      startPolling();

    } catch (error: any) {
      console.error('Update All failed:', error);
      setModal({
        isOpen: true,
        type: 'danger',
        title: '업데이트 오류',
        content: error.message || '전체 업데이트 시작 중 오류가 발생했습니다.',
        showCancel: false
      });
      setUpdating(false); // Only reset on error, otherwise let poll handle it
    }
  };


  const formatTimeAgo = (isoString: string) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}일 전`;
    if (diffHours > 0) return `${diffHours}시간 ${diffMins % 60}분 전`;
    if (diffMins > 0) return `${diffMins}분 전`;
    if (diffMins > 0) return `${diffMins}분 전`;
    return '방금 전';
  };

  const handleStopUpdate = async () => {
    try {
      await fetchAPI('/api/system/stop-update', { method: 'POST' });
    } catch (e) {
      console.error("Failed to stop update:", e);
    }
  };

  const handleSendMessage = (fileName: string) => {
    if (fileName !== 'AI Jongga V2') return;

    const effectiveDate = getEffectiveTargetDate();
    const confirmMsg = effectiveDate
      ? `${effectiveDate} 기준 종가베팅 메시지를 발송하시겠습니까?`
      : '최신 종가베팅 메시지를 발송하시겠습니까?';

    setModal({
      isOpen: true,
      type: 'default',
      title: '메시지 발송 확인',
      content: confirmMsg,
      showCancel: true,
      onConfirm: () => performSendMessage(effectiveDate)
    });
  };

  const performSendMessage = async (date: string | null) => {
    setModal(prev => ({ ...prev, isOpen: false }));

    try {
      const resData: any = await fetchAPI('/api/kr/jongga-v2/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_date: date })
      });

      setModal({
        isOpen: true,
        type: 'success',
        title: '발송 성공',
        content: resData.message || '메시지 발송 성공',
        showCancel: false
      });

    } catch (e: any) {
      console.error("Failed to send message:", e);
      setModal({
        isOpen: true,
        type: 'danger',
        title: '발송 실패',
        content: `오류: ${e.message || e.data?.message || '알 수 없는 오류'}`,
        showCancel: false
      });
    }
  };

  const isItemRunning = (name: string) => {
    return (
      updatingItem === name ||
      updateItems.some(item => item.name === name && (item.status === 'running' || item.status === 'pending'))
    );
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-500/20 bg-emerald-500/5 text-xs text-emerald-400 font-medium mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            시스템 상태
          </div>
          <h2 className="text-2xl md:text-3xl font-bold tracking-tighter text-white leading-tight mb-2">
            데이터 <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400">상태</span>
          </h2>
          <p className="text-gray-400 text-lg">데이터 파일 상태 및 업데이트 현황</p>
        </div>

        <div className="flex flex-col items-end gap-3">
          {/* Update Items Progress */}
          {updateItems.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-end">
              {updateItems.map((item) => (
                <div
                  key={item.name}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium border ${item.status === 'done' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                    item.status === 'running' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                      item.status === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                        'bg-gray-500/10 text-gray-400 border-gray-500/20'
                    }`}
                >
                  {item.status === 'running' && <i className="fas fa-spinner animate-spin text-[8px]"></i>}
                  {item.status === 'done' && <i className="fas fa-check text-[8px]"></i>}
                  {item.status === 'error' && <i className="fas fa-times text-[8px]"></i>}
                  {item.status === 'pending' && <i className="fas fa-clock text-[8px]"></i>}
                  {item.name}
                </div>
              ))}
            </div>
          )}

          {(updateProgress || updatingItem) && (
            <div className="text-xs text-emerald-400 animate-pulse">
              <i className="fas fa-spinner animate-spin mr-2"></i>
              {updateProgress || `${updatingItem} 업데이트 중...`}
            </div>
          )}

          {/* Date Selector + Update Button */}
          <div className="flex items-center gap-3">
            {/* Date Mode Toggle */}
            <div className="flex items-center bg-[#1c1c1e] rounded-xl border border-white/10 overflow-hidden">
              <button
                onClick={() => setUseTodayMode(true)}
                className={`px-3 py-2 text-xs md:text-sm font-medium transition-all whitespace-nowrap ${useTodayMode
                  ? 'bg-emerald-500 text-white'
                  : 'text-gray-400 hover:text-white'
                  }`}
              >
                <i className="fas fa-clock mr-2"></i>
                실시간
              </button>
              <button
                onClick={() => {
                  setUseTodayMode(false);
                  if (!targetDate) setTargetDate(getLastBusinessDay());
                }}
                className={`px-3 py-2 text-xs md:text-sm font-medium transition-all whitespace-nowrap ${!useTodayMode
                  ? 'bg-purple-500 text-white'
                  : 'text-gray-400 hover:text-white'
                  }`}
              >
                <i className="fas fa-calendar-alt mr-2"></i>
                날짜 지정
              </button>
            </div>

            {/* Date Picker (only visible when not in today mode) */}
            {!useTodayMode && (
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="px-4 py-2 bg-[#1c1c1e] border border-purple-500/30 rounded-xl text-white font-mono text-sm focus:outline-none focus:border-purple-500"
              />
            )}

            {/* ADMIN만 전체 업데이트 버튼 표시 */}
            {!isAdminLoading && isAdmin && (
              <button
                onClick={handleUpdateAll}
                disabled={updating || !!updatingItem}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-500/50 text-white text-xs md:text-sm font-bold rounded-xl transition-all shadow-lg hover:shadow-emerald-500/25 whitespace-nowrap"
              >
                <i className={`fas fa-sync-alt ${updating ? 'animate-spin' : ''}`}></i>
                {updating ? '업데이트 중...' : '전체 데이터 업데이트'}
              </button>
            )}
            {!isAdminLoading && !isAdmin && (
              <span className="text-xs text-amber-400 bg-amber-500/10 px-3 py-2 rounded-xl border border-amber-500/20">
                <i className="fas fa-lock mr-1.5"></i>
                관리자 전용
              </span>
            )}

            {updating && (
              <button
                onClick={handleStopUpdate}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl transition-all shadow-lg hover:shadow-red-500/25"
              >
                <i className="fas fa-stop"></i>
                중지
              </button>
            )}
          </div>

          {/* Date indicator */}
          {!useTodayMode && targetDate && (
            <div className="text-xs text-purple-400">
              <i className="fas fa-calendar-check mr-1"></i>
              {targetDate} 기준 데이터 수집
            </div>
          )}
        </div>
      </div>

      {/* Data Files Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 animate-pulse">
              <div className="h-6 w-32 bg-white/10 rounded mb-4"></div>
              <div className="h-4 w-48 bg-white/10 rounded mb-2"></div>
              <div className="h-4 w-24 bg-white/10 rounded"></div>
            </div>
          ))
        ) : (
          data?.files.map((file) => (
            <div
              key={file.name}
              className="p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 hover:border-emerald-500/30 transition-all group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                    <i className="fas fa-file-alt text-emerald-400"></i>
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-lg font-bold text-white truncate">{file.name}</h3>
                    <p className="text-xs text-gray-500 mt-1 truncate">{file.path}</p>
                  </div>
                </div>
                <div className={`px-2 py-1 rounded text-[10px] font-bold ${file.exists
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
                  }`}>
                  {file.exists ? '생성됨' : '미생성'}
                </div>
              </div>

              <div className="space-y-3 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">크기</span>
                  <span className="text-gray-300 font-mono">{file.size}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">행 수</span>
                  <span className="text-gray-300 font-mono">
                    {file.rowCount !== null ? `${file.rowCount.toLocaleString()} lines` : '-'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">최근 수정</span>
                  <div className="text-right">
                    <div className="text-gray-300">{formatTimeAgo(file.lastModified)}</div>
                    <div className="text-[10px] text-gray-600">{file.lastModified || '-'}</div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-4 border-t border-white/5">
                {!isAdminLoading && isAdmin && (
                  <button
                    onClick={() => handleUpdate(file.name)}
                    disabled={updating || !!updatingItem}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-[#2c2c2e] hover:bg-[#3c3c3e] disabled:opacity-50 text-xs text-gray-300 font-medium rounded-lg transition-colors"
                  >
                    <i className={`fas fa-sync-alt ${isItemRunning(file.name) ? 'animate-spin' : ''}`}></i>
                    {isItemRunning(file.name) ? '업데이트 중...' : '업데이트'}
                  </button>
                )}
                {file.name === 'AI Jongga V2' && isAdmin && (
                  <button
                    onClick={() => handleSendMessage(file.name)}
                    disabled={updating || !!updatingItem || !file.exists}
                    className="flex-none w-10 h-9 flex items-center justify-center bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-lg transition-colors disabled:opacity-30"
                    title="메시지 발송"
                  >
                    <i className="fas fa-paper-plane"></i>
                  </button>
                )}
              </div>

              <Tooltip content={fileDescriptions[file.name] || '데이터 설명이 없습니다.'} className="mt-3 w-full">
                <div className="w-full text-center text-[10px] text-gray-600 hover:text-gray-400 transition-colors cursor-help">
                  <i className="fas fa-info-circle mr-1"></i>
                  데이터 설명 보기
                </div>
              </Tooltip>
            </div>
          ))
        )}
      </div>

      {/* Modal */}
      <Modal
        isOpen={modal.isOpen}
        onClose={() => setModal({ ...modal, isOpen: false })}
        title={modal.title}
        type={modal.type}
        footer={
          /* Footer Content Construction */
          (modal.showCancel || modal.onConfirm) ? (
            <>
              {modal.showCancel && (
                <button
                  onClick={() => setModal({ ...modal, isOpen: false })}
                  className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-white/5"
                >
                  취소
                </button>
              )}
              {modal.onConfirm && (
                <button
                  onClick={modal.onConfirm}
                  className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold rounded-lg transition-colors shadow-lg hover:shadow-emerald-500/25"
                >
                  확인
                </button>
              )}
            </>
          ) : (
            <button
              onClick={() => setModal({ ...modal, isOpen: false })}
              className="px-4 py-2 bg-[#2c2c2e] hover:bg-[#3c3c3e] text-white text-sm font-bold rounded-lg transition-colors border border-white/5"
            >
              확인
            </button>
          )
        }
      >
        <div className="whitespace-pre-wrap">{modal.content}</div>
      </Modal>
    </div>
  );
}
