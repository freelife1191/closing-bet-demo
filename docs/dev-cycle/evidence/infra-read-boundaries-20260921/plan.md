# Read Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Parent implementation; independent source reviewers.

**Goal:** INFRA-045/046/047의 조회·기동·감사 신뢰 경계를 고정한다.
**Architecture:** 기존 scheduler/admin POST 재사용. peer IP만 감사. 새 API/프록시추정 없음.
**Tech Stack:** Flask, Python, pytest, Next.js/Vitest, ego-browser.
**Spec:** design.md

## Global Constraints

원본 .env/data/logs·3500/5501/live 접근금지. 직접 배포·실제LLM/수집/거래/삭제금지. 원본package.json보존.
최신 사용자 승인 위임하에 리더가 설계·계획 결정. 공유scratch OS sandbox, Space20 계속사용. 최대각명령300초, 리뷰15분, QA5cycles/동일실패3회.

## Review Focus

- ProxyFix 등 remote_addr를 forwarded로 덮는 미들웨어 없음 확인.
- singleton 첫 접근에서 constructor 자동sync가 남지 않음.
- scheduler-disabled에서는 자동 가격sync도 비활성, 기존수동서비스호출은 유지.
- MarketGate empty/stale에서 예전자료를 갱신중으로 잘못 표시하지 않음.
- portfolio GET 자산기록은 유지, 완전읽기전용이라 주장하지 않음.

## Task 1: Tests before change

- [ ] tests/app/test_common_routes_refactor.py: forgedheader log-event IP기대값 127.0.0.1로 변경.
- [ ] tests/app/test_kr_market_chatbot_service.py: forwarded가 있어도 remote 9.9.9.9 기대.
- [ ] after-request 활동로그 실제hook을 Flask에 등록하고 in-memory logger에서 forgedheader 무시를 검사.
- [ ] tests/app/test_common_portfolio_routes_refactor.py: GET started==0; singleton constructor auto_start_sync=False 테스트.
- [ ] tests/app/test_kr_market_system_http_routes_refactor.py: trigger 인자/deps/registry 배선을 제거한 실제 등록 계약에서 invalid/stale GET EMPTY 또는 저장값으로 새계약고정. 관리자POST기존검사유지.
- [ ] targeted RED 확인; 기존 scheduler/portfolio 연산/owner경계 baseline 확보.

## Task 2: Minimal implementation

- [ ] Flask의 `_resolve_real_ip`, `_resolve_request_ip` 본문:
```python
return request.remote_addr  # 감사 IP는 직접 연결 상대이며 사용자 IP를 보장하지 않는다.
```
- [ ] 순수 helper `extract_chatbot_client_ip(forwarded_for, remote_addr)` 본문은 전달된 인자만 사용한다. forwarded_for는호환용으로유지하고무시한다.
```python
return remote_addr
```
- [ ] portfolio GET의 start_background_sync 호출삭제.
- [ ] singleton 생성자는 `PaperTradingService(auto_start_sync=False)`.
- [ ] _bootstrap_scheduler_after_lock_acquired()의 timezone 적용 직후 기존 paper sync를 시작한다. 시작실패는 로그로남기고 기존2잡등록/loop시작은 유지하고 분당1회 paper_price_sync 잡이 같은멱등start를 재확인한다. start_scheduler()에는 추가하지 않는다.
```python
from services.paper_trading import paper_trading
paper_trading.start_background_sync()
```
- [ ] MarketGate GET에서 trigger분기 제거; `if not is_valid: gate_data = ...empty...`; 최신stale 유효자료는보존.
- [ ] Procfile삭제. CLAUDE.md의 GET쿨다운설명은 현재읽기계약으로갱신; .env.example의 독립Flask공개 PaaS예시 정리. 역사문서유지.
- [ ] targeted GREEN, 전체 pytest/Vitest/typecheck/lint/build. 소유scratch동일 sourcehash확인.

