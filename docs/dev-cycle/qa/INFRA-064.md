# UltraQA Report — INFRA-064

## 목표와 실행 경계

날짜 지정 Market Gate GET은 조회만 수행하고, 최신 GET 자동 분석은 워커 공통으로 실행 종료 후 300초간 재시작을 억제한다. 분석 중만 initializing을 반환한다.
원본 3500/5501·운영 URL·실제 .env·data는 사용하지 않는다. 소유한 독립 develop 사본, 임시 파일, 외부 수집 대역과 실제 Next/Flask/UI로 검증한다. 원본 미추적 package.json을 보존한다.

- engine: ultraqa
- lifecycle: app-adapted
- phase: cleanup
- iteration: 2
- same_failure_count: 0
- active: true
- 기준: 5cc21835fd38ddad1ea60e7e09c7d7257b00cc94 (첫 구현 커밋)
- browser_applicability: required
- 근거: /dashboard/kr의 오늘/과거 날짜 화면과 /dashboard/kr/vcp가 변경 GET을 소비한다.
- browser_driver: agent-browser
- browser_namespace: devcycle-infra064-9f4s45-r2
- browser_session: viewer
- baseline: pytest 1965 passed/3 skipped(exit0), vitest 373 passed/57 files(exit0)
- timeout: 검사별 480초, 리뷰별 900초, 브라우저 실행별 900초. 최대 5회·동일 실패 3회.
- cleanup: 서버·브라우저·namespace 종료/제거 완료, 사본 통합 후 삭제 예정

## 시나리오 행렬

| ID | 의도·행위자 | setup·명령/하네스 | 기대 신호 | 실제 결과·수정·증거 | 정리 | 필수 |
|---|---|---|---|---|---|---|
| Q1 | 정상 최신 조회 | 임시 저장 자료와 실제 GET/분석 대역, pytest·브라우저 | 최신 자료 조회는 분석0; 낡은 자료 첫 요청1; 완료 후 값 표시 | 통과: 관련65PASS 및 아래 실제 UI/HTTP·metrics 증거 | 임시 자료 최종 제거 예정 | 예 |
| Q2 | 과거 날짜 남용 | 서로 다른 없는 날짜·빈/Unicode/특이 date를 실제 GET | date 지정 분석0, 저장된 과거 자료는 보존 | 통과: 관련65PASS 및 아래 실제 UI/HTTP·metrics 증거 | 임시 자료 최종 제거 예정 | 예 |
| Q3 | 반복·실패 재시도 | 실제 파일 잠금·시계 제어·분석/스레드 start 실패 | 종료 후 299초 억제, 300초 재실행; 실패도 동일 | 통과: 실패3종·299/300·실제 UI 재시도/중단 | 소유 실행 종료 | 예 |
| Q4 | 여러 워커·중단·잘못된 상태 | 실제 별도 프로세스/flock·잘못된 timestamp·잠금/I/O 불가 | 실행중 중복0; 다음 워커 쿨다운 공유; 불명확 상태 fail closed | 통과: 실제 별도 프로세스 회귀 및 write/partial-flush RED→GREEN | 소유 실행 종료 | 예 |
| Q5 | 사용자 UI 회귀 | agent-browser로 /dashboard/kr 오늘/과거 전환·재조회, VCP 진입 | 실제 GET과 화면값 일치; 쿨다운을 분석중으로 표시하지 않음 | 통과: 실제 UI/응답/폴링/이미지 대조; 아래 참조 | 전용 세션 종료 | 예 |
| Q6 | 실패 UI | 격리 수집 실패 뒤 실제 UI 재조회 | 즉시 재실행0; 분석중 허위 표시0; console/page 오류 평가 | 통과: 실제 UI/응답/폴링/이미지 대조; 아래 참조 | 전용 세션 종료 | 예 |
| Q7 | 검사·증거·정리 보장 | 전체 pytest/vitest, diff 검사, PID/port·원본 hash 대조 | 종료코드와 결과 일치; 필수 전부 통과; 소유 임시물 제거 | 실행 증거 통과, 최종 사본 정리 대기 | runtime-cleanup.json | 예 |

