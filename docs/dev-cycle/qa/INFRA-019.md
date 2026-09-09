# UltraQA Report

# INFRA-019

engine: ultraqa
lifecycle: app-adapted
phase: planning
iteration: 0
same_failure_count: 0
active: true
cleanup: pending
browser_applicability: required
browser_driver: agent-browser

기준: 승인된 scheduler-truthfulness 계획. INFRA-029는 내부 배치의 로그만 변경하며 API/상태 반환은 변경하지 않는다. 웹 진입 변경은 INFRA-019 행에서 실제 랜딩으로 확인한다.

안전 경계: 원본3500/5501/live/.env값/data쓰기/실제LLM·수집·발송·거래·설정·삭제 금지. 신규 namespace만 사용. 5 cycles 또는 같은 실패3회 상한. baseline pytest2249/3skip, Vitest424/59files.

| ID | 의도·모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 데스크톱 독자 | 1280×900 실제 Next 랜딩 | agent-browser open / → AI 분석 anchor click → snapshot/PNG | GPT·Perplexity 설정 선택, 조건부 폴백; 고정 우선순위/최종 fallback 오기 없음 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S2 | 모바일 독자 | 375×812 같은 랜딩 | agent-browser set viewport → 각 AI 카드 scrollintoview → PNG | 두 문단 모두 폭 안에 읽히고 텍스트 누락 없음 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S3 | 인접 탭 사용자 | 실제 Scoring Logic Detail | snapshot ref로 VCP 분석 → 수급 점수 → 종가베팅 click | 각 패널 변경, AI 설명 유지, 매매 전략 15:20~15:30과 자동잡을 혼동하지 않음 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S4 | 운영자/낡은 설정 | 독립 subprocess; 실제 config와 scheduler 등록; thread/외부효과 대역 | qa/scheduler_probe.py schedule | 기본30분/17:00 잡2개, 사용자7분/18:10 반영; 폐지 JONGGA_SCHEDULE_TIME=15:20는 잡을 추가하지 않음 | 미실행 | 없음 | 실행 후 연결 | pending | yes |
| S5 | 시크릿/다른 작업 보존 | 원본 package SHA; 추적 env 및 build자산 | 정적 보안검사 + SHA 대조 | 실제 .env 미추적, 새로운 NEXT_PUBLIC 비밀없음, 키 값 로그/응답/번들로 추가 유출 없음, 원본 package 동일 | 미실행 | 없음 | 실행 후 연결 | pending | yes |

비적용: 새 JSON·경로·플래그 파서가 없으므로 malformed JSON/경로이탈 제품 행은 없음. UI에는 외부 텍스트 입력 없음. 모델 출력 실행 경계 변경 없음. 명령 timeout 및 테스트 flake는 실행 로그로 별도 판정한다.
