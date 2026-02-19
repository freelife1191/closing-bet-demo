# 간소화(1분 이내) 시나리오

- project: Smart Money Bot
- targetDurationSec: 60
- ttsPolicy: seminar(4.4~4.8 syll/sec, default 4.6)
- syncPolicy: speed -> compression -> scene_extend(no-cut)

| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | 00:00-00:09 | `/` | Hero와 핵심 가치 문장 노출 | Smart Money Bot은 VCP와 종가베팅을 통합한 한국 주식 AI 분석 플랫폼입니다. | 4.6 | VCP·종가베팅 통합 AI 분석 |
| S2 | 00:09-00:18 | `/dashboard/kr` | Overview와 KR Market Gate 강조 | Overview의 Market Gate가 코스피·코스닥과 환율 위험을 먼저 점검합니다. | 4.6 | Market Gate로 시장 리스크 선점검 |
| S3 | 00:18-00:25 | `/dashboard/kr/vcp` | 실시간 VCP 시그널 목록 스크롤 | VCP 시그널은 변동성 수축과 기관·외국인 수급을 함께 필터링합니다. | 4.4 | VCP+수급 필터로 후보 압축 |
| S4 | 00:25-00:34 | `/dashboard/kr/vcp` | Gemini/GPT/Perplexity 탭 전환 | Gemini·GPT·Perplexity 교차 검증으로 AI 의견 신뢰도를 높입니다. | 4.4 | Multi-Model AI 교차 검증 |
| S5 | 00:34-00:41 | `/dashboard/kr/closing-bet` | 점수·등급·재분석 영역 포커스 | 종가베팅은 점수·등급·재분석 흐름으로 장마감 후보를 빠르게 정렬합니다. | 4.7 | 종가베팅 점수·등급·재분석 |
| S6 | 00:41-00:47 | `/dashboard/kr/cumulative` | 누적 성과/모의투자 데이터 확인 | 누적 성과와 모의투자 이력으로 전략 성능을 수치로 검증합니다. | 4.5 | 누적 성과·모의투자 검증 |
| S7 | 00:47-01:00 | `/dashboard/data-status` | Data Status와 알림 채널 상태 확인 | AI 상담, Data Status, Telegram·Discord·Slack·Email 알림으로 운영을 마무리합니다. | 4.5 | AI 상담+Data Status+멀티채널 알림 |
