'use client';

import { useState, useEffect } from 'react';
import Modal from './Modal';
import { useRouter } from 'next/navigation';
import { useSession, signIn, signOut } from "next-auth/react";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  profile: { name: string; email: string; persona: string };
  onSave: (name: string, email: string, persona: string) => Promise<void>;
}

type Tab = 'profile' | 'api' | 'system' | 'notification';

export default function SettingsModal({ isOpen, onClose, profile, onSave }: SettingsModalProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>('profile');
  const [name, setName] = useState(profile.name);
  const [email, setEmail] = useState(profile.email || 'user@example.com');
  const [persona, setPersona] = useState(profile.persona);
  const [isSaving, setIsSaving] = useState(false);
  const [envVars, setEnvVars] = useState<Record<string, string>>({});
  const [isLoadingEnv, setIsLoadingEnv] = useState(false);

  // Google Login State
  const [isGoogleLoggedIn, setIsGoogleLoggedIn] = useState(false);
  const [googleUserInfo, setGoogleUserInfo] = useState<{ name: string, email: string } | null>(null);

  // Watchlist State
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [newStock, setNewStock] = useState('');

  useEffect(() => {
    if (isOpen) {
      setName(profile.name);
      setEmail(profile.email || 'user@example.com');
      setPersona(profile.persona);

      fetchEnvVars();
      // Load watchlist from localStorage
      const savedWatchlist = localStorage.getItem('watchlist');
      if (savedWatchlist) {
        try {
          setWatchlist(JSON.parse(savedWatchlist));
        } catch {
          setWatchlist([]);
        }
      }
    }
  }, [isOpen, profile]);

  const fetchEnvVars = async () => {
    setIsLoadingEnv(true);
    try {
      const res = await fetch('/api/system/env');
      if (res.ok) {
        const data = await res.json();
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

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // 1. Save Profile
      await onSave(name, email, persona);

      // 2. Save Env Vars
      const res = await fetch('/api/system/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(envVars)
      });

      if (!res.ok) throw new Error("Failed to save env vars");

      // 3. Save Watchlist to localStorage
      localStorage.setItem('watchlist', JSON.stringify(watchlist));

    } catch (error) {
      console.error("Save error:", error);
      alert("설정 저장 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
      onClose();
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
  const { data: session, status } = useSession();

  useEffect(() => {
    if (status === 'authenticated' && session?.user) {
      setIsGoogleLoggedIn(true);
      setGoogleUserInfo({
        name: session.user.name || "User",
        email: session.user.email || ""
      });
      // 프로필 자동 동기화 (옵션)
      if (!name) setName(session.user.name || "");
      if (!email || email === 'user@example.com') setEmail(session.user.email || "");
    } else {
      setIsGoogleLoggedIn(false);
      setGoogleUserInfo(null);
    }
  }, [status, session]);

  const handleGoogleLogin = () => {
    // Google Login via NextAuth
    signIn('google');
  };

  const handleGoogleLogout = () => {
    signOut();
  };

  // Google API Key handling in localStorage (Client Only)
  useEffect(() => {
    if (isOpen) {
      const storedKey = localStorage.getItem('X-Gemini-Key');
      if (storedKey) {
        handleEnvChange('GOOGLE_API_KEY', storedKey); // UI 상에 표시 (보안 주의: 마스킹 가능하면 좋음)
      }
    }
  }, [isOpen]);

  const saveLocalApiKey = (key: string) => {
    if (key) {
      localStorage.setItem('X-Gemini-Key', key);
    } else {
      localStorage.removeItem('X-Gemini-Key');
    }
  };

  // Override handleEnvChange for GOOGLE_API_KEY to save locally too
  const handleEnvChangeWrapped = (key: string, value: string) => {
    handleEnvChange(key, value);
    if (key === 'GOOGLE_API_KEY') {
      saveLocalApiKey(value);
    }
  };

  return (
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
      <div className="flex gap-10 min-h-[600px] text-gray-300">
        {/* Sidebar */}
        <div className="w-48 flex-shrink-0 space-y-1">
          <div className="text-xs font-bold text-gray-500 px-3 mb-2 uppercase tracking-wider">계정</div>
          <button
            onClick={() => setActiveTab('profile')}
            className={`w-full text-left px-3 py-2 rounded-[6px] text-[15px] font-medium transition-all ${activeTab === 'profile' ? 'bg-[#3b3b40] text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
          >
            일반
          </button>

          <div className="h-4"></div>
          <div className="text-xs font-bold text-gray-500 px-3 mb-2 uppercase tracking-wider">설정</div>
          <button
            onClick={() => setActiveTab('api')}
            className={`w-full text-left px-3 py-2 rounded-[6px] text-[15px] font-medium transition-all ${activeTab === 'api' ? 'bg-[#3b3b40] text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
          >
            API & 기능
          </button>
          <button
            onClick={() => setActiveTab('notification')}
            className={`w-full text-left px-3 py-2 rounded-[6px] text-[15px] font-medium transition-all ${activeTab === 'notification' ? 'bg-[#3b3b40] text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
          >
            알림 센터
          </button>
          <button
            onClick={() => setActiveTab('system')}
            className={`w-full text-left px-3 py-2 rounded-[6px] text-[15px] font-medium transition-all ${activeTab === 'system' ? 'bg-[#3b3b40] text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`}
          >
            시스템
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 max-w-2xl pt-1">
          {activeTab === 'profile' && (
            <div className="space-y-10">
              <section>
                <h3 className="text-lg font-bold text-white mb-2">프로필</h3>
                <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">이름</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                      placeholder="표시될 이름을 입력하세요"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">이메일</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                      placeholder="이메일 주소를 입력하세요"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">직무 / 역할</label>
                    <div className="relative">
                      <select className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white appearance-none focus:outline-none focus:border-[#5c5cff]/50 transition-colors">
                        <option>엔지니어링</option>
                        <option>리서치</option>
                        <option>디자인</option>
                        <option>기타</option>
                      </select>
                      <i className="fas fa-chevron-down absolute right-4 top-3.5 text-xs text-gray-500 pointer-events-none"></i>
                    </div>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-lg font-bold text-white mb-2">구글 계정</h3>
                <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                  {!isGoogleLoggedIn ? (
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-white mb-1">계정 연동</div>
                        <div className="text-xs text-gray-500">구글 계정으로 로그인하여 설정을 동기화하고 개인화 서비스를 이용하세요.</div>
                      </div>
                      <button
                        onClick={handleGoogleLogin}
                        className="px-4 py-2 bg-white text-black text-sm font-bold rounded-lg hover:bg-gray-100 transition-colors flex items-center gap-2"
                      >
                        <img src="https://www.google.com/favicon.ico" alt="G" className="w-4 h-4" />
                        로그인
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-sm">
                          {googleUserInfo?.name?.[0] || "U"}
                        </div>
                        <div>
                          <div className="text-sm font-bold text-white">{googleUserInfo?.name}</div>
                          <div className="text-xs text-gray-500">{googleUserInfo?.email}</div>
                        </div>
                      </div>
                      <button
                        onClick={handleGoogleLogout}
                        className="px-3 py-1.5 border border-white/10 bg-transparent text-gray-400 hover:text-white rounded-md text-xs transition-colors"
                      >
                        연동 해제
                      </button>
                    </div>
                  )}
                </div>
              </section>

              <section>
                <h3 className="text-lg font-bold text-white mb-2">관심 종목</h3>
                <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-4">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newStock}
                      onChange={(e) => setNewStock(e.target.value)}
                      onKeyPress={handleKeyPress}
                      className="flex-1 bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-[#5c5cff]/50 transition-colors"
                      placeholder="종목명 또는 코드 입력 (예: 삼성전자, 005930)"
                    />
                    <button
                      onClick={handleAddStock}
                      className="px-4 py-2 bg-[#5c5cff] hover:bg-[#4b4bff] text-white text-sm font-bold rounded-lg transition-colors"
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
                    <div className="text-sm text-gray-500 text-center py-2">
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

          {activeTab === 'api' && (
            <div className="space-y-8">
              {isLoadingEnv && <div className="text-center text-gray-500 py-4"><i className="fas fa-spinner fa-spin"></i> 로딩 중...</div>}

              <section>
                <h3 className="text-lg font-bold text-blue-400 mb-4 flex items-center gap-2">
                  <div className="w-2 h-6 bg-blue-500 rounded-sm"></div>
                  Google Gemini / AI
                </h3>
                <div className="bg-[#27272a] rounded-xl border border-white/5 p-5 space-y-5">
                  <div>
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">GOOGLE_API_KEY (Gemini)</label>
                    <input
                      type="password"
                      value={envVars['GOOGLE_API_KEY'] || ''}
                      onChange={(e) => handleEnvChangeWrapped('GOOGLE_API_KEY', e.target.value)}
                      className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-blue-500 transition-colors"
                      placeholder="sk-..."
                    />
                    <div className="mt-2 text-[11px] text-gray-500 text-yellow-500">
                      <i className="fas fa-lock mr-1"></i>
                      이 키는 브라우저(Local Storage)에만 저장되며 서버로 전송되지 않습니다. (AI 분석 요청 시에만 헤더에 포함됨)
                    </div>
                  </div>

                  <div className="pt-4 border-t border-white/5 grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">GOOGLE CLIENT ID</label>
                      <input
                        type="text"
                        value={envVars['GOOGLE_CLIENT_ID'] || ''}
                        onChange={(e) => handleEnvChange('GOOGLE_CLIENT_ID', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-blue-500 transition-colors"
                        placeholder="Client ID"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-gray-500 mb-1.5">GOOGLE CLIENT SECRET</label>
                      <input
                        type="password"
                        value={envVars['GOOGLE_CLIENT_SECRET'] || ''}
                        onChange={(e) => handleEnvChange('GOOGLE_CLIENT_SECRET', e.target.value)}
                        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-blue-500 transition-colors"
                        placeholder="Client Secret"
                      />
                    </div>
                  </div>
                  <div className="text-[11px] text-gray-500">
                    Google Cloud Console에서 OAuth 2.0 자격 증명을 생성하여 입력하세요. (로그인용)
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
                    <input
                      type="password"
                      value={envVars['OPENAI_API_KEY'] || ''}
                      onChange={(e) => handleEnvChange('OPENAI_API_KEY', e.target.value)}
                      className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-green-500 transition-colors"
                      placeholder="sk-..."
                    />
                  </div>
                </div>
              </section>

              <section>
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <div className="w-2 h-6 bg-purple-500 rounded-sm"></div>
                  Anthropic
                </h3>
                <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                  <div className="mb-4">
                    <label className="block text-xs font-bold text-gray-500 mb-1.5">ANTHROPIC_API_KEY</label>
                    <input
                      type="password"
                      value={envVars['ANTHROPIC_API_KEY'] || ''}
                      onChange={(e) => handleEnvChange('ANTHROPIC_API_KEY', e.target.value)}
                      className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-purple-500 transition-colors"
                      placeholder="sk-ant-..."
                    />
                  </div>
                </div>
              </section>
            </div>
          )}

          {activeTab === 'notification' && (
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
                </div>
              </section>

              <section>
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <i className="fab fa-discord text-indigo-400"></i>
                  Discord 알림
                </h3>
                <div className="bg-[#27272a] rounded-xl border border-white/5 p-5">
                  <div>
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
                </div>
              </section>
            </div>
          )}

          {activeTab === 'system' && (
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
                        <span className="text-sm font-bold">OpenAI GPT-4</span>
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
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
