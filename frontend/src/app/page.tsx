'use client';

import Link from 'next/link';
import { useState } from 'react';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<'vcp' | 'supply' | 'closing'>('closing');

  return (
    <div className="min-h-screen bg-[#0E1117] text-white flex flex-col font-sans selection:bg-rose-500/30">

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#0E1117]/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <i className="fas fa-chart-line text-white text-sm"></i>
            </div>
            <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
              KR Market Package
            </span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-400">
            <a href="#features" className="hover:text-white transition-colors">기능</a>
            <a href="#architecture" className="hover:text-white transition-colors">아키텍처</a>
            <a href="#ai-analysis" className="hover:text-white transition-colors">AI 분석</a>
          </div>
          <Link
            href="/dashboard/kr"
            className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-bold rounded-full transition-all border border-white/10"
          >
            Get Started
          </Link>
        </div>
      </nav>

      <main className="flex-1 pt-16">
        {/* Hero Section */}
        <section className="relative pt-20 pb-32 px-6 overflow-hidden">
          {/* Background Glow */}
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none"></div>
          <div className="absolute top-1/4 left-1/4 w-[400px] h-[400px] bg-rose-500/5 rounded-full blur-[80px] pointer-events-none"></div>

          <div className="max-w-4xl mx-auto text-center relative z-10">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 text-xs text-blue-400 font-bold mb-8">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              System Operational: v2.0 Released
            </div>

            <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-8 leading-tight">
              한국 주식 시장을 위한<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-rose-400">
                AI 기반 퀀트 분석 솔루션
              </span>
            </h1>

            <p className="text-xl text-gray-400 mb-12 max-w-2xl mx-auto leading-relaxed">
              VCP 패턴 인식, 기관/외국인 수급 추적, 그리고 <span className="text-indigo-400 font-semibold">Gemini & GPT Dual AI 엔진</span>이 결합된 올인원 주식 분석 패키지입니다.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/dashboard/kr"
                className="w-full sm:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2"
              >
                <i className="fas fa-terminal"></i>
                설치 가이드
              </Link>
              <Link
                href="/dashboard/kr"
                className="w-full sm:w-auto px-8 py-4 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2"
              >
                <i className="fas fa-search"></i>
                분석 엔진 살펴보기
              </Link>
            </div>

            <div className="mt-16 pt-8 border-t border-white/5 flex flex-wrap justify-center gap-8 md:gap-12 opacity-50 grayscale hover:grayscale-0 transition-all duration-500">
              <div className="flex items-center gap-2 text-sm font-semibold"><i className="fab fa-python text-xl"></i> Python</div>
              <div className="flex items-center gap-2 text-sm font-semibold"><i className="fab fa-react text-xl"></i> Next.js</div>
              <div className="flex items-center gap-2 text-sm font-semibold"><i className="fas fa-flask text-xl"></i> Flask</div>
              <div className="flex items-center gap-2 text-sm font-semibold"><i className="fas fa-brain text-xl"></i> Gemini</div>
              <div className="flex items-center gap-2 text-sm font-semibold"><i className="fas fa-robot text-xl"></i> Perplexity</div>
            </div>
          </div>
        </section>

        {/* System Architecture Section */}
        <section id="architecture" className="py-24 bg-black/20 border-y border-white/5">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">System Architecture</h2>
              <p className="text-gray-400">데이터 수집부터 AI 분석, 그리고 프론트엔드 시각화까지의 파이프라인</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
              {/* Connecting Lines (Desktop) */}
              <div className="hidden md:block absolute top-1/2 left-0 w-full h-px bg-gradient-to-r from-transparent via-indigo-500/30 to-transparent -translate-y-1/2 z-0"></div>

              {/* Backend Card */}
              <div className="relative z-10 p-8 rounded-3xl bg-[#0E1117] border border-white/10 hover:border-indigo-500/30 transition-all group">
                <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                  <i className="fas fa-server text-2xl text-indigo-400"></i>
                </div>
                <h3 className="text-xl font-bold text-center mb-2">Flask API Backend</h3>
                <p className="text-center text-xs text-gray-500 font-mono mb-6">Port: 5501</p>
                <ul className="space-y-3 text-sm text-gray-300">
                  <li className="flex items-center gap-2"><i className="fas fa-check text-green-500 text-xs"></i> Signals (/api/kr/signals)</li>
                  <li className="flex items-center gap-2"><i className="fas fa-check text-green-500 text-xs"></i> AI Analysis (/api/kr/ai)</li>
                  <li className="flex items-center gap-2"><i className="fas fa-check text-green-500 text-xs"></i> Market Gate</li>
                </ul>
              </div>

              {/* Analysis Engine Card (Center, Highlighted) */}
              <div className="relative z-10 p-8 rounded-3xl bg-[#1c1c1e] border border-indigo-500/50 shadow-2xl shadow-indigo-500/10 transform md:-translate-y-4">
                <div className="absolute top-0 center w-full flex justify-center -mt-3">
                  <span className="px-3 py-1 bg-indigo-500 text-[10px] font-bold rounded-full">CORE ENGINE</span>
                </div>
                <div className="w-16 h-16 rounded-2xl bg-indigo-500/20 flex items-center justify-center mx-auto mb-6">
                  <i className="fas fa-microchip text-2xl text-indigo-400"></i>
                </div>
                <h3 className="text-xl font-bold text-center mb-2">Analysis Engine</h3>
                <p className="text-center text-xs text-gray-400 font-mono mb-6">Python Core</p>

                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-xs font-bold text-amber-400 mb-2">Data Sources</div>
                    <div className="text-sm text-gray-300">pykrx, yfinance, FDR</div>
                  </div>
                  <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20">
                    <div className="text-xs font-bold text-indigo-400 mb-2">AI Models</div>
                    <div className="text-sm text-gray-300">Gemini + Perplexity</div>
                  </div>
                </div>
              </div>

              {/* Frontend Card */}
              <div className="relative z-10 p-8 rounded-3xl bg-[#0E1117] border border-white/10 hover:border-blue-500/30 transition-all group">
                <div className="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform">
                  <i className="fas fa-desktop text-2xl text-blue-400"></i>
                </div>
                <h3 className="text-xl font-bold text-center mb-2">Next.js Frontend</h3>
                <p className="text-center text-xs text-gray-500 font-mono mb-6">Port: 3500</p>
                <ul className="space-y-3 text-sm text-gray-300">
                  <li className="flex items-center gap-2"><i className="fas fa-columns text-blue-400 text-xs"></i> Dashboard UI</li>
                  <li className="flex items-center gap-2"><i className="fas fa-bolt text-blue-400 text-xs"></i> Real-time Signals</li>
                  <li className="flex items-center gap-2"><i className="fas fa-newspaper text-blue-400 text-xs"></i> News Feed</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Core Features Section */}
        <section id="features" className="py-24 px-6">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-16">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">Core Analysis Features</h2>
              <p className="text-gray-400">데이터와 알고리즘이 찾아내는 최적의 투자 기회</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* VCP Card */}
              <div className="p-8 rounded-3xl bg-[#13151A] border border-white/5 hover:border-rose-500/30 transition-all group hover:-translate-y-1">
                <div className="w-12 h-12 rounded-xl bg-rose-500/10 flex items-center justify-center mb-6 text-rose-500">
                  <i className="fas fa-compress-arrows-alt text-xl"></i>
                </div>
                <h3 className="text-xl font-bold mb-3">VCP 패턴 감지</h3>
                <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                  변동성 축소 패턴(Volatility Contraction Pattern)을 자동으로 탐지합니다.
                </p>
                <ul className="space-y-2 text-sm text-gray-300">
                  <li className="flex items-center gap-2"><span className="w-1 h-1 bg-rose-500 rounded-full"></span>수축 임계값: 0.7 (70%)</li>
                  <li className="flex items-center gap-2"><span className="w-1 h-1 bg-rose-500 rounded-full"></span>ATR 기반 변동성 점수</li>
                  <li className="flex items-center gap-2"><span className="w-1 h-1 bg-rose-500 rounded-full"></span>고가-저가 범위 축소 확인</li>
                </ul>
              </div>

              {/* Smart Money Card */}
              <div className="p-8 rounded-3xl bg-[#13151A] border border-white/5 hover:border-emerald-500/30 transition-all group hover:-translate-y-1">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-6 text-emerald-500">
                  <i className="fas fa-money-bill-wave text-xl"></i>
                </div>
                <h3 className="text-xl font-bold mb-3">수급 추적 (Smart Money)</h3>
                <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                  외국인과 기관의 매집 흐름을 100점 만점 기준으로 평가합니다.
                </p>
                <div className="space-y-2 text-sm bg-black/20 p-4 rounded-xl">
                  <div className="flex justify-between"><span className="text-gray-400">외인 순매매</span> <span className="text-emerald-400 font-bold">25점</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">기관 순매매</span> <span className="text-emerald-400 font-bold">20점</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">연속 매수일</span> <span className="text-emerald-400 font-bold">15점</span></div>
                </div>
              </div>

              {/* Closing Bet V2 Card */}
              <div className="p-8 rounded-3xl bg-[#13151A] border border-white/5 hover:border-purple-500/30 transition-all group hover:-translate-y-1">
                <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center mb-6 text-purple-500">
                  <i className="fas fa-hourglass-half text-xl"></i>
                </div>
                <h3 className="text-xl font-bold mb-3">종가베팅</h3>
                <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                  장 마감 전 최적의 매수 기회를 포착하는 18점 만점 시스템입니다.
                </p>
                <div className="flex gap-2 mb-4">
                  <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 text-xs font-bold rounded">S급: 15점+</span>
                  <span className="px-2 py-1 bg-gray-500/20 text-gray-400 text-xs font-bold rounded">A급: 12점+</span>
                </div>
                <p className="text-xs text-gray-500">거래대금 1조 이상 시 가산점 부여</p>
              </div>
            </div>
          </div>
        </section>

        {/* Dual AI Section & Market Gate */}
        <section id="ai-analysis" className="py-24 px-6 bg-[#0E1117] relative">
          <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Dual AI Analysis System (2/3) */}
            <div className="lg:col-span-2 p-1 rounded-3xl bg-gradient-to-r from-purple-500/20 via-indigo-500/20 to-blue-500/20 h-full">
              <div className="bg-[#13151A] rounded-[22px] p-8 md:p-12 h-full flex flex-col justify-between">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
                  <div>
                    <div className="w-12 h-12 rounded-xl bg-indigo-500 flex items-center justify-center mb-4">
                      <i className="fas fa-brain text-2xl text-white"></i>
                    </div>
                    <h2 className="text-3xl font-bold mb-2">Dual AI Analysis System</h2>
                    <p className="text-gray-400">최신 LLM 모델들의 상호 검증을 통한 신뢰도 높은 분석</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-3 py-1 bg-purple-500/20 text-purple-400 text-xs font-bold rounded-full border border-purple-500/30">DUAL ENGINE</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="p-6 rounded-2xl bg-[#1c1c1e] border border-indigo-500/20 hover:bg-[#252529] transition-colors">
                    <h3 className="text-lg font-bold text-indigo-400 mb-2 flex items-center gap-2">
                      <i className="fas fa-star"></i> Gemini (Main)
                    </h3>
                    <p className="text-sm text-gray-400 leading-relaxed">
                      뉴스 종합 분석, 호재 점수(0~3), 매매 추천(Buy/Hold/Sell) 및 신뢰도 산출. 최신 시장 데이터를 실시간으로 해석합니다.
                    </p>
                  </div>
                  <div className="p-6 rounded-2xl bg-[#1c1c1e] border border-green-500/20 hover:bg-[#252529] transition-colors">
                    <h3 className="text-lg font-bold text-green-400 mb-2 flex items-center gap-2">
                      <i className="fas fa-robot"></i> Perplexity (Sub)
                    </h3>
                    <p className="text-sm text-gray-400 leading-relaxed">
                      VCP 패턴 해석, 심층 수급 분석, 목표가 및 손절가 제안 (Cross-Check). Gemini의 분석 결과를 검증합니다.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Market Gate Card (1/3) - Moved Here */}
            <div className="p-8 rounded-3xl bg-[#13151A] border border-white/5 hover:border-orange-500/30 transition-all group hover:-translate-y-1 h-full flex flex-col justify-center">
              <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mb-6 text-orange-500">
                <i className="fas fa-dungeon text-xl"></i>
              </div>
              <h3 className="text-xl font-bold mb-3">Market Gate</h3>
              <p className="text-sm text-gray-400 mb-6 leading-relaxed">
                시장 전체의 상태와 주도 섹터를 분석합니다.
              </p>
              <ul className="space-y-3 text-sm text-gray-300">
                <li className="flex items-center gap-2">
                  <i className="fas fa-check-circle text-orange-500"></i>
                  <span>EMA 추세 정배열 (25점)</span>
                </li>
                <li className="flex items-center gap-2">
                  <i className="fas fa-check-circle text-orange-500"></i>
                  <span>RSI & MACD (45점)</span>
                </li>
                <li className="flex items-center gap-2">
                  <i className="fas fa-check-circle text-orange-500"></i>
                  <span>거래량 & 상대강도 (30점)</span>
                </li>
              </ul>
              <div className="mt-8 pt-6 border-t border-white/5 text-center">
                <p className="text-xs text-gray-500 mb-2">모니터링 대상</p>
                <div className="flex flex-wrap justify-center gap-2">
                  <span className="px-2 py-1 bg-white/5 rounded text-xs text-gray-400">반도체</span>
                  <span className="px-2 py-1 bg-white/5 rounded text-xs text-gray-400">2차전지</span>
                  <span className="px-2 py-1 bg-white/5 rounded text-xs text-gray-400">헬스케어</span>
                  <span className="text-xs text-gray-600 self-center">+4</span>
                </div>
              </div>
            </div>

          </div>
        </section>

        {/* Scoring Logic Detail (Tabs) */}
        <section className="py-24 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-3xl font-bold mb-12">Scoring Logic Detail</h2>

            <div className="inline-flex p-1 rounded-xl bg-[#1c1c1e] border border-white/10 mb-12">
              <button
                onClick={() => setActiveTab('vcp')}
                className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'vcp' ? 'bg-[#2c2c2e] text-white shadow-lg' : 'text-gray-500 hover:text-gray-300'}`}
              >
                VCP 분석
              </button>
              <button
                onClick={() => setActiveTab('supply')}
                className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'supply' ? 'bg-[#2c2c2e] text-white shadow-lg' : 'text-gray-500 hover:text-gray-300'}`}
              >
                수급 점수
              </button>
              <button
                onClick={() => setActiveTab('closing')}
                className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'closing' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25' : 'text-gray-500 hover:text-gray-300'}`}
              >
                종가베팅
              </button>
            </div>

            <div className="bg-[#13151A] rounded-3xl border border-white/5 p-8 md:p-12 text-left relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-[80px] pointer-events-none"></div>

              {activeTab === 'closing' && (
                <div className="animate-fade-in relative z-10">
                  <h3 className="text-xl font-bold text-blue-400 mb-6 flex items-center gap-2">
                    <i className="fas fa-question-circle"></i> 종가베팅이란?
                  </h3>
                  <p className="text-lg text-gray-300 mb-12 leading-relaxed">
                    <span className="text-white font-bold">"오늘 뜬 놈이 내일도 뜬다"</span>는 가설에 기반하여, 장 마감 직전 급등주를 매수하고 다음 날 오전 갭상승을 노리는 단타 전략입니다.
                  </p>

                  <div className="flex flex-col md:flex-row items-center gap-4 mb-12">
                    <div className="flex-1 w-full p-6 rounded-2xl bg-[#0E1117] border border-rose-500/20 text-center">
                      <div className="text-xs text-rose-500 font-bold mb-2">15:20 ~ 15:30</div>
                      <div className="text-gray-500 text-xs mb-4">장 마감 직전</div>
                      <div className="inline-block px-4 py-2 bg-rose-500/20 text-rose-400 rounded-lg font-bold">
                        <i className="fas fa-shopping-cart mr-2"></i> 선별 매수
                      </div>
                    </div>
                    <div className="hidden md:block w-12 h-px bg-gray-700 relative">
                      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] text-gray-500 bg-[#13151A] px-2 whitespace-nowrap">Overnight (보유)</span>
                    </div>
                    <div className="md:hidden h-8 w-px bg-gray-700 mx-auto"></div>
                    <div className="flex-1 w-full p-6 rounded-2xl bg-[#0E1117] border border-blue-500/20 text-center">
                      <div className="text-xs text-blue-500 font-bold mb-2">09:00 ~ 10:00</div>
                      <div className="text-gray-500 text-xs mb-4">익일 장 시작</div>
                      <div className="inline-block px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg font-bold">
                        <i className="fas fa-coins mr-2"></i> 전량 매도
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
                    <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                      <h4 className="flex items-center gap-2 font-bold mb-6 text-yellow-400">
                        <i className="fas fa-lightbulb"></i> 승리 공식 (Why?)
                      </h4>
                      <ul className="space-y-4 text-sm text-gray-400 text-left">
                        <li className="flex gap-3">
                          <i className="fas fa-check text-blue-500 mt-1"></i>
                          <div>
                            <span className="text-gray-200 font-bold block mb-1">모멘텀 지속성</span>
                            오늘 강한 종목은 내일 시초가에도 강할 확률이 높음
                          </div>
                        </li>
                        <li className="flex gap-3">
                          <i className="fas fa-check text-blue-500 mt-1"></i>
                          <div>
                            <span className="text-gray-200 font-bold block mb-1">FOMO 심리</span>
                            장 마감 후 뉴스를 접한 투자자들의 익일 아침 매수세 유입
                          </div>
                        </li>
                        <li className="flex gap-3">
                          <i className="fas fa-check text-blue-500 mt-1"></i>
                          <div>
                            <span className="text-gray-200 font-bold block mb-1">뉴스 확산</span>
                            장중 발생한 호재가 밤사이 커뮤니티로 확산되며 기대감 증폭
                          </div>
                        </li>
                      </ul>
                    </div>
                    <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                      <h4 className="flex items-center gap-2 font-bold mb-6 text-green-400">
                        <i className="fas fa-calculator"></i> 기대값 (Example)
                      </h4>
                      <div className="space-y-6">
                        <div>
                          <div className="flex justify-between text-xs text-gray-400 mb-2">
                            <span>승률 가정</span>
                            <span className="text-white font-bold">60%</span>
                          </div>
                          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 w-[60%]"></div>
                          </div>
                        </div>
                        <div className="flex justify-between text-sm py-2 border-b border-white/5">
                          <span className="text-gray-400">익절 / 손절</span>
                          <span className="font-mono font-bold text-white">+5% / -3%</span>
                        </div>
                        <div className="bg-[#13151A] p-4 rounded-xl text-center border border-green-500/20">
                          <div className="text-xs text-gray-500 mb-1">1회 매매 기대수익</div>
                          <div className="text-2xl font-black text-green-400">+1.8%</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Dos & Don'ts */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
                    <div className="border border-green-500/20 bg-green-500/5 rounded-2xl p-6">
                      <h4 className="flex items-center justify-center gap-2 font-bold mb-6 text-green-400 text-lg">
                        <i className="fas fa-check-square"></i> 진입 조건 (Dos)
                      </h4>
                      <ul className="space-y-3 text-sm text-gray-300 text-left">
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                          거래대금 500억 이상 (유동성)
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                          확실한 뉴스/재료 보유 (지속성)
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                          신고가/돌파 차트 패턴
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                          등락률 5~20% (상한가 제외)
                        </li>
                      </ul>
                    </div>
                    <div className="border border-red-500/20 bg-red-500/5 rounded-2xl p-6">
                      <h4 className="flex items-center justify-center gap-2 font-bold mb-6 text-red-400 text-lg">
                        <i className="fas fa-times-circle"></i> 회피 조건 (Don&apos;ts)
                      </h4>
                      <ul className="space-y-3 text-sm text-gray-300 text-left">
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
                          뉴스 없이 단순 급등 (작전주)
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
                          윗꼬리가 긴 캔들 (매도세)
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
                          거래대금 급감
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 bg-red-500 rounded-full"></span>
                          이미 상한가 간 종목
                        </li>
                      </ul>
                    </div>
                  </div>

                  {/* Score Logic Table (21 Points) - Rich Design */}
                  <div>
                    <h3 className="text-xl font-bold text-white mb-8">종가베팅 점수표 (21점 만점)</h3>

                    {/* Basic Score (12) */}
                    <div className="mb-8">
                      <h4 className="text-sm font-bold text-gray-400 mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-500"></span> 기본 배점 (Max 12점)
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* News Score */}
                        <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                          <div className="flex justify-between items-end mb-2">
                            <span className="font-bold text-gray-200">뉴스/재료</span>
                            <span className="text-2xl font-black text-blue-400">3<span className="text-sm text-gray-500 ml-1">점</span></span>
                          </div>
                          <div className="h-2 bg-gray-800 rounded-full mb-3 overflow-hidden">
                            <div className="h-full bg-blue-500 w-[100%]"></div>
                          </div>
                          <p className="text-xs text-gray-500">AI 호재 분석 및 강도 (3점)</p>
                        </div>

                        {/* Volume Score */}
                        <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                          <div className="flex justify-between items-end mb-2">
                            <span className="font-bold text-gray-200">거래대금</span>
                            <span className="text-2xl font-black text-blue-400">3<span className="text-sm text-gray-500 ml-1">점</span></span>
                          </div>
                          <div className="h-2 bg-gray-800 rounded-full mb-3 overflow-hidden">
                            <div className="h-full bg-blue-500 w-[100%]"></div>
                          </div>
                          <p className="text-xs text-gray-500">1조(3점), 5천억(2점), 1천억(1점)</p>
                        </div>

                        {/* Chart Score */}
                        <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                          <div className="flex justify-between items-end mb-2">
                            <span className="font-bold text-gray-200">차트/수급</span>
                            <span className="text-2xl font-black text-blue-400">4<span className="text-sm text-gray-500 ml-1">점</span></span>
                          </div>
                          <div className="h-2 bg-gray-800 rounded-full mb-3 overflow-hidden">
                            <div className="h-full bg-blue-500 w-[100%]"></div>
                          </div>
                          <p className="text-xs text-gray-500">신고가(+2), 외인/기관 수급(+2)</p>
                        </div>

                        {/* Candle Score */}
                        <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                          <div className="flex justify-between items-end mb-2">
                            <span className="font-bold text-gray-200">캔들/기간</span>
                            <span className="text-2xl font-black text-blue-400">2<span className="text-sm text-gray-500 ml-1">점</span></span>
                          </div>
                          <div className="h-2 bg-gray-800 rounded-full mb-3 overflow-hidden">
                            <div className="h-full bg-blue-500 w-[66%]"></div>
                          </div>
                          <p className="text-xs text-gray-500">장대양봉(+1), 기간조정(+1)</p>
                        </div>
                      </div>
                    </div>

                    {/* Bonus Score (9) */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-400 mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-yellow-500"></span> 가산점 (Max 9점)
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Volume Surge Score */}
                        <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-yellow-500/20">
                          <div className="flex justify-between items-end mb-2">
                            <span className="font-bold text-gray-200">거래량 급증</span>
                            <span className="text-2xl font-black text-yellow-400">+4<span className="text-sm text-gray-500 ml-1">점</span></span>
                          </div>
                          <div className="h-2 bg-gray-800 rounded-full mb-3 overflow-hidden">
                            <div className="h-full bg-yellow-500 w-[80%]"></div>
                          </div>
                          <p className="text-xs text-gray-500">전일 대비 10배 이상 폭증</p>
                        </div>

                        {/* Daily Rise Score */}
                        <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-yellow-500/20">
                          <div className="flex justify-between items-end mb-2">
                            <span className="font-bold text-gray-200">당일 상승률</span>
                            <span className="text-2xl font-black text-yellow-400">+5<span className="text-sm text-gray-500 ml-1">점</span></span>
                          </div>
                          <div className="h-2 bg-gray-800 rounded-full mb-3 overflow-hidden">
                            <div className="h-full bg-yellow-500 w-[100%]"></div>
                          </div>
                          <p className="text-xs text-gray-500">25% 이상 급등 시 (상한가 임박)</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'vcp' && (
                <div className="animate-fade-in relative z-10">
                  <h3 className="text-xl font-bold text-rose-400 mb-6 flex items-center gap-2">
                    <i className="fas fa-chart-bar"></i> VCP 패턴이란?
                  </h3>
                  <p className="text-lg text-gray-300 mb-8 leading-relaxed">
                    마크 미너비니(Mark Minervini)의 <span className="text-white font-bold">변동성 축소 패턴(Validation Contraction Pattern)</span>을 의미하며, 주가가 상승하기 전 변동폭이 점진적으로 줄어드는 현상을 포착합니다.
                  </p>

                  <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-rose-500/20 mb-8">
                    <h4 className="text-sm font-bold text-rose-400 mb-4">감지 로직 상세</h4>
                    <ul className="space-y-3 text-sm text-gray-300">
                      <li className="flex items-center gap-3">
                        <i className="fas fa-check text-rose-500"></i>
                        <span>ATR(변동성)의 점진적 감소 확인</span>
                      </li>
                      <li className="flex items-center gap-3">
                        <i className="fas fa-check text-rose-500"></i>
                        <span>고가-저가 범위의 축소 비율 계산</span>
                      </li>
                      <li className="flex items-center gap-3">
                        <i className="fas fa-check text-rose-500"></i>
                        <span>현재가가 최근 고점 근처 위치 (매물 소화)</span>
                      </li>
                      <li className="flex items-center gap-3">
                        <i className="fas fa-check text-rose-500"></i>
                        <span><span className="text-white font-bold">Contraction Threshold: 0.7</span> (70% 이하 축소 시 인정)</span>
                      </li>
                    </ul>
                  </div>
                </div>
              )}

              {activeTab === 'supply' && (
                <div className="animate-fade-in relative z-10">
                  <h3 className="text-xl font-bold text-emerald-400 mb-6 flex items-center gap-2">
                    <i className="fas fa-hands-helping"></i> 수급 분석이란?
                  </h3>
                  <p className="text-lg text-gray-300 mb-8 leading-relaxed">
                    주가를 움직이는 주체인 <span className="text-white font-bold">외국인과 기관(Smart Money)</span>의 자금 흐름을 추적하여, 단순 개인 매수세가 아닌 메이저 주체의 매집 종목을 선별합니다.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-emerald-500/20">
                      <h4 className="text-sm font-bold text-emerald-400 mb-4">분석 가중치 (Total 100점)</h4>
                      <div className="space-y-4">
                        <div className="flex justify-between items-center text-sm">
                          <span className="text-gray-300">외국인 순매매량 (5/20/60일)</span>
                          <span className="font-bold text-white">25점</span>
                        </div>
                        <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500 w-[25%]"></div>
                        </div>

                        <div className="flex justify-between items-center text-sm">
                          <span className="text-gray-300">기관 순매매량 (5/20/60일)</span>
                          <span className="font-bold text-white">20점</span>
                        </div>
                        <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500 w-[20%]"></div>
                        </div>

                        <div className="flex justify-between items-center text-sm">
                          <span className="text-gray-300">거래량 대비 비율 (수급강도)</span>
                          <span className="font-bold text-white">20점</span>
                        </div>
                        <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500 w-[20%]"></div>
                        </div>

                        <div className="flex justify-between items-center text-sm">
                          <span className="text-gray-300">연속 매수일 (지속성)</span>
                          <span className="font-bold text-white">25점</span>
                        </div>
                        <div className="w-full h-1 bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500 w-[25%]"></div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5">
                      <h4 className="text-sm font-bold text-blue-400 mb-4">데이터 소스 우선순위</h4>
                      <ul className="space-y-3 text-sm text-gray-300">
                        <li className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">1</span>
                          <span><span className="text-white font-bold">pykrx</span> - KRX 공식 데이터 (가장 정확)</span>
                        </li>
                        <li className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">2</span>
                          <span><span className="text-white font-bold">FinanceDataReader</span> - 네이버 금융 크롤링</span>
                        </li>
                        <li className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">3</span>
                          <span><span className="text-white font-bold">yfinance</span> - Yahoo Finance API (보조)</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="py-8 bg-black border-t border-white/10 text-center">
        <div className="flex items-center justify-center gap-2 mb-4 opacity-50">
          <i className="fas fa-code"></i>
          <span className="font-mono text-sm">Engineered by Gemini Agent</span>
        </div>
        <p className="text-gray-600 text-xs">
          © 2026 KR Market Analysis System. All rights reserved.
        </p>
      </footer>
    </div >
  );
}