## Task 3: Review/QA/archive

- [ ] ponytail→code-review+architect→T3심층 및 인증/로그신뢰 보안검토.
- [ ] UltraQA App: portfolio 실제라우트연속GET sync0; 초기화lazy sync0; scheduler명시sync; MarketGate정상/stale/빈GET은trigger dependency없이200/adminPOST 유지; 위조IP3지점 peer; 실제NextUI반영/오류복구.
- [ ] 정적통과후첫커밋+행렬, 실제ego-browser측정. fixture로원본/외부효과차단.
- [ ] 공유QA환경정리후 필수전체통과항목만아카이브. 불확실한외부배포사용은 로컬지원정책과구분해서보고.

## 캐시 기동 회귀 보강

- [ ] tests/services/test_paper_trading_service.py: 같은 임시 DB에서 reader 선생성·빈/옛cache 확인 → writer71000저장 → reader GET71000 → writer72000저장 → reader GET72000. provider는실패spy로0호출고정.
- [ ] get_portfolio_valuation에서 비동기화 워커는 기존 `_load_price_cache_from_db()`만 호출해 공유DB cache를 읽는다. 새외부호출 없음.

## 확정된 실행 세부사항

- 기동 위치를 `_bootstrap_scheduler_after_lock_acquired()` 맨 앞의 timezone 적용 다음으로 확정한다. `start_scheduler()`에는 추가하지 않는다. scheduler lock 미획득워커는 paper singleton을 만들지 않는다. 기존 lock retry 성공도 bootstrap을 지나 승계된다.
- bootstrap에서 `try: paper_trading.start_background_sync()` / `except Exception: logger.exception(...)` 후 기존2잡등록/loop시작계속. 함수재호출은 기존sync멱등성에맡김.
- scheduler 검사: disabled와 lock경합이면 sync0, 직접획득과retry획득에서 sync1, sync예외시2잡과loop정상등록, 반복bootstrap시sync실제스레드1개(기존sync멱등성+bootstrap호출회귀).
- 캐시 검사 순서: reader부터생성하고 빈/이전cache확인 → writer가71000저장 → reader GET71000 → writer72000저장 → 두번째GET72000. 외부provider호출을 실패spy로두어0확인.
- GET전용 MarketGate 3함수 `_write_market_gate_cooldown`, `_finish_market_gate_refresh`, `_trigger_market_gate_background_refresh`와 전용전역state/lock/time/math/fcntl/TextIO import삭제. `threading`은 다른잠금에도사용하므로유지.
- app/routes/kr_market_dependency_builders.py와 kr_market_route_registry.py 및 kr_market.py의 trigger인자/deps배선제거. 해당생성자테스트도새계약에맞춤.
- tests/app/test_market_gate_refresh_cooldown.py는삭제된GET자동분석전용계약이므로폐기. 대신공개GET stale/empty/repeated/date에서외부trigger없음과adminPOST/scheduler유지검사.
- frontend/src/app/dashboard/kr/page.tsx의888행주석만현행scheduler/admin갱신설명으로바꿈. 동작변경없음. frontend-skills.md 읽었고 Next 06-fetching-data.md 번들문서읽은뒤수정. 렌더/훅/구독변경없어추가React스킬불필요.
- .env.example의구형서명설명도같은지원경계단락에서v2메서드/path서명현행으로맞춘다. 키/값변경없음.

## 리뷰 보완 실행

- [x] 날짜helper를 strictASCII두형식+datetime달력검증으로바꿈. route는ValueError를파일접근전400으로변환. traversal/불가능날짜/빈값/유니코드입력에서load0, 윤년정상경로 회귀.
- [x] 가격sync 시작실패/종료복구를 `_ensure_paper_trading_sync`와분당1회tagged job으로리더에귀속. 기존sync멱등성/프로세스락유지. 단일리더scheduler의순차잡실행으로동시호출표면을늘리지않아추가mutex제안은미반영.
