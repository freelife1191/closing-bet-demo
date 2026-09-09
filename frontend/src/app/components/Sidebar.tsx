'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect, useCallback } from 'react';
import Modal from './Modal';
import PaperTradingModal from './PaperTradingModal';
import { useSession, signOut } from 'next-auth/react';
import { useAdmin } from '@/hooks/useAdmin';
import { getBrowserSessionId } from '@/lib/session';
import { DEFAULT_USER_PROFILE, normalizeUserProfile, resolveUserProfile, saveUserProfile, type UserProfile } from './chatHelpers';

export default function Sidebar() {
  const pathname = usePathname();
  const [isKrExpanded, setIsKrExpanded] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_USER_PROFILE);

  const [quota, setQuota] = useState<{ usage: number, limit: number, remaining: number } | null>(null);
  const [isPaperTradingOpen, setIsPaperTradingOpen] = useState(false);

  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    type: 'default' | 'success' | 'danger';
    title: string;
    content: string;
  }>({ isOpen: false, type: 'default', title: '', content: '' });

  // Mobile Sidebar State
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  // ADMIN 권한 체크
  const { isAdmin } = useAdmin();

  // 표시의 기준은 세션이다. 권한 판정(useAdmin)과 사용량 집계가 모두 세션 이메일을 쓰므로,
  // 사이드바만 localStorage 프로필을 보여 주면 어느 계정으로 로그인했는지 오해하게 된다.
  const { data: session, status } = useSession();
  const displayProfile = resolveUserProfile(
    profile,
    status === 'authenticated' ? session?.user : null,
  );
  const displayName = displayProfile.name;
  const displayEmail = displayProfile.email;

  // Close mobile sidebar on path change
  useEffect(() => {
    setIsMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    const handleSidebarToggle = () => setIsMobileOpen(prev => !prev);
    window.addEventListener('sidebar-toggle', handleSidebarToggle);

    const loadProfile = () => {
      const savedProfile = localStorage.getItem('user_profile');
      if (!savedProfile) {
        setProfile(DEFAULT_USER_PROFILE);
        return;
      }
      try {
        setProfile(normalizeUserProfile(JSON.parse(savedProfile)));
      } catch (e) {
        console.error("Profile parse error", e);
        setProfile(DEFAULT_USER_PROFILE);
      }
    };
    loadProfile();
    window.addEventListener('user-profile-updated', loadProfile);

    const handleOpenSettings = () => setIsSettingsOpen(true);
    window.addEventListener('open-settings', handleOpenSettings);

    return () => {
      window.removeEventListener('sidebar-toggle', handleSidebarToggle);
      window.removeEventListener('open-settings', handleOpenSettings);
      window.removeEventListener('user-profile-updated', loadProfile);
    };
  }, []);

  const refreshQuota = useCallback(() => {
    // 세션이 확정되기 전에는 어느 계정의 사용량인지 알 수 없다. 세션 쿠키가 붙기 전에
    // 조회하면 로그인한 사용자에게 익명 응답이 잠깐 표시된다.
    if (status === 'loading') return;

    // 신원은 서버가 정한다. 종전에는 쿼리 파라미터로 이메일을 넘겼는데, 그러면 URL 한
    // 줄로 남의 사용량을 조회할 수 있었다.
    fetch('/api/kr/user/quota')
      .then(res => res.json())
      .then(data => {
        setQuota(data);
      })
      .catch(e => console.error(e));
  }, [status]);

  useEffect(() => {
    refreshQuota();
  }, [refreshQuota, isSettingsOpen]); // Update when settings close or API key changes

  // [Fix] 챗봇 응답 후 quota 자동 갱신
  useEffect(() => {
    const handleQuotaUpdate = () => refreshQuota();
    window.addEventListener('quota-updated', handleQuotaUpdate);
    return () => window.removeEventListener('quota-updated', handleQuotaUpdate);
  }, [refreshQuota]);

  const isActive = (path: string) => pathname === path;
  const isGroupActive = (prefix: string) => pathname.startsWith(prefix);

  const handleSaveSettings = async (name: string, email: string, persona: string) => {
    await saveUserProfile(name, email, persona);
    setProfile({ name, email, persona });

    // [Log] Update Profile Event
    try {
      const sessionId = getBrowserSessionId();
      await fetch('/api/system/log-event', {
        method: 'POST',
        headers: {
          // 신원은 proxy.ts 가 세션에서 확정해 서명한다. X-User-Email 을 보내도 지워진다.
          'Content-Type': 'application/json',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify({
          action: 'PROFILE_UPDATE',
          details: { name, email, persona }
        })
      });
    } catch (e) { console.error("Log failed", e); }
  };

  return (
    <>
      {/* Mobile Sidebar Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[59] lg:hidden transition-opacity"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      <aside className={`w-64 border-r border-white/10 bg-[#1c1c1e] flex flex-col h-screen fixed left-0 top-0 z-[60] transition-transform duration-300 ${isMobileOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        {/* Logo */}
        <Link href="/" className="p-6 flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold">
            M
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
            스마트 머니 봇
          </span>
        </Link>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-2 space-y-1 overflow-y-auto custom-scrollbar">
          <div className="text-xs font-semibold text-gray-500 mb-2 px-2 mt-4">DASHBOARD</div>

          {/* KR Market Group */}
          <div>
            <button
              onClick={() => setIsKrExpanded(!isKrExpanded)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${isGroupActive('/dashboard/kr')
                ? 'text-white'
                : 'text-gray-400 hover:bg-white/5 hover:text-white'
                }`}
            >
              <div className="flex items-center gap-3">
                <i className="fas fa-chart-line w-5 text-center text-rose-400"></i>
                KR Market
              </div>
              <i className={`fas fa-chevron-down text-xs transition-transform ${isKrExpanded ? 'rotate-180' : ''}`}></i>
            </button>

            {isKrExpanded && (
              <div className="ml-4 mt-1 space-y-0.5 border-l border-white/10 pl-3">
                <Link
                  href="/dashboard/kr"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${isActive('/dashboard/kr')
                    ? 'text-blue-400 bg-blue-500/5'
                    : 'text-gray-500 hover:text-gray-300'
                    }`}
                >
                  ● Overview
                </Link>
                <Link
                  href="/dashboard/kr/vcp"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${isActive('/dashboard/kr/vcp')
                    ? 'text-rose-400 bg-rose-500/5'
                    : 'text-gray-500 hover:text-gray-300'
                    }`}
                >
                  ● VCP 시그널
                </Link>
                <Link
                  href="/dashboard/kr/closing-bet"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${isActive('/dashboard/kr/closing-bet')
                    ? 'text-purple-400 bg-purple-500/5'
                    : 'text-gray-500 hover:text-gray-300'
                    }`}
                >
                  ● 종가베팅
                </Link>
                <Link
                  href="/dashboard/kr/cumulative"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${isActive('/dashboard/kr/cumulative')
                    ? 'text-amber-400 bg-amber-500/5'
                    : 'text-gray-500 hover:text-gray-300'
                    }`}
                >
                  ● 누적 성과
                </Link>
                <Link
                  href="/chatbot"
                  className={`block px-3 py-2 rounded-lg text-sm transition-colors ${isActive('/chatbot')
                    ? 'text-green-400 bg-green-500/5'
                    : 'text-gray-500 hover:text-gray-300'
                    }`}
                >
                  ● AI 상담
                </Link>
              </div>
            )}
          </div>

          {/* 모의투자 버튼 */}
          <button
            onClick={() => setIsPaperTradingOpen(true)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors text-gray-400 hover:bg-white/5 hover:text-white"
          >
            <i className="fas fa-wallet w-5 text-center text-emerald-400"></i>
            모의투자
          </button>

          <Link
            href="/dashboard/data-status"
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${isActive('/dashboard/data-status')
              ? 'bg-blue-500/10 text-blue-400'
              : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
          >
            <i className="fas fa-database w-5 text-center"></i>
            데이터 상태
          </Link>
        </nav>

        {/* Footer / User */}
        <div className="p-4 border-t border-white/10 relative">
          {/* User Dropdown Menu */}
          {isUserMenuOpen && (
            <>
              <div className="fixed inset-0 z-40 bg-transparent" onClick={() => setIsUserMenuOpen(false)} />
              <div className="absolute bottom-full left-4 right-4 mb-2 bg-[#252529] border border-white/10 rounded-xl shadow-xl overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200">
                <div className="p-3 border-b border-white/5">
                  <div className="text-sm font-bold text-white mb-0.5">{displayName}</div>
                  <div className="text-xs text-gray-400">{displayEmail}</div>
                  {isAdmin ? (
                    <div className="text-[10px] text-rose-400 mt-1 font-medium bg-rose-500/10 px-1.5 py-0.5 rounded inline-block">
                      Admin · 무제한
                    </div>
                  ) : quota && (
                    <div className="text-[10px] text-blue-400 mt-1 font-medium bg-blue-500/10 px-1.5 py-0.5 rounded inline-block">
                      {quota.remaining}회 남음 (총 {quota.limit}회)
                    </div>
                  )}
                </div>
                <div className="p-1 space-y-0.5">
                  <button
                    onClick={() => {
                      setIsSettingsOpen(true);
                      setIsUserMenuOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors flex items-center justify-between group"
                  >
                    <div className="flex items-center gap-2">
                      <i className="fas fa-cog w-4 text-center text-gray-500 group-hover:text-white transition-colors"></i>
                      <span>설정</span>
                    </div>
                    <span className="text-[10px] text-gray-600 border border-gray-700 rounded px-1 group-hover:border-gray-500 bg-black/20">⌘,</span>
                  </button>
                  <button className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-white/5 rounded-lg transition-colors flex items-center gap-2 group">
                    <i className="fas fa-question-circle w-4 text-center text-gray-500 group-hover:text-white transition-colors"></i>
                    <span>도움말 & 지원</span>
                  </button>
                  <div className="h-px bg-white/5 mx-2 my-1"></div>
                  <button
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      signOut({ callbackUrl: '/' });
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors flex items-center gap-2"
                  >
                    <i className="fas fa-sign-out-alt w-4 text-center"></i>
                    <span>로그아웃</span>
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Quota Display above Profile (Admin은 무제한이라 숨김) */}
          {!isAdmin && quota && (
            <div className="mb-2 px-3">
              {(
                <div className="bg-white/5 border border-white/5 rounded-lg p-2">
                  <div className="flex justify-between items-center text-[10px] text-gray-400 mb-1">
                    <span>무료 사용량</span>
                    <div className="flex items-center gap-1.5">
                      <span className={`font-bold ${quota.remaining > 3 ? 'text-blue-400' : 'text-red-400'}`}>
                        {quota.remaining}회 남음
                      </span>
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            // 신원은 서버가 세션에서 정한다. 바디로 넘기던 email 과
                            // session_id 는 아무나 지어낼 수 있는 값이었다.
                            const res = await fetch('/api/kr/user/quota/recharge', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' }
                            });
                            const data = await res.json();
                            if (res.ok) {
                              setQuota(data);
                              setAlertModal({ isOpen: true, type: 'success', title: '충전 완료', content: data.message });
                            } else {
                              // 하루 1회 제한(429)과 로그인 필요(401)를 사용자에게 알린다.
                              // 종전에는 실패를 삼켜 버튼이 먹통인 것처럼 보였다.
                              setAlertModal({
                                isOpen: true,
                                type: 'danger',
                                title: '충전할 수 없습니다',
                                content: data.message || data.error || '잠시 후 다시 시도해 주세요.'
                              });
                            }
                          } catch (e) { console.error(e); }
                        }}
                        className="w-4 h-4 flex items-center justify-center bg-blue-500 hover:bg-blue-400 rounded text-white text-[9px] font-bold transition-colors"
                        title="5회 충전 (하루 1회)"
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${quota.remaining > 3 ? 'bg-blue-500' : 'bg-red-500'}`}
                      style={{ width: `${(quota.usage / quota.limit) * 100}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          )}

          <button
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className={`relative z-30 flex items-center gap-3 w-full px-3 py-2 rounded-lg hover:bg-white/5 text-left transition-colors ${isUserMenuOpen ? 'bg-white/5' : ''}`}
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-blue-500 flex items-center justify-center text-xs font-bold text-white relative">
              {displayName[0]}
              {isAdmin && (
                <div className="absolute -top-1 -right-1 w-3 h-3 bg-rose-500 border-2 border-[#1c1c1e] rounded-full" title="ADMIN"></div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <div className="text-sm font-medium text-white truncate">{displayName}</div>
                {isAdmin && (
                  <span className="text-[10px] font-bold bg-rose-500/20 text-rose-400 px-1 rounded border border-rose-500/30">
                    ADMIN
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-500 truncate flex items-center gap-1.5">
                {isAdmin ? (
                  <span className="text-rose-400 text-[11px] font-semibold">Admin · 무제한 사용</span>
                ) : quota ? (
                  <span className="text-gray-500 text-[11px]">Free Tier Plan</span>
                ) : (
                  <span className="text-gray-500 text-[11px]">Free Tier (무료 10회)</span>
                )}
              </div>
            </div>
            <i className={`fas fa-chevron-${isUserMenuOpen ? 'down' : 'up'} text-gray-500 text-xs`}></i>
          </button>


        </div>
      </aside>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        profile={profile}
        onSave={handleSaveSettings}
      />

      <PaperTradingModal
        isOpen={isPaperTradingOpen}
        onClose={() => setIsPaperTradingOpen(false)}
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
    </>
  );
}

import SettingsModal from './SettingsModal';
