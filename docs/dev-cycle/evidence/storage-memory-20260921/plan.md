# Storage and memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox tracking.

**Goal:** 승인 CHAT-027/023/012 및 INFRA-032 4건 구현·검증·아카이브(TODO18→14).
**Architecture:** 기존 SqliteReadyGate의 readiness 제어만 재사용한다. 각 저장소의 SQL/테이블/트랜잭션/키/프루닝/반환 계약은 유지한다. 메모리 명령과 공용 추천 캐시 경계는 기존 저장 매니저에서 처리한다.
**Tech Stack:** Python/SQLite/Flask, Next/Vitest, UltraQA App 대응+ego-browser.
**Spec:** 현재대화 4건 bounded설계에 사용자 「승인」. 같은범위 계획에 재승인게이트를 추가하지 않는다.

## Global Constraints
- develop, baseline8b5f6d5. 사용자root package.json 수정/스테이징금지.
- 원본3500/5501/live/.env값/data내용 접근금지. 실제LLM·수집·인증·발송·거래·삭제·설정저장금지.
- 실행은git archive사본,비밀없는whitelist환경/dotenv비활성/외부망차단. 실제삭제는본라운드소유fixture/scratch만.
- 부모가공용gate/chatbot schema/TODO/QA/git/실행검증소유. 독립레인은명시파일만수정,타인변경보존.
- 기존소유자마이그레이션SQL/테이블스키마/계좌계산불변. 기존데이터재계산/원본DB열람없음.
- T3 공용DB 및메모리소유경계. critic→ponytail→code+architect→심층+보안→정적→첫커밋→UltraQA→정리→독립검수→아카이브.

## Review Focus
1. 동시강제재검사는이미진행중인초기화결과를공유하며무한재초기화하지않음.
2. DB경로가같아도테이블별gate독립(JSON/CSV별개),정규화·파일소실·실패후재시도동일.
3. 공용추천prefix만TTL/cap정리,사용자동일prefix/프로필/기타public메모리보존.
4. 재시작/다중MemoryManager에서DB·메모리·JSONsnapshot이삭제캐시를무제한되살리지않음.
5. 일반 /memory 명령이설정프로필을변경하지않고명시적 /clear all의기존전체초기화는보존.

## Task 1 — 공용 gate + CHAT012 (parent)
Files: services/sqlite_ready_gate.py, chatbot/storage_sqlite_common.py, tests/services/test_sqlite_ready_gate_refactor.py, tests/chatbot/test_storage_sqlite.py.
Interface: ensure 기존keyword인자유지 + force_recheck=False, max_ready_entries: int|None=None(호출자에이미있는동적상한보존). 새key/state계층없음.
```python
if force_recheck:
    self.ready_keys.discard(db_key)
# 기다리는강제호출도현재in_progress완료결과를받는기존chatbot계약유지
limit = self._max_ready_entries if max_ready_entries is None else max_ready_entries
```
- [x] 강제재검사/동시강제호출/실패후재시도/동적상한 회귀 RED→GREEN.
- [x] chatbot 초기화SQL callback그대로, 앞뒤condition/ready/in-progress를gate.ensure에위임.
- [x] 게이트는self.lock=threading.Lock(),self.condition=threading.Condition(self.lock)로같은잠금을공개한다. 기존test가쓰는lock/condition/ready/in-progress전역이름은gate의같은객체alias유지. 복구예외/로그bool동일.

