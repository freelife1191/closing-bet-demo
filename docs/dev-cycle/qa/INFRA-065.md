# UltraQA Report

## 목표와 실행 경계

- 항목: INFRA-065, 인가 목록 검사의 상태 초기화·스케줄러 기동 차단
- engine: ultraqa
- lifecycle: app-adapted
- phase: static-verified
- active: true
- iteration: 1
- same_failure_count: 0
- 기준: b092bfe, 테스트 파일 하나만 변경하는 bounded/T1 설계
- 승인: 2026-09-08 현재 대화에서 사용자 「승인」. 테스트 내부 두 startup 함수 monkeypatch, 실제 factory/라우트 대조 유지, 격리 QA·리뷰·커밋.
- browser_applicability: not-applicable
- browser_driver: none
- 근거: pytest 준비 코드만 바뀌며 제품 API·인가·UI 동작 변경 없음. 동적 검증은 실제 pytest 실행으로 수행.
- 안전: 독립 clone, 가짜 상태 파일, 전체 network deny. 원본 .env/data, 3500/5501/라이브, 실제 LLM·발송·거래·재시작에 접근하지 않는다.
- 상한: 명령별120초, 같은 실패3회/최대5회. 소유 clone·하네스만 정리.

## 시나리오 행렬

공통 사용자 모델은 pytest를 실행하는 개발자이며 모든 행은 필수다. 명령은 증거의 runner.py.gz를 복원하여 실행한다.

| ID | 의도·setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup |
|---|---|---|---|---|---|---|---|
| S-1 | 실행 중 표시된 상태 파일3개, 실제 factory | runner.py safe | 파일 내용/mtime 불변, scheduler 진입0, 목록 일치 | 미실행 | 두 함수 차단 | safe* | tmp_path |
| S-2 | 관리자 게이트 한 개 제거 대역 | runner.py missing | pytest exit1, /api/kr/refresh 누락 탐지 | 미실행 | 없음 | missing* | monkeypatch |
| S-3 | 관리자 게이트 한 개 추가 대역 | runner.py extra | pytest exit1, /api/qa-only-extra 초과 탐지 | 미실행 | 없음 | extra* | monkeypatch |
| S-4 | 인접 인가·route guard 검사 | runner.py related tests/app/test_admin_gated_routes.py tests/app/test_route_guards.py | 전체 PASS, 원본 package 보존 | 미실행 | 없음 | related* | clone |

## 실행 계획과 판정

수정 전 baseline은 실제 reset 함수가 임시 상태를 바꾸는 것과 스케줄러 진입 spy를 측정한다.
실제 스케줄러는 baseline에서도 실행하지 않는다. 수정 후 동일 관측으로0회/불변을 확인한다.
라우트 등록·url_map·인가 목록 수집은 정상 행에서 실제 코드를 사용하며, 적대적 두 행만 결함을 주입한다.
잘못된 JSON/Unicode·prompt injection·취소 재개는 입력을 받지 않는 pytest setup 변경과 무관해 적용 불가다.
상태 파일은 실행중 sentinel을 사용하며 실제 파일을 읽지 않는다. 의도된 mutation exit1과 검사 실패를 구분한다.
테스트 전용 T1로 frontend lint/typecheck/build와 브라우저는 적용 불가. Python AST와 diff check 수행.

## 정리

대기. baseline·행렬·원본 보존·소유 임시 파일 정리를 모두 확인한 후 완료한다.

## 수정 전 관측과 정적 검증

- baseline 원래 인가 검사1 PASS인데 상태3파일 내용/mtime 변경, scheduler 진입 spy1회. 실제 scheduler는 대역으로 막았다.
- 동일 상태 보존 assertion을 적용한 RED: exit1, test body1 PASS + teardown error1 (`startup status files changed`). 테스트 자체의 인가 실패와 구분한다.
- 첫 baseline 하네스는 import가 만든 SQLite DB까지 UTF-8로 읽어 UnicodeDecodeError가 났다. 관측을 계약 대상 상태 JSON3개로 한정하여 수리했다. 최초 오류는 baseline-harness-error 증거에 보존했다.
- 두 startup 함수를 테스트 내부에서만 monkeypatch했다. 실제 factory, blueprint 등록, 목록 수집과 두 assertion은 유지했다.
- 관련 pytest:26 PASS/skip0, exit0,1.12s. 상태3파일 불변·scheduler 진입0을 함께 확인했다. Python AST PASS.
- T1: 테스트 파일 +7 -3. 제품 코드 수정0. lint/typecheck/build는 실행하지 않았으며 통과로 보고하지 않는다.
- import 자체의 DB 준비·dotenv 읽기·로깅 설정까지 제거한 것은 아니다. 이 때문에 검증은 .env/data가 없는 독립 clone에서만 수행했다. 전체 data 디렉터리 무변경을 주장하지 않는다.
- 증거: ../evidence/INFRA-065/ 의 baseline*, red*, related*, source.json. 명령·timeout·exit·원문 gzip 포함.
