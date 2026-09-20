# Infrastructure boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox tracking.

**Goal:** 승인 INFRA-028/066/048/054 4건 구현·공유검증·마감.
**Architecture:** 기존 parser, Flask 오류 wrapper, startup 안내, shell 호출을 수정한다. 새 계층/의존성 없음.
**Tech Stack:** Flask/Python, Bash, pytest, Next/Vitest, ego-browser.
**Spec:** 직전 대화의 4건 설계와 사용자 「승인」. 같은 승인 범위 계획은 dev-cycle [1] 규약에 따라 재승인 없이 진행.

## Global Constraints
- develop 기준47aa730, 사용자 root package.json 보존. 원본3500/5501/live/.env값/data내용 접근 금지.
- 실행은 git archive 사본, dotenv 비활성·비밀없는 whitelist 환경·외부망차단. 원본에서 테스트/서버/재시작 실행 금지.
- 실제 LLM/수집/인증/발송/거래/삭제/설정저장 금지. 경계 대역의 합성자료만 사용.
- T3 공유 심층·보안 리뷰. INFRA047과 배포·누적파일정리는 범위 밖.

## Review Focus
1. invalid 날짜 때문에 quota가 소모되지 않음(028).
2. custom builder에서도 내부 경로/비밀 sentinel 노출 없음(066).
3. HTTPException 상태와 Allow/Retry-After 유지(066).
4. 설정 유무는 안내하되 값은 로그/번들/API에 노출 없음(048).
5. shell 검증이 실제 사용자 프로세스를 종료하지 않음(054).

## Task 1 — INFRA-028
Files: services/kr_market_route_service.py, tests/app/test_infra_boundary_dates.py 및 기존 parser 회귀.
Interface: parse_target_dates(req_data)->list[str], invalid raises ValueError. execute_user_gemini_reanalysis_request는 400 INVALID_TARGET_DATES 반환; quota/runner 전에 검증.
계약: 날짜 문자열 단일/배열 호환, 앞뒤공백 trim, ASCII YYYY-MM-DD+date.fromisoformat, 최대30개(원시 배열길이기준), 순서/중복 유지. 누락/null/빈목록은 기존 [] 전체범위 호환; 항목 null/빈값은 거부하여 잘못된 필터가 전체분석으로 바뀌지 않게 함. 비object body도400. HTTP /reanalyze/gemini는 request.get_json()으로 원본body를 전달(silent/or{}제거), malformedJSON400/잘못contenttype415 유지. 전역 MAX_CONTENT_LENGTH는 타API 영향을 피하여 이번에 도입하지 않는다.
- [ ] tests 먼저: leap/date경계,31개,객체/개행/Unicode,invalid시quota0/runner0,valid quota기존동작.
```python
assert parse_target_dates({'target_dates':'2024-02-29'}) == ['2024-02-29']
# invalid request: status == 400; tracker.check_and_increment.assert_not_called()
```
- [ ] 격리 RED 확인후 최소구현, target GREEN.

## Task 2 — INFRA-066
Files: app/routes/route_execution.py, common_portfolio_routes.py, common_market_mock_routes.py, kr_market_{jongga_execution,system_http,data_signals}_routes.py; tests/app/test_infra_boundary_errors.py 및 영향회귀.
Interface: 현재 JSON key/error/status 형태 보존, unexpected exception은 일반문구 Internal Server Error; 기존HTTPException은 wrapper에서 re-raise하여전역상태/헤더유지. 내부logger에는원래예외 유지.
- [ ] 실제Flask test_client로 기본/custom/portfolio/HTTP예외의 유출차단·상태·헤더 RED.
```python
assert b'/private/qa-secret' not in response.data
assert response.status_code == 500
```
- [ ] 모든 execute_json_route/custom builder 호출부 조사, 원문삽입만교체, 범위밖반환dict오류까지확장하지않음. target GREEN.

## Task 3 — INFRA-048
Files: app/__init__.py, .env.example, tests/app/test_infra_boundary_startup.py.
Interface: create_app logging 설정뒤 누락/공백비밀 warning1회/생성 호출, fail-closed그대로. warning내용은 변수이름+익명/관리자화면영향만.
- [ ] 격리 factory에서 외부효과 startup경계를stub하여 missing/empty warning, configured no warning, sentinel미노출 RED.
```python
assert 'INTERNAL_IDENTITY_SECRET' in captured_log
assert 'synthetic-secret-sentinel' not in captured_log
```
- [ ] 최소 warning분기·참조본설명보완후 GREEN. 실제.env파일열지않음.

## Task 4 — INFRA-054
Files: restart_all.sh, tests/test_restart_cleanup_contract.py.
Interface: 기존3패턴각각 pkill -f 단일패턴. stop_all의확대패턴은새로복제하지않음.
- [ ] 실제shell의정리구간을 PATH대역pkill로실행: 호출3개/인자단일패턴 확인 RED. 전체restart실행금지.
```python
assert patterns == ['flask_app.py', 'next dev', 'npm.*dev']
```
- [ ] 3줄로분리후 GREEN, bash -n. restart_all.sh 자체를 실행/source하지 않는다. 파일의 정확한 pkill 명령줄만 정적으로 추출해 임시 PATH의 가짜 pkill argv 캡처기로 실행한다. 실제 pkill/kill/lsof/ss 호출과 dummy 프로세스 종료도 하지 않는다. 동적 QA 역시 같은 shell argv 캡처 경계로 실행한다.

## Task 5 — shared review and QA
- [ ] critic OKAY후 구현; ponytail→code-review+architect→T3deep+security. 같은입력SHA명시.
- [ ] 격리pytest/Vitest/typecheck/lint/build,비밀파일추적/번들sentinel검사. 명령timeout300초.
- [ ] QA행렬작성·정적통과첫커밋(TODO유지). UltraQA App대응, ego-browser 실제앱 모달/갱신실패→안전오류, retry복구. 날짜API적대적검증은보강하네스, 기존화면재분석진입은합성외부runner만. 없는UI입력조작을위조하지않음.
- [ ] 로그/요청/스크린샷열람/Next진단,필수행전부통과. CLI054,048 startup도실제격리실행.
- [ ] 소유브라우저1회finish/서버PID-cwd대조종료/scratch삭제/package보존。최종독립검증후4건아카이브(TODO22→18).

독립리뷰인접보완: common_market_mock_routes의같은원인별도wrapper를기존execute_json_route에위임하여모든등록샘플route도동일오류계약을적용한다. 생성값/성공동작변경없음. 실제route회귀와UI호출여부대조로검증한다.