## Task 2 — INFRA032 readiness-only 15모듈
SQL·SeenKey/counter·prune/time-state는모듈에남긴다. 이번통합은초기화상태골격만이며범용invalidate callback추가없음. 현재invalidate의추적키/시간/실패시세정리는유지한다.
각파일별gate인스턴스,JSON/CSV2인스턴스. 기존_lock/ready/condition/inprogress전역은동일객체alias로유지,기존상한값을ensure(max_ready_entries=...)로전달. SQL initializer본문변경금지.
Files/groups:
A: services/kr_market_vcp_signals_cache.py, kr_market_jongga_payload_helpers.py, kr_market_data_cache_jongga.py, kr_market_backtest_summary_cache.py, kr_market_cumulative_cache.py.
B: services/kr_market_realtime_latest_close_cache.py, kr_market_realtime_market_map_cache.py, file_row_count_cache.py; engine/signal_tracker_source_cache.py, signal_tracker_analysis_source_cache.py, kr_ai_stock_info_cache.py.
C: services/kr_market_data_cache_sqlite_payload.py, common_update_status_service.py, kr_market_realtime_price_cache.py.
D: services/paper_trading_db_setup.py(마지막검증:BEGIN IMMEDIATE/마이그레이션/rollback그대로).
```python
_GATE = SqliteReadyGate()
_READY_LOCK = _GATE.lock
_READY = _GATE.ready_keys
_CONDITION = _GATE.condition
_IN_PROGRESS = _GATE.in_progress_keys
return _GATE.ensure(db_path, initialize=_initialize_schema,
    db_path_exists=sqlite_db_path_exists, run_with_retry=run_sqlite_with_retry,
    retry_attempts=RETRY_ATTEMPTS, retry_delay_seconds=RETRY_DELAY,
    max_ready_entries=READY_MAX_ENTRIES, on_failure=_log_failure)
```
- [x] 기존pytest baseline로동작고정후 A→B→C→D 그룹검증. 독립파일편집은병렬가능,검증과판정은순서유지.
- [x] readonly SQL/force/prune/조건변수회귀그대로,결함과하네스오류분리. 필요시실제tempSQLite roundtrip·병렬ensure검사추가.
- [x] 테이블SQL AST/문자열변경없음대조,주석제외토큰줄수와diff순감계측.

## Task 3 — CHAT027/023 (memory lane)
Files: chatbot/command_service.py, runtime_setup_service.py, core.py, daily_suggestions_service.py, data_service.py, storage_memory_manager.py, storage_sqlite_memory.py, storage_sqlite_helpers.py; 관련tests/chatbot.
계약CHAT027: /memory view에서는user_profile제외; add/update/remove에해당예약키면설정화면안내후변경0. /memory clear는본인의일반메모리만지우고프로필유지. /clear all의명시적전체초기화계약은그대로. 공용USER_PROFILE자동저장함수/초기호출제거,기본프로필과소유자설정조회/저장은보존.
계약CHAT023: owner_id=''이면서literal daily_suggestions_ prefix인재생성가능캐시만1시간TTL·최대500개,최신순결정적tie-break. 메모리/SQLite/JSON snapshot일치. 일반공용/다른owner/프로필은정리하지않음. 기존prune_rows_by_updated_at_if_needed는WHERE범위가없어chatbot_memories전체에사용금지;한정SQL로처리하고범용helper확장금지.
```python
assert 'user_profile' not in rendered_memory_view
assert before_other_owner == after_other_owner
assert len(shared_suggestion_rows) <= 500
assert all(row.updated_at > cutoff for row in shared_suggestion_rows)
```
- [x] reservedprofile명령보호/owner격리/캐시TTL500/동일prefixprivate보존/재로드·snapshot·실패검사 RED.
- [x] 최소기존경계구현,공용profile를사용자에게복제하지않음,캐시prune 실패는로그로구분.
- [x] 기존메모리·프로필·추천질문회귀,임시SQLite복수매니저로검증. 원본.env USER_PROFILE값조회금지.

## Task 4 — 검증/QA/마감
- [x] baseline pytest/Vitest 및현재module분기회귀,격리검증명령timeout300초. 프론트소스변경없으면같은SHA정적결과재사용.
- [x] 공유리뷰위순서실행,전용역할불가시dev-cycle허용대체명시. 전체pytest/Vitest/typecheck/lint/build,원본packageSHA/sourceSHA확인.
- [x] 첫커밋에구현/QA행렬,TODO유지. UltraQA App대응필수행: 강제/동시/복구gate;16모듈SQL/roundtrip;profile일반명령격리;캐시TTL/500/owner/snapshot;실제chatUI메모리/프로필및대화목록/캐시화면영향;정리.
- [x] 브라우저ego사용자선택. 실제앱UI를합성auth/LLM/데이터외부경계대역과연결,제품MemoryManager/SQLite/route검증연결. 사용자금지조작을원본으로보내지않음. UI관측과HTTP/서비스하네스증거구분.
- [x] screenshots직접열람,Next진단·요청로그·하네스한계기록. 필수실패5회/동일3회한도.
- [x] 소유Spacefinish1회/3프로세스PID-cwd검증종료/port닫힘/scratch제거. 독립최종PASS후4건만TODO제거아카이브.

