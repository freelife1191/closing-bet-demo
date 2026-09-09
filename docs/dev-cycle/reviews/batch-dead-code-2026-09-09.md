# UltraQA Report

## 목표와 범위

CHAT-005와 INFRA-021을 미사용 코드 정리 묶음으로 처리한다. 호출되는 서비스 함수·모델 호환 API·공유 캐시는 보존한다. 실행 코드 206줄 삭제, 전용 테스트 2개 제거와 종료 회귀 1개 추가로 총 코드/테스트 순감 226줄이다.

brainstorming의 bounded 경로로 설계했으며 사용자의 현재 연속 진행 요청 및 AGENTS의 AUTO-CONTINUE를 따른다. 별도의 새 승인 응답을 받은 것으로 기록하지 않는다. 원문 범위는 [scope](../evidence/dead-code-20260909/scope.md)에 있다.

## 검증 경계

원본 3500/5501 및 live 서비스에는 요청하지 않았다. 시크릿과 사용자 data는 격리 환경에 복사하지 않았다. 소스는 git archive와 변경 7개 파일, 의존성은 설치된 버전의 격리 복사본으로 구성했다. 외부 네트워크·원본 저장소 쓰기를 sandbox로 차단했다. 프론트엔드 빌드에 필요한 loopback IPC만 허용하며 원본 서비스 포트로의 outbound는 차단했다.

브라우저 적용: not-applicable. 삭제 상수·래퍼·성과 보고서에는 실행 호출자가 없고, 살아 있는 close 변경은 chatbot/__init__.py의 atexit 정리 경로다. UI·API·응답·저장 데이터 계약은 변경하지 않는다. agent-browser 검증을 수행한 것으로 보고하지 않는다. 실제 SDK의 자원 해제까지 이번 검수 범위로 주장하지 않으며, 기존 close_client 위임과 client=None만 확인한다.

## 정적 및 회귀 결과

- INFRA-021: 기존 22건 → 삭제 함수 전용 2건 제거 후 20건 통과. 삭제 테스트는 최소 열 로딩/누락 열 보정만 검사했다. 유지되는 CSV/SQLite 캐시 회귀는 보존했다.
- CHAT-005: close 재조회 RED 실패 → 수정 후 1건 통과, 인접 호환·서비스 검사 46건 통과.
- 격리 전체 pytest: 2,279 passed / 3 skipped, exit 0. 기존 수동 검사 2건 및 비밀 .env 미복사로 실제 .env 대조 1건 제외. 변경 범위 필수 검사에는 skip 없음.
- 전체 Vitest: 462 passed / 67 files, exit 0. 실제 Next build 검사 2개와 tsc --noEmit 검사가 포함된다.
- lint: 0 errors / 기존 198 warnings, exit 0.
- 변경 Python 7파일 AST parse 및 diff check 통과. Python LSP 검증으로 표현하지 않는다.

## 실패와 보완

첫 INFRA-021 테스트 삭제 편집은 nested def를 함수 경계로 잘못 판단해 IndentationError가 났다. 원본을 기준으로 top-level 함수 범위를 정확히 제거하여 20건 통과했다. 실패 원문을 보존했다.

첫 격리 Vitest는 node_modules 외부 symlink를 Turbopack이 거부했고 캐시 쓰기도 sandbox에 막혔다. 의존성을 scratch에 복사해 고쳤다. 이어 PostCSS 빌드의 로컬 IPC가 막혀 loopback을 허용했다. bind/listen 진단은 통과했으나 이전 실패 캐시 때문에 같은 오류가 남았고, 소유한 .next 캐시를 비운 뒤 전체 462건이 통과했다. 이 과정에서 제품 코드나 테스트 기대값은 바꾸지 않았다. 기존 FE-042의 간헐 실패 원인이 이것이라고 단정하지 않는다.

## 독립 리뷰

Ponytail 전용 code-reviewer: SHIP → code-review 전용 code-reviewer APPROVE · architect CLEAR. 원문은 증거 디렉터리의 각 리뷰 파일에 보존했다. 최종 합성 APPROVE. 저장소 밖 소비자 여부는 검색으로 증명할 수 없으며, 이 제거 사실을 이 보고서와 아카이브에 명시한다.

## 동적 행렬·정리

계획: [CHAT-005](../qa/CHAT-005.md), [INFRA-021](../qa/INFRA-021.md). 엔진 ultraqa, lifecycle app-adapted. 첫 구현/행렬 커밋 뒤 고정된 동일 코드의 실제 Python 클래스를 격리 하네스에서 실행한다. 검증 기준 8487e7d, phase=complete, iteration=1. 필수 시나리오 CHAT-005 3/3 · INFRA-021 3/3, 총6/6 통과. 반복 종료/reload0/모델 호환 응답/삭제표면/score0·20/유효한 KPI JSON/사용자 파일 및 정리를 실제 assert로 확인했다. 명령은 run_check.py probe, exit0(1.42초, timeout30초).

## 증거

[증거 디렉터리](../evidence/dead-code-20260909/)의 review-input.json에 기준 SHA와 파일별 SHA-256이 있다. 실행 명령·timeout·exit·소요시간은 각 단계 JSON, 원문은 각 단계 .log.gz에 원문을 손실 없이 보존한다. 초기 실패 로그와 최종 성공 로그를 구분한다.

## 완료 및 잔여 범위

소유 scratch·임시 로그·포인터를 제거했고 ps 명령행과 lsof cwd에서 소유 프로세스가 없음을 확인했다. 검토 소스7개와 사용자 root package.json의 SHA-256이 유지됐다. cleanup.json 참조. OMX hook 상태 조작 없음. 최종 코드/테스트 순감226줄. TODO51→49(P1 11/P2 38).

INFRA-030은 현재 실제 실행되는 레거시 KRX의 기능/캐시/폴백 동등성 검증이 필요한 구조 통합으로 별도 유지했다. INFRA-045/046의 배포 정보 대기 역시 유지한다. 실제 호출되는 레거시 모델·서비스·공유 캐시를 미사용으로 간주해 지우지 않았다.

ULTRAQA COMPLETE: Goal met after 1 cycles