외부 자료 속 지시 실행은 이 GET의 기능이 아니므로 prompt injection 동적 행은 해당 없음. 특이 query는 코드/명령으로 평가하지 않는다. 인증 정책·관리자 강제 POST·스케줄러 변경은 범위 밖이며 실운영으로 실행하지 않는다. 하네스 setup 실패와 제품 실패를 구분해 재시도 횟수와 원인을 보존한다.

## 정적 검증

- TDD 첫 RED: 18 failed/2 passed. 날짜 조회·실패 재시도·멀티프로세스 상태·파일 오류를 재현.
- GREEN: 관련 54 passed. 손상된 미래 시각/긴 기록 복구 RED 2 failed/23 passed 후 최종 관련 59 passed.
- 전체 pytest: 1990 passed/3 skipped, exit0. 수동 Gemini 2개·격리 사본 .env 부재 1개 skip.
- 전체 vitest: 57 files/373 passed, exit0. Next build smoke 포함.
- AST: 수정 Python 4개 파싱 통과. 실제 실행/원문/종료코드는 evidence/INFRA-064 참조.
- 기존 날짜 기반 초기화 검사 하나는 승인한 새 계약에 맞춰 최신 조회의 초기화 검사로 변경하고, 별도 날짜 조회 금지 검사를 추가했다. 기대값만 낮춰 실패를 숨기지 않았다.

## 독립 리뷰 보완 이력

- 완료 기록 write 실패가 빈 파일을 남기는 root 재현: io-red 1FAIL → running 표식 및 write-first 적용 → io-green 26PASS.
- code-reviewer: 쿨다운 조회 자체의 flock 경합을 분석 중으로 오인. architect: 부분 flush 숫자를 만료 시각으로 오인. review-red 3FAIL 재현.
- exact running 판별과 cooldown:<timestamp>:end 완결 형식으로 보완. review-green은 **관련 65PASS(새 파일31개 포함)**, exit0. 이전54/59/62PASS는 중간 이력이며 최신 검사 수를 대신하지 않는다.
- type-check exit0, lint exit0(0 errors/199 warnings). 새 프론트 소스 변경 없음.

- 최종(리뷰 반영) 전체 pytest: **1996 passed/3 skipped**, exit0, 27.48초. pytest-reviewed가 최종 코드의 근거다.
- 표준 TextIOWrapper의 실제 FileIO.write ENOSPC 주입 후 close 검사: 예외28을 내면서도 wrapper/buffer/raw 모두 closed, fd는 EBADF9. 무효화된 임의 close mock과 실제 표준 IO 정리 계약을 구분했다.

## 브라우저 1회차 환경 실패

- Next64539/Flask64538, 브라우저 진입 GET /dashboard/kr 500. 제품 Market Gate GET에는 도달하지 않았다.
- exact 두 포트 Seatbelt가 Turbopack CSS/PostCSS 임시 로컬 IPC를 차단했다. globals.css → creating new process → child exited before connection 원문/정리 증거를 attempt1-*로 보존했다.
- 브라우저 명령 exit0만으로 PASS 처리하지 않고 DOM 오류 overlay와 실제 HTTP500으로 실패 판정했다.
- 전용 브라우저/Next/Flask/proxy 종료 및 실패한 .next 분리 후, 외부 outbound 차단+localhost IPC 허용으로 fixture를 재기동한다. 실제 API_URL과 브라우저 주소는 새 소유 포트에 고정한다. 원본3500/5501/live 호출은 계속 금지한다.

## 실제 브라우저·전송 결과

