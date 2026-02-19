# 보통(2분) 시나리오

- project: Smart Money Bot
- targetDurationSec: 120
- ttsPolicy: seminar(4.4~4.8 syll/sec, default 4.6)
- syncPolicy: speed -> compression -> scene_extend(no-cut)

| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | 00:00-00:14 | `/` | 핵심 가치 슬라이드 노출 | Smart Money Bot은 Rule-based Screening과 AI Reasoning을 결합해 한국 주식 매매 신호 품질을 끌어올립니다. | 4.8 | Rule-based Screening + AI Reasoning |
| S2 | 00:14-00:27 | `README.md` | 데이터 레이어 다이어그램 포커스 | 데이터 레이어는 Toss Securities API 우선, pykrx·yfinance 폴백, 뉴스 크롤링으로 입력 품질을 유지합니다. | 4.8 | Toss 우선, pykrx/yfinance 폴백 |
| S3 | 00:27-00:38 | `engine/phases.py` | Phase1~4 파이프라인 코드 하이라이트 | 엔진은 Phase1~4 구조로 사전 필터링, 뉴스 수집, LLM 배치 분석, 시그널 생성을 역할로 분리해 처리합니다. | 4.6 | Phase1~4 파이프라인 분리 처리 |
| S4 | 00:38-00:51 | `/dashboard/kr` | Overview KPI와 KR Market Gate 강조 | Overview의 KR Market Gate는 시장 점수와 상위 섹터를 보여주고 interval 설정으로 자동 갱신 주기를 제어합니다. | 4.7 | Overview + KR Market Gate + interval |
| S5 | 00:51-01:02 | `/dashboard/kr/vcp` | 실시간 시그널과 VCP 기준표 모달 표시 | VCP 페이지는 실시간 시그널, VCP 기준표, 차트 범위 표시, AI 탭 비교로 패턴 완성도를 다면으로 검토합니다. | 4.5 | VCP 기준표/차트범위/AI 탭 비교 |
| S6 | 01:02-01:13 | `/dashboard/kr/closing-bet` | Jongga V2 결과와 재분석 버튼 강조 | 종가베팅은 점수 구성, S/A/B 등급, Jongga V2 재분석과 메시지 전송 흐름으로 의사결정을 가속합니다. | 4.5 | 종가베팅 + Jongga V2 재분석 |
| S7 | 01:13-01:23 | `/dashboard/kr/cumulative` | 성과 테이블과 백테스트 요약 확인 | 누적 성과 화면은 페이지네이션 히스토리와 백테스트 요약을 제공해 전략의 장기 기대값을 지속적으로 추적합니다. | 4.8 | 누적 성과 + 백테스트 요약 |
| S8 | 01:23-01:34 | `/dashboard/kr/vcp` | 매수/매도 모달과 포트폴리오 연계 강조 | 매수·매도 모달로 연결되는 모의투자 기능은 포트폴리오, 자산 곡선, 거래 로그를 함께 기록해 실행력을 점검합니다. | 4.5 | 모의투자 포트폴리오/거래로그 |
| S9 | 01:34-01:45 | `/chatbot` | 세션 목록과 모델 선택 영역 포커스 | AI 상담은 세션 관리, 모델 조회, 제안 프롬프트, 프로필·쿼터 API를 결합해 일관된 투자 대화 흐름을 제공합니다. | 4.6 | AI 상담 세션/모델/쿼터 관리 |
| S10 | 01:45-02:00 | `/dashboard/data-status` | 업데이트 진행, 알림 채널, 운영 스크립트 강조 | Data Status, 스케줄러, Telegram·Discord·Slack·Email 알림, restart_all.sh로 루프를 완성합니다. | 4.7 | Data Status + 스케줄러 + 멀티채널 알림 |
