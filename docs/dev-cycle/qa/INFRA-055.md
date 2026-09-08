# UltraQA Report — INFRA-055 Next 환경 분리

- QA 엔진(engine): Codex UltraQA
- lifecycle: app-adapted
- phase: qa-ready
- iteration: 1
- same_failure_count: 0
- active: true
- browser_applicability: required
- browser_driver: agent-browser
- 근거: Next 실행 환경이 로그인 세션·신원 서명·관리자 설정 조회에 연결된다.
- 설계: 2026-09-09 사용자 「진행해」, 바로 앞 bounded/T3 설계에 대한 승인.
- 기준: 정적 검증 후 첫 구현 커밋에 고정한다. 원본 기준97113d4.
- 안전 범위: 독립 clone·합성 계정/환경·소유 loopback만. 원본3500/5501/live·실제env/data·LLM/발송/매매/변경 API 금지.
- baseline: pytest2027 PASS/3skip, Vitest373 PASS/57files(실제build포함). 명령별 JSON과 gzip 로그 보존 예정.

## 필수 행렬

| ID | 의도/모델 | setup·실행 | 기대 | 실제·결과 | 수정·증거 | cleanup |
|---|---|---|---|---|---|---|
| S-1 | 회귀: 개발 실행/캐시, 운영자 | clone.env의 합성 backend키+필수Next키, 기존legacy링크, 실제npm dev·실제dashboard·종료·warm재실행 | cache파일>0, backend sentinel 바이트일치0, 인증설정 유지 | 미실행 | 없음 | 소유Next종료, 합성env/cache제거 |
| S-2 | 회귀: 빌드/운영 실행, 운영자 | 합성 부모backend환경도 주입, 실제npm build/start·dashboard | build0, 실제페이지정상, 생성cache·bundle에 backend sentinel0 | 미실행 | 없음 | 소유Next종료, 빌드/cache제거 |
| S-3 | 인접: 관리자 정상 흐름 | 합성admin cookie, 실제SettingsModal→Next env GET→Flask 실제토큰게이트·마스킹, actual신원확인 | 관리자탭/가려진fixture값/HTTP200, admin=true | 미실행 | 없음 | 전용admin browser닫기 |
| S-4 | 적대적: 일반/익명 | 별도viewer cookie의 실제설정UI, 보강직접API, 무쿠키요청 | 관리자환경탭없음, env403, viewer신원검증성공/admin=false | 미실행 | 없음 | 전용viewer browser닫기 |
| S-5 | 적대적: 입력/파일/프로세스 | pytest가 실제launcher subprocess실행: 우선순위·특수문자·금지키·symlink·자식exit/종료 | 비밀출력없음, 실패nonzero, 무관파일보존, 자식정리 | 미실행 | 없음 | 소유tmp/PID정리 |
| S-6 | 보존/정리 | 원본package해시·source해시·소유PID/port/namespace확인, 통합후재대조 | 사용자파일불변, 필수검증범위동일, 소유잔여0 | 미실행 | 없음 | clone·합성cookies/keys·세션제거 |

모든 행 required. S1-S4 화면은 실제agent-browser 조작과 screenshot열람·네트워크상태로 확인한다. API-only를 UI증거로 세지 않는다. CLI-only S5는 none. 행마다 명령·종료코드·기대/관측·대역경계·정리기록을 증거로 연결한다.

## 완료 조건과 한계

필수6/6·T3리뷰·정적검사·정리가 모두 통과해야 완료한다. 실패최대5cycle/동일실패3회. 원본이 아니라 합성clone의새캐시를 검사한다. Next에 필요한 서버 인증키의private cache잔존은 backend-only유입과 구분하며0700을 유지한다. 실제Google OAuth·외부LLM·알림은 실행하지 않는다.

## 실행 결과

- 필수 통과: 0/6 (아직 미실행)
- 재개 판정: v10 구현·독립 리뷰·정적 검증 통과, 첫 커밋 후 실제 QA 실행
- UltraQA Report: [INFRA-055.md](INFRA-055.md)

## QA 진입 증거

v10 manifest 7개 일치. pytest2077/3skip·Vitest373·lint0error·typecheck0. 구현 단계의 실패와 수정 원문은 리뷰 문서 및 evidence에 보존. 필수 웹 행은 아직 통과로 세지 않았다.
