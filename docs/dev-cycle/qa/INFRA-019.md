# UltraQA Report

# INFRA-019

engine: ultraqa
lifecycle: app-adapted
phase: complete
iteration: 1
same_failure_count: 0
active: false
cleanup: complete
browser_applicability: required
browser_driver: agent-browser

기준: 승인된 scheduler-truthfulness 계획. INFRA-029는 내부 배치의 로그만 변경하며 API/상태 반환은 변경하지 않는다. 웹 진입 변경은 INFRA-019 행에서 실제 랜딩으로 확인한다.

안전 경계: 원본3500/5501/live/.env값/data쓰기/실제LLM·수집·발송·거래·설정·삭제 금지. 신규 namespace만 사용. 5 cycles 또는 같은 실패3회 상한. baseline pytest2249/3skip, Vitest424/59files.

| ID | 의도·모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 데스크톱 독자 | 1280×900 실제 Next 랜딩 | agent-browser open / → AI 분석 anchor click → snapshot/PNG | GPT·Perplexity 설정 선택, 조건부 폴백; 고정 우선순위/최종 fallback 오기 없음 | PASS — 1280×900 조건부 GPT/Perplexity 설명 확인 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/desktop-ai.txt + desktop-ai.png | 정리 완료 | yes |
| S2 | 모바일 독자 | 375×812 같은 랜딩 | agent-browser set viewport → 각 AI 카드 scrollintoview → PNG | 두 문단 모두 폭 안에 읽히고 텍스트 누락 없음 | PASS — 375×812 문단 좌85/우290, 카드좌60/우315, 수평 잘림 없음 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/mobile-dom.txt + mobile-gpt-corrected.png + mobile-perplexity.png | 정리 완료 | yes |
| S3 | 인접 탭 사용자 | 실제 Scoring Logic Detail | snapshot ref로 VCP 분석 → 수급 점수 → 종가베팅 click | 각 패널 변경, AI 설명 유지, 매매 전략 15:20~15:30과 자동잡을 혼동하지 않음 | PASS — 실제 ref 클릭으로 VCP→수급→종가 패널 전환, 공급자 설명/전략시간 유지 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/vcp-after.txt + supply-after.txt + closing-after.txt + mobile-*-tab.png + final-dom-corrected.txt | 정리 완료 | yes |
| S4 | 운영자/낡은 설정 | 독립 subprocess; 실제 config와 scheduler 등록; thread/외부효과 대역 | qa/scheduler_probe.py schedule | 기본30분/17:00 잡2개, 사용자7분/18:10 반영; 폐지 JONGGA_SCHEDULE_TIME=15:20는 잡을 추가하지 않음 | PASS — 실제 등록 잡2개: 기본30분/17:00, 사용자7분/18:10; 폐지15:20값 추가잡 없음 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/qa-schedule-result.json | 정리 완료 | yes |
| S5 | 시크릿/다른 작업 보존 | 원본 package SHA; 추적 env 및 build자산 | 정적 보안검사 + SHA 대조 | 실제 .env 미추적, 새로운 NEXT_PUBLIC 비밀없음, 키 값 로그/응답/번들로 추가 유출 없음, 원본 package 동일 | PASS — 추적env예제만, 새비밀노출경로없음, 기존packageSHA보존 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/security-static.json + static-analysis.json + security-review.md + workspace.json | 정리 완료 | yes |

비적용: 새 JSON·경로·플래그 파서가 없으므로 malformed JSON/경로이탈 제품 행은 없음. UI에는 외부 텍스트 입력 없음. 모델 출력 실행 경계 변경 없음. 명령 timeout 및 테스트 flake는 실행 로그로 별도 판정한다.

source_commit: 3853de87b3f62018fbbb7d6466379d0a40158bea
검증 URL: http://127.0.0.1:57272/
namespace: devcycle-scheduler-ta7kuvwh

## 실제 실행과 제한

첫 커밋3853de8의 불변 소스에서 iteration1 수행. agent-browser 실제 Next페이지, 독립 subprocess 실제스케줄/체인 실행. 하네스 원본과 명령별 종료코드/timeout/로그를 증거 폴더에 보존했다. 필수5/5의 동작은 통과했고 런타임/namespace/profile을 정리했다. clone 통합·제거와 원본 파일 보존까지 확인했다.

브라우저: GET24건, 본문/자산/세션 정상. 외부font는안전설정상차단했고 favicon.ico는기존404라 아이콘자산성공을주장하지않는다. 콘솔warning/error0, 페이지error0, Next compilation/runtime0. 스크린샷7개를실제로열었고 잘못된스크롤1개는통과증거에서제외했다. viewport변경뒤ref갱신과textContent.trim 누락을하네스오류로고쳐재관측했다. 제품코드수정/검증기대완화없음.

범위 밖: 랜딩의 종가+9/-5·15일보유/기대수익 예시는JONGGA-036에 별도등록. 이번S3는탭전환과인접요소유지검사이며모든전략수치정합성을통과시킨것이아니다.

ULTRAQA COMPLETE: Goal met after 1 cycles

완료 확인: 2026-09-09 15:13 KST. 필수 5/5 통과. `../evidence/scheduler-truthfulness-2026-09-09/cleanup.json` 및 `integration.json` 참조.
