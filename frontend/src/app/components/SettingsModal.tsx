'use client';

import { useState, useEffect } from 'react';
import Modal from './Modal';
import { useRouter } from 'next/navigation';
import { useSession, signIn, signOut } from "next-auth/react";
import { useAdmin } from '@/hooks/useAdmin';
import { getBrowserSessionId } from '@/lib/session';
import { apiKeyFieldProps, pickNotificationEnv } from './settingsEnv';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: { name: string; email: string; persona: string };
  onSave: (name: string, email: string, persona: string) => Promise<void>;
}

type Tab = 'profile' | 'api' | 'system' | 'notification';

export default function SettingsModal({ isOpen, onClose, profile, onSave }: SettingsModalProps) {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [activeTab, setActiveTab] = useState<Tab>('profile');
  const [name, setName] = useState(profile.name);
  const [email, setEmail] = useState(profile.email || 'user@example.com');
  const [persona, setPersona] = useState(profile.persona);
  const [isSaving, setIsSaving] = useState(false);
  const [envVars, setEnvVars] = useState<Record<string, string>>({});
  const [isLoadingEnv, setIsLoadingEnv] = useState(false);
  const [role, setRole] = useState('엔지니어링');
  const [isCustomRole, setIsCustomRole] = useState(false);



  // ADMIN 권한 체크
  const { isAdmin } = useAdmin();

  // Google Login State — useSession 이 이미 주는 값이므로 렌더 중에 그대로 읽는다.
  const isGoogleLoggedIn = status === 'authenticated';
  const googleUserInfo = isGoogleLoggedIn && session?.user
    ? { name: session.user.name || "User", email: session.user.email || "" }
    : null;
  const [quota, setQuota] = useState<{ usage: number, limit: number, remaining: number } | null>(null);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    if (session?.user?.email && isOpen) {
      // 신원은 서버가 세션에서 정한다. 쿼리로 이메일을 넘기면 URL 한 줄로 남의
      // 사용량을 조회할 수 있었다.
      fetch('/api/kr/user/quota')
        .then(res => res.json())
        .then(data => setQuota(data))
        .catch(e => console.error(e));
    }
  }, [session, isOpen]);

  // Watchlist State
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [isWatchlistLoaded, setIsWatchlistLoaded] = useState(false);
  const [newStock, setNewStock] = useState('');

  useEffect(() => {
    if (isOpen) {
      setName(profile.name);
      setEmail(profile.email || 'user@example.com');
      setPersona(profile.persona);

      // Load watchlist from localStorage
      const savedWatchlist = localStorage.getItem('watchlist');
      if (savedWatchlist) {
        try {
          setWatchlist(JSON.parse(savedWatchlist));
        } catch {
          setWatchlist([]);
        }
      }
      setIsWatchlistLoaded(true);
    }
  }, [isOpen, profile]);

  // Watchlist 자동 저장 (변경 시 즉시 반영)
  // Watchlist 자동 저장 (변경 시 즉시 반영)
  useEffect(() => {
    // 로드 완료 전에는 저장 방지 (데이터 덮어쓰기 방지)
    if (!isWatchlistLoaded) return;

    if (watchlist.length > 0) {
      localStorage.setItem('watchlist', JSON.stringify(watchlist));
    } else if (isOpen) {
      // 빈 배열이어도 사용자가 모두 삭제했을 수 있으므로 저장
      localStorage.setItem('watchlist', JSON.stringify([]));
    }
  }, [watchlist, isOpen, isWatchlistLoaded]);

  // [INFRA-025] 서버가 이 경로를 관리자 토큰으로 막았다. 비관리자가 모달을 열 때마다
  // 403 을 받아 올 이유가 없으므로 요청 자체를 보내지 않는다.
  useEffect(() => {
    if (isOpen && isAdmin) {
      fetchEnvVars();
    }
  }, [isOpen, isAdmin]);

  const fetchEnvVars = async () => {
    setIsLoadingEnv(true);
    try {
      const res = await fetch(`/api/system/env?t=${new Date().getTime()}`, { cache: 'no-store' });
      if (res.ok) {
        const data = await res.json();

        // 마스킹 값은 그대로 둔다. apiKeyFieldProps 가 입력 필드의 값이 아니라
        // 자리 표시자로 돌리고, 서버의 update_env_file 도 `*` 가 섞인 값을 받으면
        // 기존 키를 유지하므로 되돌려 보내도 덮어쓰지 않는다.
        setEnvVars(data);
      }
    } catch (error) {
      console.error("Failed to fetch env vars:", error);
    } finally {
      setIsLoadingEnv(false);
    }
  };

  const handleEnvChange = (key: string, value: string) => {
    setEnvVars(prev => ({ ...prev, [key]: value }));
  };

  const handleResetData = () => {
    setIsDeleteConfirmOpen(true);
  };

  const performResetData = async () => {
    try {
      // 이 화면의 「초기화」는 브라우저에 남은 것만 지운다. 서버 .env 를 지우던
      // DELETE 는 [INFRA-025] 에서 라우트째 없앴다.
      localStorage.clear();
      sessionStorage.clear();
      await signOut({ callbackUrl: '/' });
    } catch (e) {
      console.error(e);
      setTestModal({
        isOpen: true,
        type: 'danger',
        title: '초기화 실패',
        content: '계정 삭제 처리에 실패했습니다.'
      });
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    // 저장 대상이 서로 다른 탭의 값이므로 하나가 실패해도 나머지는 진행한다. 한 줄로
    // 이어 두면 프로필 저장이 400 을 받았을 때 API 키와 관심종목까지 저장되지 않는데,
    // 화면에는 「설정 저장 중 오류」만 떠서 어느 탭이 원인인지 알 수 없다.
    const failed: string[] = [];
    try {
      // 1. Save Profile
      await onSave(name, email, persona);
    } catch (error) {
      console.error("Profile save error:", error);
      failed.push('프로필');
    }

    // 비관리자에게는 .env 탭이 아예 없으므로 보낼 값도 없다. 그대로 두면 저장할
    // 때마다 403 을 받아 「API 설정」이 실패 목록에 남는다.
    if (isAdmin) {
      try {
        // 2. Save Env Vars
        const res = await fetch('/api/system/env', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(envVars)
        });

        if (!res.ok) {
          const detail: unknown = await res.json().catch(() => null);
          const rejected = detail && typeof detail === 'object' && 'rejected' in detail
            && detail.rejected && typeof detail.rejected === 'object' && !Array.isArray(detail.rejected)
            ? Object.keys(detail.rejected) : [];
          failed.push(rejected.length ? `API 설정 (${rejected.join(', ')})` : 'API 설정');
        }
      } catch (error) {
        console.error("Env save error:", error);
        failed.push('API 설정');
      }
    }

    try {
      // 3. Save Watchlist to localStorage
      localStorage.setItem('watchlist', JSON.stringify(watchlist));

      setTestModal(failed.length === 0
        ? {
          isOpen: true,
          type: 'success',
          title: '저장 완료',
          content: '설정이 성공적으로 저장되었습니다.'
        }
        : {
          isOpen: true,
          type: 'danger',
          title: '일부 저장 실패',
          content: `${failed.join(', ')} 저장에 실패했습니다. 나머지 설정은 저장되었습니다.`
        });
    } catch (error) {
      console.error("Save error:", error);
      setTestModal({
        isOpen: true,
        type: 'danger',
        title: '오류 발생',
        content: '설정 저장 중 오류가 발생했습니다.'
      });
    } finally {
      setIsSaving(false);
      // onClose(); -> 저장 후 닫지 않음 (사용자 요청)
      router.refresh();
    }
  };

  const handleAddStock = () => {
    const trimmed = newStock.trim();
    if (trimmed && !watchlist.includes(trimmed)) {
      setWatchlist([...watchlist, trimmed]);
      setNewStock('');
    }
  };

  const handleRemoveStock = (stock: string) => {
    setWatchlist(watchlist.filter(s => s !== stock));
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddStock();
    }
  };

  // NextAuth
  // const { data: session, status } = useSession(); // Moved to top

  // 세션이 붙으면 비어 있는 프로필 입력만 채운다.
  useEffect(() => {
    if (status === 'authenticated' && session?.user) {
      if (!name) setName(session.user.name || "");
      if (!email || email === 'user@example.com') setEmail(session.user.email || "");
    }
  }, [status, session]);

  const handleGoogleLogin = () => {
    // Google Login via NextAuth
    signIn('google');
  };

  const handleGoogleLogout = () => {
    signOut();
  };

  // API 키는 서버의 .env 에만 둔다. 브라우저에 남기면 보호 수단이 없는 평문이 되고,
  // 서버가 이미 마스킹한 값을 돌려주므로 캐시할 이유도 없다.
  // 예전 버전이 남겨 둔 값이 있으면 설정을 열 때 정리한다.
  useEffect(() => {
    if (isOpen) {
      for (const key of ['X-Gemini-Key', 'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'PERPLEXITY_API_KEY']) {
        localStorage.removeItem(key);
      }
    }
  }, [isOpen]);

  // Notification Test
  const [isTesting, setIsTesting] = useState(false);
  const [testModal, setTestModal] = useState<{ isOpen: boolean, type: 'default' | 'success' | 'danger', title: string, content: string }>({
    isOpen: false,
    type: 'default',
    title: '',
    content: ''
  });

  const handleTestNotification = async (platform: 'discord' | 'telegram' | 'email') => {
    // 알림 탭은 관리자에게만 보이지만, 화면 조건 하나가 바뀌어도 .env 저장 요청이
    // 새지 않도록 여기서도 막는다.
    if (!isAdmin) return;
    setIsTesting(true);
    try {
      // 먼저 알림 설정을 저장한다. 서버가 .env 에서 읽어야 발송할 수 있기 때문이다.
      // 저장 버튼을 누르지 않은 요청이므로 알림에 필요한 키만 보낸다.
      try {
        const savedResponse = await fetch('/api/system/env', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(pickNotificationEnv(envVars))
        });
        if (!savedResponse.ok) throw new Error('Settings save failed');
        const saved: unknown = await savedResponse.json();
        if (!saved || typeof saved !== 'object' || !('status' in saved) || saved.status !== 'ok') {
          throw new Error('Settings save was not confirmed');
        }
      } catch {
        setTestModal({
          isOpen: true,
          type: 'danger',
          title: '설정 저장 실패',
          content: '설정 저장을 확인하지 못해 테스트 발송을 중단했습니다. 일부 설정은 반영되었을 수 있습니다.',
        });
        return;
      }

      const res = await fetch('/api/notification/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform })
      });

      const data: unknown = await res.json();
      const result = data && typeof data === 'object' ? data : null;

      if (res.ok && result && 'status' in result && result.status === 'success') {
        setTestModal({
          isOpen: true,
          type: 'success',
          title: '발송 성공',
          content: `${platform} 테스트 발송 성공!`,
        });
      } else {
        setTestModal({
          isOpen: true,
          type: 'danger',
          title: '발송 실패',
          content: result && 'message' in result && typeof result.message === 'string'
            ? `발송 실패: ${result.message}` : '알림을 발송하지 못했습니다.',
        });
      }
    } catch {
      setTestModal({
        isOpen: true,
        type: 'danger',
        title: '발송 실패',
        content: '테스트 발송 중 오류가 발생했습니다.',
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title="설정"
        maxWidth="max-w-5xl"
        footer={
          <div className="flex justify-end gap-3 w-full">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-transparent text-gray-400 hover:text-white text-sm font-medium rounded-lg transition-colors border border-transparent hover:border-white/10"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-6 py-2 bg-[#5c5cff] hover:bg-[#4b4bff] text-white text-sm font-bold rounded-lg transition-colors min-w-[80px] shadow-lg shadow-blue-900/20"
            >
              {isSaving ? <i className="fas fa-spinner fa-spin"></i> : '저장'}
            </button>
          </div>
        }
      >
        <div className="flex flex-col md:flex-row gap-6 md:gap-10 h-full md:min-h-[500px] text-gray-300">
          {/* Sidebar (Menu) */}
          <div className="w-full md:w-48 flex-shrink-0 flex md:flex-col gap-2 md:gap-1 overflow-x-auto md:overflow-visible pb-2 md:pb-0 no-scrollbar">
            <div className="hidden md:block text-xs font-bold text-gray-500 px-3 mb-2 uppercase tracking-wider">계정</div>
            <button
              onClick={() => setActiveTab('profile')}
              className={`flex-none md:w-full text-left px-4 md:px-3 py-2 rounded-full md:rounded-[6px] text-sm md:text-[15px] font-medium transition-all whitespace-nowrap ${activeTab === 'profile' ? 'bg-[#3b3b40] text-white' : 'bg-white/5 md:bg-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10 md:hover:bg-white/5'
                }`}
            >
              일반
            </button>

            {/* [INFRA-025] 아래 세 탭은 서버 .env 를 읽고 쓴다. 관리자에게만 보인다. */}
            {isAdmin && (
              <>
            <div className="hidden md:block h-4"></div>
            <div className="hidden md:block text-xs font-bold text-gray-500 px-3 mb-2 uppercase tracking-wider">설정</div>
            <button
              onClick={() => setActiveTab('api')}
              className={`flex-none md:w-full text-left px-4 md:px-3 py-2 rounded-full md:rounded-[6px] text-sm md:text-[15px] font-medium transition-all whitespace-nowrap ${activeTab === 'api' ? 'bg-[#3b3b40] text-white' : 'bg-white/5 md:bg-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10 md:hover:bg-white/5'
                }`}
            >
              API & 기능
            </button>
            <button
              onClick={() => setActiveTab('notification')}
              className={`flex-none md:w-full text-left px-4 md:px-3 py-2 rounded-full md:rounded-[6px] text-sm md:text-[15px] font-medium transition-all whitespace-nowrap ${activeTab === 'notification' ? 'bg-[#3b3b40] text-white' : 'bg-white/5 md:bg-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10 md:hover:bg-white/5'
                }`}
            >
              알림 센터
            </button>
            <button
              onClick={() => setActiveTab('system')}
              className={`flex-none md:w-full text-left px-4 md:px-3 py-2 rounded-full md:rounded-[6px] text-sm md:text-[15px] font-medium transition-all whitespace-nowrap ${activeTab === 'system' ? 'bg-[#3b3b40] text-white' : 'bg-white/5 md:bg-transparent text-gray-400 hover:text-gray-200 hover:bg-white/10 md:hover:bg-white/5'
                }`}
            >
              시스템
            </button>
              </>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 max-w-2xl pt-0">
            {activeTab === 'profile' && (
              <div className="space-y-10">
                <section>
                  <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                    프로필
                    {isAdmin && (
                      <span className="text-[10px] font-bold bg-rose-500/20 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/30">
                        ADMIN
                      </span>
                    )}
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-4">
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">이름</label>
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                        placeholder="표시될 이름을 입력하세요"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">이메일</label>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                        placeholder="이메일 주소를 입력하세요"
                      />
                    </div>

                    {/* Quota Display for General Settings */}
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">
                        {isAdmin ? '관리자 사용 권한' : '무료 사용량 상태'}
                      </label>
                      <div className="bg-[#18181b] border border-white/10 rounded-lg p-3">
                        {isAdmin ? (
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-rose-400 font-bold">Admin</span>
                            <span className="text-gray-300">· 무제한 사용 가능</span>
                          </div>
                        ) : quota ? (
                          <div className="w-full">
                            <div className="flex justify-between text-xs text-blue-400 mb-1.5">
                              <span>사용량: {quota.usage} / {quota.limit}회</span>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-white">{quota.remaining}회 남음</span>
                                <button
                                  onClick={async (e) => {
                                    e.preventDefault();
                                    try {
                                      // 신원은 서버가 세션에서 정한다. 바디로 넘기던
                                      // email 과 session_id 는 아무나 지어낼 수 있었다.
                                      const res = await fetch('/api/kr/user/quota/recharge', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' }
                                      });
                                      const data = await res.json();
                                      if (res.ok) {
                                        setQuota(data);
                                        setTestModal({ isOpen: true, type: 'success', title: '충전 완료', content: data.message });
                                      } else {
                                        // 하루 1회 제한(429)과 로그인 필요(401)를 알린다.
                                        setTestModal({
                                          isOpen: true,
                                          type: 'danger',
                                          title: '충전할 수 없습니다',
                                          content: data.message || data.error || '잠시 후 다시 시도해 주세요.'
                                        });
                                      }
                                    } catch (e) { console.error(e); }
                                  }}
                                  className="w-5 h-5 flex items-center justify-center bg-blue-500 hover:bg-blue-400 rounded text-white text-xs font-bold transition-colors"
                                  title="5회 충전 (하루 1회)"
                                >
                                  +
                                </button>
                              </div>
                            </div>
                            <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-500 ${quota.remaining > 3 ? 'bg-blue-500' : 'bg-red-500'}`}
                                style={{ width: `${(quota.usage / quota.limit) * 100}%` }}
                              ></div>
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-blue-400">
                            ✨ 무료 10회 AI 사용 가능
                          </div>
                        )}
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">직무 / 역할</label>
                      <div className="space-y-2">
                        <div className="relative">
                          <select
                            value={role === '직접 입력' || !['엔지니어링', '리서치', '디자인', '트레이딩', '학생'].includes(role) ? '직접 입력' : role}
                            onChange={(e) => {
                              const val = e.target.value;
                              if (val === '직접 입력') {
                                setRole('직접 입력'); // Placeholder for custom input
                              } else {
                                setRole(val);
                                setIsCustomRole(false);
                              }
                            }}
                            className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white appearance-none focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                          >
                            <option>엔지니어링</option>
                            <option>리서치</option>
                            <option>디자인</option>
                            <option>트레이딩</option>
                            <option>학생</option>
                            <option>직접 입력</option>
                          </select>
                          <i className="fas fa-chevron-down absolute right-4 top-3.5 text-xs text-gray-500 pointer-events-none"></i>
                        </div>

                        {(role === '직접 입력' || isCustomRole) && (
                          <input
                            type="text"
                            value={role === '직접 입력' ? '' : role}
                            onChange={(e) => {
                              setRole(e.target.value);
                              setIsCustomRole(true);
                            }}
                            className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors animate-fadeIn"
                            placeholder="직무를 직접 입력하세요"
                            autoFocus
                          />
                        )}
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-2">구글 계정</h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                    {!isGoogleLoggedIn ? (
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                          <div className="text-sm font-medium text-white mb-1">계정 연동</div>
                          <div className="text-xs text-gray-400 break-keep leading-relaxed">
                            구글 계정으로 로그인하여 설정을 동기화하세요.
                            <div className="mt-1">
                              <span className="text-blue-400 font-bold block break-keep">(무료 10회 AI 사용 가능)</span>
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={handleGoogleLogin}
                          className="w-full md:w-auto px-5 py-2.5 bg-white hover:bg-gray-100 text-gray-900 text-sm font-bold rounded-xl transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 flex items-center justify-center gap-3 flex-shrink-0"
                        >
                          <img src="https://www.google.com/favicon.ico" alt="G" className="w-4 h-4" />
                          <span>Google 계정으로 계속하기</span>
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                            {googleUserInfo?.name?.[0] || "U"}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <div className="text-base font-bold text-white">{googleUserInfo?.name}</div>
                              {isAdmin && (
                                <span className="text-[10px] font-bold bg-rose-500/20 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/30">
                                  ADMIN
                                </span>
                              )}
                            </div>
                            <div className="text-sm text-gray-400">{googleUserInfo?.email}</div>
                            {isAdmin ? (
                              <div className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] font-semibold text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded">
                                <i className="fas fa-infinity text-[10px]"></i>
                                <span>Admin · 무제한</span>
                              </div>
                            ) : quota && (
                              <div className="mt-1.5 w-full max-w-[200px]">
                                <div className="text-[11px] text-blue-400 flex justify-between mb-1">
                                  <span>무료 사용량</span>
                                  <span className="font-bold text-white">{quota.usage} / {quota.limit}회</span>
                                </div>
                                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all duration-500 ${quota.remaining > 3 ? 'bg-blue-500' : 'bg-red-500'}`}
                                    style={{ width: `${(quota.usage / quota.limit) * 100}%` }}
                                  ></div>
                                </div>
                                <div className="text-[10px] text-gray-500 mt-0.5 text-right">
                                  {quota.remaining}회 남았습니다.
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 self-end md:self-auto">
                          <button
                            onClick={handleGoogleLogout}
                            className="px-4 py-2 border border-white/10 bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white rounded-lg text-xs transition-colors font-medium h-9"
                          >
                            로그아웃
                          </button>
                          <button
                            onClick={handleResetData}
                            className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/20 rounded-lg text-xs transition-colors font-medium h-9 whitespace-nowrap"
                          >
                            계정 삭제
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-2">관심 종목</h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-4">
                    <div className="flex flex-col md:flex-row gap-2">
                      <input
                        type="text"
                        value={newStock}
                        onChange={(e) => setNewStock(e.target.value)}
                        onKeyPress={handleKeyPress}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                        placeholder="종목명/코드 (예: 삼성전자)"
                      />
                      <button
                        onClick={handleAddStock}
                        className="w-full md:w-auto px-4 py-2 bg-[#5c5cff] hover:bg-[#4b4bff] text-white text-sm font-bold rounded-lg transition-colors flex-shrink-0"
                      >
                        추가
                      </button>
                    </div>

                    {watchlist.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {watchlist.map((stock) => (
                          <span
                            key={stock}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#18181b] border border-white/10 rounded-full text-sm text-gray-200"
                          >
                            {stock}
                            <button
                              onClick={() => handleRemoveStock(stock)}
                              className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="text-xs text-gray-500 text-center py-2 break-keep leading-relaxed">
                        관심 종목을 추가하면 AI 챗봇이 해당 종목을 분석해드립니다.
                      </div>
                    )}
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-2">모양</h3>
                  <div className="grid grid-cols-3 gap-3">
                    {/* Theme Option: Dark */}
                    <button className="bg-[#27272a] border-2 border-[#5c5cff] rounded-xl p-3 text-left group relative overflow-hidden">
                      <div className="h-16 bg-[#18181b] rounded mb-2 border border-white/5 relative">
                        <div className="absolute top-2 left-2 w-8 h-2 bg-white/10 rounded-sm"></div>
                        <div className="absolute top-5 left-2 w-12 h-1.5 bg-white/5 rounded-sm"></div>
                        <div className="absolute bottom-2 right-2 w-3 h-3 rounded-full bg-[#5c5cff]"></div>
                      </div>
                      <div className="text-xs font-bold text-white text-center">다크</div>
                    </button>

                    {/* Theme Option: Light */}
                    <button className="bg-[#27272a] border border-white/5 hover:border-white/20 rounded-xl p-3 text-left group relative overflow-hidden opacity-60 grayscale hover:grayscale-0 transition-all">
                      <div className="h-16 bg-[#e4e4e7] rounded mb-2 border border-white/5 relative">
                        <div className="absolute top-2 left-2 w-8 h-2 bg-black/10 rounded-sm"></div>
                        <div className="absolute top-5 left-2 w-12 h-1.5 bg-black/5 rounded-sm"></div>
                        <div className="absolute bottom-2 right-2 w-3 h-3 rounded-full bg-gray-400"></div>
                      </div>
                      <div className="text-xs font-bold text-gray-400 text-center">라이트</div>
                    </button>

                    {/* Theme Option: Auto */}
                    <button className="bg-[#27272a] border border-white/5 hover:border-white/20 rounded-xl p-3 text-left group relative overflow-hidden opacity-60 grayscale hover:grayscale-0 transition-all">
                      <div className="h-16 flex rounded mb-2 border border-white/5 relative overflow-hidden">
                        <div className="w-1/2 bg-[#e4e4e7]"></div>
                        <div className="w-1/2 bg-[#18181b]"></div>
                      </div>
                      <div className="text-xs font-bold text-gray-400 text-center">자동</div>
                    </button>

                  </div>
                </section>
              </div>
            )}

            {activeTab === 'api' && isAdmin && (
              <div className="space-y-8">
                {isLoadingEnv && <div className="text-center text-gray-500 py-4"><i className="fas fa-spinner fa-spin"></i> 로딩 중...</div>}

                <section>
                  <h3 className="text-lg font-bold text-blue-400 mb-4 flex items-center gap-2">
                    <div className="w-2 h-6 bg-blue-500 rounded-sm"></div>
                    Gemini (Vertex AI)
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                    <div className="text-[12px] text-gray-300 leading-relaxed break-keep">
                      <i className="fas fa-shield-alt mr-1 text-blue-400"></i>
                      Gemini는 서버 측 <span className="font-bold text-blue-400">Vertex AI 서비스 계정 인증</span>으로 호출됩니다.
                      <div className="mt-2 text-[11px] text-gray-500">
                        사용자별 API Key 입력 기능은 Vertex AI 전환과 함께 제거되었습니다.
                        무료 사용량은 일반 탭에서 확인할 수 있습니다.
                      </div>
                    </div>
                  </div>
                </section>



                <section>
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <div className="w-2 h-6 bg-green-500 rounded-sm"></div>
                    OpenAI
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                    <div className="mb-4">
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">OPENAI_API_KEY</label>
                      <div className="relative">
                        <input
                          type="password"
                          {...apiKeyFieldProps(envVars['OPENAI_API_KEY'], 'sk-...')}
                          onChange={(e) => handleEnvChange('OPENAI_API_KEY', e.target.value)}
                          className="w-full bg-[#18181b] border border-white/10 rounded-lg pl-4 pr-10 py-2 text-white font-mono text-xs focus:outline-none focus:border-green-500 transition-colors"
                          autoComplete="new-password"
                          data-lpignore="true"
                        />
                        {envVars['OPENAI_API_KEY'] && (
                          <button
                            onClick={() => handleEnvChange('OPENAI_API_KEY', '')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-red-500 transition-colors"
                            title="API Key 삭제"
                          >
                            <i className="fas fa-trash-alt"></i>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <div className="w-2 h-6 bg-cyan-500 rounded-sm"></div>
                    Perplexity
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                    <div className="mb-4">
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">PERPLEXITY_API_KEY</label>
                      <div className="relative">
                        <input
                          type="password"
                          {...apiKeyFieldProps(envVars['PERPLEXITY_API_KEY'], 'pplx-...')}
                          onChange={(e) => handleEnvChange('PERPLEXITY_API_KEY', e.target.value)}
                          className="w-full bg-[#18181b] border border-white/10 rounded-lg pl-4 pr-10 py-2 text-white font-mono text-xs focus:outline-none focus:border-cyan-500 transition-colors"
                          autoComplete="new-password"
                          data-lpignore="true"
                        />
                        {envVars['PERPLEXITY_API_KEY'] && (
                          <button
                            onClick={() => handleEnvChange('PERPLEXITY_API_KEY', '')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-red-500 transition-colors"
                            title="API Key 삭제"
                          >
                            <i className="fas fa-trash-alt"></i>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {activeTab === 'notification' && isAdmin && (
              <div className="space-y-8">
                <section>
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <i className="fab fa-telegram text-blue-400"></i>
                    Telegram 알림
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-5">
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">TELEGRAM_BOT_TOKEN</label>
                      <input
                        type="password"
                        value={envVars['TELEGRAM_BOT_TOKEN'] || ''}
                        onChange={(e) => handleEnvChange('TELEGRAM_BOT_TOKEN', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-blue-400 transition-colors"
                        placeholder="bot123456:ABC-DEF..."
                      />
                      <div className="mt-2 text-[11px] text-gray-500">
                        @BotFather를 통해 생성한 봇 토큰을 입력하세요.
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">TELEGRAM_CHAT_ID</label>
                      <input
                        type="text"
                        value={envVars['TELEGRAM_CHAT_ID'] || ''}
                        onChange={(e) => handleEnvChange('TELEGRAM_CHAT_ID', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-blue-400 transition-colors"
                        placeholder="-1001234567890"
                      />
                      <div className="mt-2 text-[11px] text-gray-500">
                        알림을 받을 채널 또는 개인 채팅 ID입니다. ( https://api.telegram.org/bot[TOKEN]/getUpdates 로 확인)
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <button
                        onClick={() => handleTestNotification('telegram')}
                        disabled={isTesting}
                        className="px-3 py-1.5 bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 text-xs font-bold rounded-lg transition-colors flex items-center gap-2"
                      >
                        {isTesting ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-paper-plane"></i>}
                        테스트 발송
                      </button>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <i className="fab fa-discord text-indigo-400"></i>
                    Discord 알림
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                    <div className="mb-4">
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">DISCORD_WEBHOOK_URL</label>
                      <input
                        type="password"
                        value={envVars['DISCORD_WEBHOOK_URL'] || ''}
                        onChange={(e) => handleEnvChange('DISCORD_WEBHOOK_URL', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                        placeholder="https://discord.com/api/webhooks/..."
                      />
                      <div className="mt-2 text-[11px] text-gray-500">
                        디스코드 채널 설정 &gt; 연동 &gt; 웹후크에서 생성한 URL을 입력하세요.
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <button
                        onClick={() => handleTestNotification('discord')}
                        disabled={isTesting}
                        className="px-3 py-1.5 bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 text-xs font-bold rounded-lg transition-colors flex items-center gap-2"
                      >
                        {isTesting ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-paper-plane"></i>}
                        테스트 발송
                      </button>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <i className="fas fa-envelope text-orange-400"></i>
                    이메일 알림 (SMTP)
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-5">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold text-gray-500 mb-1.5">SMTP Host</label>
                        <input
                          type="text"
                          value={envVars['SMTP_HOST'] || ''}
                          onChange={(e) => handleEnvChange('SMTP_HOST', e.target.value)}
                          className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-orange-500 transition-colors"
                          placeholder="smtp.gmail.com"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-gray-500 mb-1.5">SMTP Port</label>
                        <input
                          type="text"
                          value={envVars['SMTP_PORT'] || ''}
                          onChange={(e) => handleEnvChange('SMTP_PORT', e.target.value)}
                          className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-orange-500 transition-colors"
                          placeholder="587"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">SMTP User (Email)</label>
                      <input
                        type="email"
                        value={envVars['SMTP_USER'] || ''}
                        onChange={(e) => handleEnvChange('SMTP_USER', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-orange-500 transition-colors"
                        placeholder="your-email@gmail.com"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">SMTP Password (App Password)</label>
                      <input
                        type="password"
                        value={envVars['SMTP_PASSWORD'] || ''}
                        onChange={(e) => handleEnvChange('SMTP_PASSWORD', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-orange-500 transition-colors"
                        placeholder="abcd efgh ijkl mnop"
                      />
                      <div className="mt-2 text-[11px] text-gray-500">
                        Gmail의 경우, 2단계 인증 설정 후 '앱 비밀번호'를 생성하여 입력해야 합니다. (공용 비밀번호 절대 불가)
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">수신 이메일 (콤마로 구분)</label>
                      <input
                        type="text"
                        value={envVars['EMAIL_RECIPIENTS'] || ''}
                        onChange={(e) => handleEnvChange('EMAIL_RECIPIENTS', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-orange-500 transition-colors"
                        placeholder="me@example.com, boss@example.com"
                      />
                    </div>

                    <div className="flex justify-end">
                      <button
                        onClick={() => handleTestNotification('email')}
                        disabled={isTesting}
                        className="px-3 py-1.5 bg-orange-500/20 text-orange-400 hover:bg-orange-500/30 text-xs font-bold rounded-lg transition-colors flex items-center gap-2"
                      >
                        {isTesting ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-paper-plane"></i>}
                        테스트 발송
                      </button>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {activeTab === 'system' && isAdmin && (
              <div className="space-y-8">
                <section>
                  <h3 className="text-lg font-bold text-white mb-4">AI 모델 설정</h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-5">
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-2">기본 AI 공급자</label>
                      <div className="grid grid-cols-3 gap-3">
                        <button
                          onClick={() => handleEnvChange('AI_PROVIDER', 'gemini')}
                          className={`flex flex-col items-center justify-center p-4 rounded-lg border transition-all ${(envVars['AI_PROVIDER'] || 'gemini') === 'gemini'
                            ? 'bg-blue-500/10 border-blue-500 text-blue-400'
                            : 'bg-[#18181b] border-white/10 text-gray-400 hover:bg-white/5'
                            }`}
                        >
                          <i className="fas fa-robot text-xl mb-2"></i>
                          <span className="text-sm font-bold">Google Gemini</span>
                        </button>

                        <button
                          onClick={() => handleEnvChange('AI_PROVIDER', 'openai')}
                          className={`flex flex-col items-center justify-center p-4 rounded-lg border transition-all ${envVars['AI_PROVIDER'] === 'openai'
                            ? 'bg-green-500/10 border-green-500 text-green-400'
                            : 'bg-[#18181b] border-white/10 text-gray-400 hover:bg-white/5'
                            }`}
                        >
                          <i className="fas fa-brain text-xl mb-2"></i>
                          <span className="text-sm font-bold">OpenAI GPT</span>
                        </button>

                        <button
                          onClick={() => handleEnvChange('AI_PROVIDER', 'anthropic')}
                          className={`flex flex-col items-center justify-center p-4 rounded-lg border transition-all ${envVars['AI_PROVIDER'] === 'anthropic'
                            ? 'bg-purple-500/10 border-purple-500 text-purple-400'
                            : 'bg-[#18181b] border-white/10 text-gray-400 hover:bg-white/5'
                            }`}
                        >
                          <i className="fas fa-magic text-xl mb-2"></i>
                          <span className="text-sm font-bold">Claude 3.5</span>
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">시스템 프롬프트 / 페르소나</label>
                      <textarea
                        value={persona}
                        onChange={(e) => setPersona(e.target.value)}
                        rows={6}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white resize-none focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                        placeholder="AI에게 부여할 전역 페르소나를 입력하세요..."
                      />
                      <div className="mt-2 text-[11px] text-gray-500">
                        <i className="fas fa-info-circle mr-1"></i>
                        AI의 말투나 역할을 정의합니다. 예: "너는 친절한 주식 전문가야." (설정 시 즉시 적용됩니다)
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-white mb-4">검색 엔진</h3>
                  <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">Google Custom Search Engine ID</label>
                      <input
                        type="text"
                        value={envVars['GOOGLE_SEARCH_ENGINE_ID'] || ''}
                        onChange={(e) => handleEnvChange('GOOGLE_SEARCH_ENGINE_ID', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-lg font-bold text-red-500 mb-4 flex items-center gap-2">
                    <i className="fas fa-exclamation-triangle"></i>
                    데이터 관리 (Danger Zone)
                  </h3>
                  <div className="bg-[#27272a] rounded-xl border border-red-500/20 p-5">
                    <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                      <div>
                        <div className="text-sm font-bold text-white mb-1">모든 설정 초기화</div>
                        <div className="text-xs text-gray-500 break-keep leading-relaxed">
                          저장된 API Key, 구글 로그인 정보, 이메일 설정 등 모든 민감 정보를 영구적으로 삭제하고 로그아웃합니다.
                        </div>
                      </div>
                      <button
                        onClick={handleResetData}
                        className="w-full md:w-auto px-5 py-2.5 bg-red-500/10 text-red-500 text-sm font-bold rounded-xl hover:bg-red-500 hover:text-white transition-all border border-red-500/20 shadow-lg hover:shadow-red-500/20 whitespace-nowrap flex-shrink-0"
                      >
                        초기화 및 삭제
                      </button>
                    </div>
                  </div>
                </section>
              </div>
            )}
          </div>
        </div >
      </Modal >
      <Modal
        isOpen={testModal.isOpen}
        onClose={() => setTestModal(prev => ({ ...prev, isOpen: false }))}
        title={testModal.title}
        type={testModal.type}
      >
        {testModal.content}
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={isDeleteConfirmOpen}
        onClose={() => setIsDeleteConfirmOpen(false)}
        title="계정 삭제 확인"
        type="danger"
        footer={
          <div className="flex justify-end gap-3 w-full">
            <button
              onClick={() => setIsDeleteConfirmOpen(false)}
              className="px-4 py-2 bg-transparent text-gray-400 hover:text-white text-sm font-medium rounded-lg transition-colors border border-transparent hover:border-white/10"
            >
              취소
            </button>
            <button
              onClick={performResetData}
              className="px-6 py-2 bg-red-500 hover:bg-red-600 text-white text-sm font-bold rounded-lg transition-colors shadow-lg shadow-red-900/20"
            >
              삭제 (복구 불가)
            </button>
          </div>
        }
      >
        <div className="text-gray-300">
          <p className="mb-2 font-bold text-white">정말로 모든 설정을 초기화하고 계정을 삭제하시겠습니까?</p>
          <p className="text-sm text-gray-400">
            이 작업은 되돌릴 수 없습니다.<br />
            저장된 API Key, 사용자 설정, 쿼터 정보 등 모든 데이터가 영구적으로 삭제됩니다.
          </p>
        </div>
      </Modal>
    </>
  );
}