## Critic 보완 계약

1. 모든 legacy readiness LOCK/CONDITION/READY/IN_PROGRESS는gate가소유하는정확히동일객체alias이다. 개별모듈메모리캐시/SeenKey/counter 잠금은혼합하지않는다.
2. MemoryManager.clear_general(owner_id)를추가해 /memory clear만호출한다. SQL삭제범위는 owner_id=? AND memory_key<>'user_profile'. clear(owner_id)는전체owner삭제로남겨 /clear all 의미유지. 일반메모리명령의예약키보호는command경계에서보장하며설정저장경로는유지한다.
3. legacy JSON 권위의전체정책은변경하지않고새metadata marker/스키마도추가하지않는다. 기존빈SQLite에서JSON가져오기호환을유지하되, 가져오기전에공용literal daily_suggestions_ namespace만TTL/500으로정규화한다. 비대상owner/프로필/일반public legacy자료는보존한다. 정상SQLite조회에서도같은cache정책을적용한다.
4. 캐시전용 MemoryManager.save_daily_suggestions(key,value)->bool 및SQLhelper: upsert+expired/cap정리를동일SQLite트랜잭션에서commit(실패시rollback), 성공후SQLite재로드→강제JSONsnapshot. 일반메모리upsert/fallback경로를캐시에재사용해실패를성공으로위장하지않는다. 저장실패는false/log이며추천생성자체가성공한경우생성결과는반환가능하다.
5. snapshot실패는log/false이며이미성공한DBcommit을되돌리지않는다. 다음로드에서는JSON이나SQLite어느경로든동일namespace의만료/500제약을적용한다. 목표는만료/상한초과캐시재유입방지다. 아직유효한특정캐시키의영구삭제보장은범위밖이며캐시는재생성가능하다.
6. 동시매니저검사는각자cache업서트+prune가직렬화된뒤500이하를보장하고,owner별메모리/프로필의동시upsert를스냅샷전체재저장으로덮어쓰지않음을검증한다. cacheprune예외시부분삭제/새캐시부분저장을허용하지않고commit된DB가성공조회된때만snapshot을갱신한다.

7. SQL/JSON은동일하게캡처한now/cutoff를사용하고정렬tie-break는 updated_at DESC, memory_key DESC로고정한다. literal prefix는startswith/substr판정,LIKE의underscore wildcard사용금지. future/손상timestamp는재생성가능한무효캐시로정리한다. clear_general도SQL성공후reload→forced snapshot,SQL실패는메모리변경/legacy-only저장없이실패문구를돌린다.

## 동시성 리뷰 보완 — 정책 시각

동일cutoff는전체요청시작시각을여러IO에고정한다는뜻이아니다. 각일관된스냅샷/트랜잭션마다한번캡처한다: reader SELECT/fetch후probe시각,실제writer BEGINIMMEDIATE획득직후transaction시각(upsert/prune공유),JSONparse후시각,cache memory.get후유효성시각. 재시도는새잠금후새시각,manager가미리캡처한now를SQL/reload로넘기지않는다. 시간허용치를늘려경합을숨기지않는다. writer/reader순서교차와JSON교체/lookup도중신행회귀로고정한다.

## 스냅샷 동시성 심층 리뷰 보완

공용 _write_legacy_memory_snapshot(memories, *, allow_uncommitted=False)는sidecar flock아래권위SQLite재로드→self.memories갱신→atomic JSON replace를묶는다. 모든SQL성공snapshotwriter는이경로를쓴다. SQLreload실패는False/log/기존JSON보존,기존일반메모리SQLmutation실패경로에서만allow_uncommitted=True로기존legacy-fallback유지가능. cache/clear_general의성공commit뒤에는False기본값필수. DBcommit은snapshotlock전에종료하고lock파일은실행중삭제하지않는다. A직전B성공다른owner/profile보존회귀와가능하면3worker검증을추가한다. 새테이블/historysnapshot/legacy권위전체이관정책은변경하지않는다.

마감: 승인4건완료,후속FE043추가로잔여15.
