'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

export default function Sidebar() {
  const pathname = usePathname();
  const [isKrExpanded, setIsKrExpanded] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [profile, setProfile] = useState({ name: 'User', email: 'user@example.com', persona: '' });

  const [quota, setQuota] = useState<{ usage: number, limit: number, remaining: number } | null>(null);
  const [hasApiKey, setHasApiKey] = useState(false);

  useEffect(() => {
    // Check for API Key in localStorage
    const checkApiKey = () => {
      const key = localStorage.getItem('GOOGLE_API_KEY');
      setHasApiKey(!!key);
    };
    checkApiKey();

    // Listen for storage changes (in case Settings updates it)
    window.addEventListener('storage', checkApiKey);

    // Also check periodically or on window focus
    const interval = setInterval(checkApiKey, 2000);

    const savedProfile = localStorage.getItem('user_profile');
    if (savedProfile) {
      try {
        const parsed = JSON.parse(savedProfile);
        setProfile(parsed);
      } catch (e) {
        console.error("Failed to parse user profile from localStorage", e);
      }
    }

    // Custom event listener for Header button
    const handleOpenSettings = () => setIsSettingsOpen(true);
    window.addEventListener('open-settings', handleOpenSettings);

    return () => {
      window.removeEventListener('open-settings', handleOpenSettings);
    };
  }, []);

  // Fetch quota when profile email is available
  useEffect(() => {
    if (profile.email && profile.email !== 'user@example.com') {
      fetch(`/api/kr/user/quota?email=${profile.email}`)
        .then(res => res.json())
        .then(data => setQuota(data))
        .catch(e => console.error(e));
    }
  }, [profile.email, isSettingsOpen]); // Update when settings close too

  const isActive = (path: string) => pathname === path;
  const isGroupActive = (prefix: string) => pathname.startsWith(prefix);

  const handleSaveSettings = async (name: string, email: string, persona: string) => {
    const newProfile = { ...profile, name, email, persona };
    setProfile(newProfile);
    localStorage.setItem('user_profile', JSON.stringify(newProfile));
    // Dispatch event for other components to update
    window.dispatchEvent(new Event('user-profile-updated'));
  };

  return (
    <>
      <aside className="w-64 border-r border-white/10 bg-[#1c1c1e] flex flex-col h-screen fixed left-0 top-0 z-50">
        {/* Logo */}
        <Link href="/" className="p-6 flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold">
            M
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
            마켓플로우
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
                  <div className="text-sm font-bold text-white mb-0.5">{profile.name}</div>
                  <div className="text-xs text-gray-400">{profile.email}</div>
                  {quota && (
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
                      alert("로그아웃 되었습니다.");
                      setIsUserMenuOpen(false);
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

          {/* Quota Display above Profile */}
          {(hasApiKey || quota) && (
            <div className="mb-2 px-3">
              {hasApiKey ? (
                <div className="text-[10px] font-bold text-center text-purple-400 bg-purple-500/10 border border-purple-500/20 rounded py-1">
                  ✨ API Key 사용 중 (무제한)
                </div>
              ) : quota && (
                <div className="bg-white/5 border border-white/5 rounded-lg p-2">
                  <div className="flex justify-between items-center text-[10px] text-gray-400 mb-1">
                    <span>무료 사용량</span>
                    <span className={`font-bold ${quota.remaining > 3 ? 'text-blue-400' : 'text-red-400'}`}>
                      {quota.remaining}회 남음
                    </span>
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
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-blue-500 flex items-center justify-center text-xs font-bold text-white">
              {profile.name[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">{profile.name}</div>
              <div className="text-xs text-gray-500 truncate flex items-center gap-1.5">
                {hasApiKey ? (
                  <span className="text-gray-500 text-[11px]">Personal Pro Plan</span>
                ) : quota ? (
                  <span className="text-gray-500 text-[11px]">Free Tier Plan</span>
                ) : (
                  <span className="text-gray-500 text-[11px]">로그인 필요 (무료 10회)</span>
                )}
              </div>
            </div>
            <i className={`fas fa-chevron-${isUserMenuOpen ? 'down' : 'up'} text-gray-500 text-xs`}></i>
          </button>

          {/* Issues Button (from screenshot) */}
          <button className="mt-3 w-full flex items-center justify-between px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-full text-xs font-medium transition-colors border border-rose-500/20">
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-rose-500 text-white flex items-center justify-center text-[10px]">N</span>
              <span>5 Issues</span>
            </div>
            <i className="fas fa-times text-[10px] opacity-50 hover:opacity-100"></i>
          </button>
        </div>
      </aside>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        profile={profile}
        onSave={handleSaveSettings}
      />
    </>
  );
}

import SettingsModal from './SettingsModal';
