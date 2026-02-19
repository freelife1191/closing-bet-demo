# 디테일(3분 이상) 시나리오

- project: Smart Money Bot
- targetDurationSec: 220
- ttsPolicy: seminar(4.4~4.8 syll/sec, default 4.6)
- syncPolicy: speed -> compression -> scene_extend(no-cut)

| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | 00:00-00:15 | `/` | 랜딩 Hero와 가치 제안 노출 | Smart Money Bot은 한국 주식의 Market-First 운용 원칙 위에서 VCP와 종가베팅 전략을 AI로 연결해 실행하는 통합 시스템입니다. | 4.5 | Market-First + VCP + 종가베팅 통합 |
| S2 | 00:15-00:31 | `terminal:./restart_all.sh` | Quick Start 명령과 서비스 포트 확인 | 운영 시작은 restart_all.sh 하나로 백엔드 5501과 프론트엔드 3500을 동시에 띄우고 stop_all.sh로 안전하게 종료하는 구조입니다. | 4.5 | restart_all.sh / stop_all.sh 운영 |
| S3 | 00:31-00:49 | `README.md#architecture` | 아키텍처 다이어그램과 Data Layer 강조 | Data Layer는 Toss Securities API 우선, pykrx·yfinance 폴백, 뉴스 수집을 결합해 시세·수급·재료 데이터의 신뢰성과 연속성을 확보합니다. | 4.5 | Toss 우선 + pykrx/yfinance 폴백 |
| S4 | 00:49-01:03 | `/dashboard/kr` | KR Market Gate 점수와 상태 배지 확대 | Market Gate는 코스피·코스닥, 환율, 섹터 강도를 종합해 OPEN 또는 CLOSED를 판정하고 무리한 종목 진입을 상단에서 차단합니다. | 4.6 | Market Gate OPEN/CLOSED 판정 |
| S5 | 01:03-01:19 | `engine/phases.py` | Phase1~4 파이프라인 코드 스냅샷 | 엔진은 Phase1 사전 필터링, Phase2 뉴스 수집, Phase3 LLM 배치 분석, Phase4 최종 시그널 확정으로 책임을 분리해 유지보수성을 높입니다. | 4.5 | Phase1~4 책임 분리 아키텍처 |
| S6 | 01:19-01:33 | `engine/scorer.py` | 점수/등급 계산 로직과 임계값 강조 | Scorer와 Grade 체계는 거래대금, 수급, 패턴 완성도, 리스크 항목을 수치화해 S/A/B 등급으로 의사결정 우선순위를 명확히 만듭니다. | 4.6 | 점수화 + S/A/B 등급화 |
| S7 | 01:33-01:46 | `/dashboard/kr/vcp` | 실시간 VCP 테이블과 VCP 기준표 모달 확인 | VCP 페이지는 Score 60+ 필터, VCP 범위 시각화, 차트 패턴 검증을 결합해 변동성 수축 후보를 기술적으로 빠르게 추려냅니다. | 4.5 | VCP Score60+ + 범위 시각화 |
| S8 | 01:46-02:00 | `/dashboard/kr/vcp` | Gemini/GPT/Perplexity AI 탭 순차 전환 | Gemini·GPT·Perplexity의 교차 검증 결과를 한 화면에서 비교해 단일 모델 편향을 줄이고 매수·보유·회피 판단의 신뢰도를 올립니다. | 4.8 | Multi-Model AI 교차 검증 |
| S9 | 02:00-02:15 | `/dashboard/kr/closing-bet` | Jongga V2 최신 결과와 상태 영역 스크롤 | 종가베팅은 점수 구성, 등급 기준, 최신 결과 조회와 상태 추적을 제공하고 run·analyze·reanalyze 흐름으로 장마감 전략을 즉시 갱신합니다. | 4.7 | Jongga V2 run/analyze/reanalyze |
| S10 | 02:15-02:28 | `/dashboard/kr/closing-bet` | 재분석 버튼과 메시지 전송 기능 포커스 | reanalysis와 message API는 후보군 해석을 재계산한 뒤 팀 채널로 바로 공유해 분석과 실행 사이의 지연을 줄여줍니다. | 4.5 | 재분석 후 즉시 메시지 공유 |
| S11 | 02:28-02:40 | `/dashboard/kr/cumulative` | 누적 성과 표와 백테스트 카드 확대 | 누적 성과 화면은 페이지네이션 히스토리, 승률, 평균수익, 백테스트 요약을 제공해 전략 품질을 감이 아닌 데이터로 관리하게 합니다. | 4.8 | 누적 성과 + 백테스트 데이터 관리 |
| S12 | 02:40-02:53 | `/dashboard/kr/vcp` | 매수·매도 모달과 포트폴리오 히스토리 연계 | 모의투자 서비스는 포트폴리오, 입출금, 매매 이력, 자산 곡선을 SQLite로 기록해 실제 운용 전에 실행 규율을 검증하도록 돕습니다. | 4.5 | 모의투자 실행 규율 사전 검증 |
| S13 | 02:53-03:07 | `/chatbot` | 세션 목록/모델 선택/추천 질문 흐름 시연 | AI 상담은 세션·히스토리·프로필·모델·제안 프롬프트·쿼터 API를 통합해 시장 질문, 종목 질문, 리스크 질문을 연속적으로 처리합니다. | 4.5 | AI 상담 세션·히스토리·쿼터 통합 |
| S14 | 03:07-03:21 | `services/scheduler.py` | 스케줄러 체인과 lock 처리 로직 하이라이트 | 스케줄러는 lock 파일로 중복 실행을 막고 장중/장마감 체인에서 Market Gate 갱신, VCP 분석, AI 종가베팅, 알림 발송을 자동화합니다. | 4.8 | lock 기반 스케줄링 자동 체인 |
| S15 | 03:21-03:40 | `project/project-showcase-kit/scripts/pipeline/run_all.sh` | showcase-scenario stage와 검증 리포트 확인 | project-showcase-kit은 preflight부터 validate까지 파이프라인을 오케스트레이션하고 시나리오·TTS·자막·용어 감사 결과로 산출물 품질을 보증합니다. | 4.6 | 파이프라인+용어감사+싱크검증 |