- 대상: Next http://localhost:64981/dashboard/kr 및 /dashboard/kr/vcp, Flask 포트는 ready.json. 검증 소스는 5cc2183과 정확히 일치(tested-source.json).
- 브라우저: agent-browser 0.31.1, 새 namespace/session viewer, 임시 synthetic NextAuth 쿠키. 실제 Next proxy와 Flask GET/validity/잠금/쿨다운을 실행했다. Market Gate API를 브라우저 mock하지 않았다.
- 외부 수집/저장 경계는 SyntheticMarketGate로 대체해 임시 JSON만 기록했다. 보조 GET은 Flask fixture이며, 빠져 있던 /api/kr/user/quota만 브라우저 응답 대역(usage0/limit10/remaining10)으로 보완했다. 쿼터 기능 검증은 주장하지 않는다.
- 현재 자료: 화면72/Bullish, 분석0. 날짜 선택은 실제 날짜 지정 버튼과 native 연도·월·일 키 입력으로 1999-01-01 선택→31/Bearish, 1999-01-02 선택→50/Neutral. 분석0 유지(metrics-dates).
- 실행 중: 실제 최신 모드 재조회에서 Market Gate GET3회·분석1/저장0, API initializing. release 후 자동 재조회가72/Bullish로 복구, 분석1/저장1(metrics-running-short, metrics-success).
- 실패: 분석1/저장0, 다음 응답은 message=데이터 없음/status=YELLOW. 6.5초 추가 대기에도 Gate 요청 수2→2, 자동 재조회0(metrics-failure, metrics-no-repoll).
- 경계: 제품 300초 상수를 유지하고 fixture 시계만299초 전진→분석1 유지; 추가1초→분석2. 성공 모드로 바꾸고 다음300초 경계에서 분석3/저장1·화면72 복구(metrics-299/300/recovery). 실제 5분을 기다린 측정으로 표현하지 않는다.
- VCP: 실제 사이드바 링크로 진입, 빈 시그널 표 정상 표시, 실제 Gate GET72 수신·분석3 유지. VCP 표의 전체 기능 검증은 범위 밖이다.
- 익명 HTTP: 쿠키 없이 실제 Next→Flask로 날짜 쿼리7종을 전달해 전부200, initializing0, 추가 분석0을 확인(anonymous-http.json).
- 최종 페이지 오류0, console error0. 초기 quota404가 만든 JSON 파싱 오류는 browser-commands 원문에 보존하고 대역 추가 후 clear/reload로 재검증했다. 기존 HMR/React 개발 로그와 caniuse 데이터 경고는 제품 실패가 아니다.
- 이미지9개를 모두 view_image로 열어 눈으로 대조했다. visual-checks.json에 크기1280×577·해시·관찰 기록이 있다. 파일 존재만으로 시각 검증을 통과시키지 않았다.

### 실측 중 하네스·검사 방식 보완

첫 독립 환경은 Turbopack 로컬 IPC 차단으로 실패했고 정리 후 두 번째 환경에서 재검증했다. 두 번째 환경 준비/시나리오 조정 과정에서는 quota 보조 응답 누락, native date input에 fill/type가 적용되지 않은 문제, 실제 UI에 없는 Initializing 문자열 대기를 각각 확인했다. 이 명령들의 timeout과 초기 console 오류를 보존했으며 성공으로 세지 않았다.

날짜는 실제 spinbutton과 press 키 입력으로 검증했다. 기존 화면은 API의 label/message를 직접 표시하지 않고 점수로 이름을 계산하므로 initializing과 empty 모두50/Neutral로 그린다. 따라서 기존 UI 계약에 맞춰 **화면 점수 + 실제 API 상태 + 자동 재조회 유무**를 함께 판정했다. 완료 후72 표시는 실제 DOM과 이미지에서 검증했다. API label이 그대로 화면에 보였다고 보고하지 않는다.

## 잔여 한계

독립 리뷰의 LOW 1건: 중단된 running을 복구하는 아주 짧은 동안 다른 요청이 그 표식을 읽으면 initializing 한 번을 볼 수 있다. 재실행/쿨다운 우회는 없고 다음 폴링에서 정정된다. 동기화 계층 추가는 하지 않는 것으로 수용했고 code-reviewer APPROVE/architect CLEAR를 받았다.
관리자 강제 POST와 스케줄러는 이번 GET 쿨다운의 대상이 아니다. 원본 환경/운영 서비스의 재시작·배포는 수행하지 않았다. 실제 시장 데이터 정확도나 외부 수집 자체는 이번 실측의 보장 범위가 아니다.

## 종료 확인

fixture/proxy/브라우저 종료 모두 exit0. 첫/두 번째 소유 포트 모두 listener0, Chrome0, 두 namespace 삭제. 사진·명령·HTTP·부수효과·실패와 수정·정리 증거는 evidence/INFRA-064에 보존했다. 남은 단계는 이 사본의 커밋 통합과 사본 삭제다.
