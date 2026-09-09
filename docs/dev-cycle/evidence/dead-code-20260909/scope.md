# CHAT-005 · INFRA-021 정리 범위

- 사용자 근거: 2026-09-09 현재 대화의 「연관된 라운드들 쭉 이어서」「최대한 한번에 묶어서」 및 AGENTS의 AUTO-CONTINUE. 별도의 설계 승인 응답을 받은 것으로 기록하지 않는다.
- brainstorming: bounded. 쓰이지 않는 프롬프트 상수·private 래퍼·성과 보고서 제거, 종료 시 초기화 잔재 제거. 살아 있는 서비스 함수·모델 호환 경로 유지.
- 묶음 이유: 독립적인 제거 작업의 전체 pytest·vitest와 T2 독립 리뷰 비용을 공유한다. 기능을 통합하지 않는다.
- INFRA-021: get_performance_report, 단독 종속 normalization/defaults, 전용 테스트 2개 제거. 공유 CSV/SQLite 캐시는 유지한다.
- CHAT-005: 상수 3개/private 래퍼 3개 및 단독 import 제거. close는 클라이언트 종료 위임/client=None 유지, 생성자 초기화를 반복하지 않는다. 공개 model_name 호환 경로 유지.
- 검증: baseline/회귀 테스트 → ponytail → code-review와 architect → 전체 pytest·vitest → 첫 구현/행렬 커밋 → UltraQA App-adapted 격리 Python 하네스 → 기록/아카이브.
- 상한: 리뷰 레인별 10분, 전체 라운드 60분; 동적 하네스 30초, UltraQA 최대 5회/동일 실패3회.
- 안전: 원본 3500/5501/live 요청·재시작, 실 LLM/수집/거래/발송/설정저장/삭제 금지. 사용자 root package.json, 시크릿, data 보존. .omx/state 조작하지 않는다.
- 브라우저 판정: 삭제 대상은 호출자 없는 상수·래퍼·함수이며 바뀌는 살아 있는 close는 atexit 정리에서만 실행된다. API/응답/UI 계약 변경이 없어 not-applicable. 모의 HTML로 실측을 주장하지 않는다.
- 상태 조사: TODO51(P1 11/P2 40), 최근 CHAT-013/015/FE-038 완료. 남은 FLOW-013/INFRA-018 QA 파일은 현재 TODO와 다른 옛 제목의 완료 기록이라 재개 대상으로 삼지 않는다. INFRA-045/046 배포 정보 대기 유지. INFRA-030은 실행 KRX 동등성 대조가 필요한 T3로 별도 유지.

## 구현 전후 근거

INFRA-021 기준 표적22통과 → 전용2개 삭제 후20통과. 첫 편집에서 nested def 경계를 잘못 잡아 IndentationError가 났으며, 원본에서 top-level 함수 경계로 삭제 범위를 바로잡아 통과했다. 실패 원문 infra021-target.log 보존. CHAT-005 close 회귀는 RED의 stock map reload 실패 후 GREEN1, 관련 호환46통과. 원문 chat005-*.log.

전체 검증은 git archive와 변경7파일을 복사한 scratch에서 실행하며 시크릿/data를 복사하지 않는다. 최초 frontend node_modules 심볼릭 링크는 Turbopack의 root 밖 symlink 거부 및 Vitest 캐시 쓰기 EPERM을 일으켰다. 설치된 의존성을 scratch에 APFS copy-on-write 복사하고 같은 전체 명령으로 재검증한다. 원본 의존성/제품 코드를 이 환경 문제 때문에 바꾸지 않는다.

Turbopack 로컬 IPC 차단은 localhost 포트 생성·수신 진단으로 허용을 확인한 뒤, 실패한 scratch .next 캐시를 제거하고 해결했다. 전체 Vitest462/67파일 통과(실제 build2개·tsc 포함). 이전 IPC 오류는 캐시 제거 전 재실행에도 남았고 원문 no-ipc/cached-ipc 로그에 보존했다. 제품 소스 수정 없이 검증 환경을 보완한 결과다. 전체 pytest2279/3skip: 기존 수동2개 외 tests/scripts/test_env_value_sh.py의 실제 .env 대조는 복사하지 않은 비밀 파일이 없어서 skip. 이 라운드의 필수 변경 검사는 skip 없음.
