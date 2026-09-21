# VCP Real Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Parent implements; independent reviewers.

**Goal:** VCP-022의모의생산·노출·덮어쓰기재발경로를없애고현행VCP엔진을재사용한다.
**Architecture:** 기존Pandas배치builder와VCP비동기실행기/원자JSON저장재사용. 전면provenance마이그레이션없음.
**Tech Stack:** Python/Flask/pandas, Next/Vitest, ego-browser, 기존의존성핀.
**Spec:** design.md

## Global Constraints

원본.env/data/logs/3500/5501/live 접근·실행·재기동금지,실제LLM/수집/거래/설정저장/원본삭제금지. 사용자package보존.
원작업트리정본편집→소유scratch동기화후만제품실행. 기존핀사용,NumPy후보는보안차단되어재사용하지않음.
사용자승인판단위임. 과거요청주체/특정날짜순서는미확정으로명시. 스킬상한각명령300초/리뷰15분/QA5회·동일실패3회.

## Review Focus

- 일반적인산업어휘나BUY만으로기존정상분석을삭제하지않음; 정확한전체템플릿만제외.
- API캐시copy에만None할당하여원본JSON/캐시객체불변.
- 실제VCP배치가분석한뒤AI Analysis가중복호출하지않음.
- 실패/None/provider일부실패는기존정상추천·news·다른ticker를보존.
- 역사날짜가latest파일을덮지않고종료된개인키API는쿼터/분석/파일접근0.

## Task 1: 구형 생산·조회

Files: engine/kr_ai_strategies.py, engine/kr_ai_analyzer.py, engine/kr_ai_templates.py, app/routes/kr_market_signal_common.py, services/kr_market_ai_payload_service.py, 관련engine/app/service tests.

- [x] 기존Mock producer를결정론적으로실행한합성결과를fixture로고정; read-boundary가이를거부해야하는RED와일반용어를포함한정상사유유지검사추가.
- [x] templates모듈에아래의미의순수predicate를추가한다. 길이4096이하, full-match만사용.
```text
정확한 GPT 고정문장 → 템플릿
Gemini: 전체3섹션을분리하고2driver/risk가현재정적목록에있으며
3가지hypothesis중하나가driver/risk를그대로참조하는전체문장과일치 → 템플릿
나머지(같은어휘를쓴정상분석포함) → 그대로유지
```
- [x] _is_meaningful_ai_reason에서위predicate를사용(CSV·병합동일). rawAI응답은_clone_payload_for_signal_normalization의복사본에서3recommendation필드만필터한다. 원본dict수정금지.
- [x] legacy전략두개는None,가용성false로변경; 실제모델호출이라고설명하지않는다. random전용헬퍼/import삭제.
- [x] 표적pytest RED→GREEN; cache원본과정상legacy값불변확인.

## Task 2: 실제 분석과 안전한 저장

Files: services/common_update_ai_analysis_service.py, scripts/init_data.py, 관련service/script tests.

- [x] _load_ai_signal_targets의선택열에name/current_price/entry_price와기존AI_PROMPT_NUMERIC_FIELDS추가. 없는숫자는기존builder가생략한다.
- [x] 단독step: 선택/정규화/상위N dataframe에서build_ai_batch_payload를만들고 get_vcp_analyzer() + run_async_analyzer_batch() 호출. KrAiAnalyzer를호출하지않음.
- [x] 사용가능추천(action BUY/SELL/HOLD,비어있지않은사유,구형템플릿아님)이있는ticker만갱신. 기존datedpayload를복사하여새유효provider필드만대체하고None는기존값보존. news/기타ticker도보존. sanitize_for_json 후기존atomic_write_text사용.
- [x] date정규화는None/최신과YYYY-MM-DD·YYYYMMDD달력날짜만허용. filename생성전검증. dated2파일은항상성공시에만,latest2파일은오늘날짜일때만쓴다. 기존삭제함수/선삭제는제거.
- [x] 무대상은count0/기존파일보존,실패는error/count0/기존파일보존. 성공은updated count반환. common서비스의기존return무시호출과호환.
- [x] selected_items에VCP Signals가있으면기존step가이미실제분석했으므로같은날짜캐시의유효결과를재사용하고모델호출/파일write0. 유효결과없으면error로기록.
- [x] create_kr_ai_analysis는같은step를data_dir=BASE_DIR/data로부른다. CLI all의중복후속호출삭제. 필요한경로주입은실제스크립트경로를보존하는선택인자이며테스트전용분기없음.
- [x] 실제VCP클래스+가짜model응답으로batch/저장통합검사. partial/None/빈DF/history/latest/중복0회각회귀추가.

## Task 3: 구형 개인키 API 종료·정합성

Files: app/routes/kr_market_system_http_routes.py, app/routes/kr_market_dependency_builders.py, app/routes/kr_market_route_registry.py, services/kr_market_route_service.py, scripts/init_data.py, 관련route/contract tests, .claude/skills/dev-cycle/references/tier-rules.md, frontend/src/app/dashboard/data-status/page.tsx.

- [x] POST /reanalyze/gemini는410과현재VCP재분석기능안내를반환. 키/쿼터tracker/파일을열기전종료한다. 현재VCP /signals/reanalyze-failed-ai는변경없음.
- [x] 쓰이지않는legacy user reanalysis함수/deps배선만제거. create_kr_ai_analysis_with_key는직접호출호환을위해구형경로종료error/count0 반환(어떤키도읽거나사용하지않음).
- [x] 기존개인키분석성공/쿼터검사는폐기된행동으로명시하고410/쿼터0/분석0/기존VCP경로유지검사로교체.
- [x] Data Status의AI Analysis설명은실제VCP엔진재사용/통합선택시중복호출없음으로맞춤. frontend-skills/Next06-fetching-data읽고본문설명만수정한다.
- [x] 위험목록에engine/signal_tracker_ai_helpers.py추가. 실제VCP판정열을만드는기존파일이라는근거기록.

## Task 4: 리뷰·QA·마감

- [x] 전체pytest/Vitest/type/lint/build,원본package보존. ponytail→code-review+architect→T3심층/보안,입력SHA보존.
- [x] UltraQA행렬+정적통과첫커밋후소유Flask57992/Next57991/gateway57990,Space20실제VCP화면으로검증.
- [x] UI: 합성legacy템플릿은merged/raw어느경로에서도표시안됨,정상legacy실제분석과75%는유지,새실제VCP배치(transport대역)결과표시,실패시이전정상값보존,410은호출/쿼터0. API/DOM/이미지/console/Next증거대조.
- [x] 종료시소유PID/cwd/PGID확인·scratch삭제·원본불변,Space20finish1회. 요구범위검증통과후VCP022아카이브하되과거날짜의실제요청귀속미확정은명시한다.

## Critic 수정 1 — 구현 전 고정 사항

1. `scripts/init_data.py:create_signals_log`의 기존 실제 AI writer에도 과거 날짜 latest 금지를 적용한다. 과거 날짜 run_ai=True 실행 후 dated만 갱신되고 latest 두 파일의 바이트가 유지되는 회귀 검사를 추가한다.
2. 410 배선 제거 대상에는 `app/routes/kr_market.py`의 import 및 register 호출 인자를 포함한다.
3. 저장 기준: 두 종류 파일 모두 top-level metadata 및 signals-list payload인 기존 스키마를 유지한다. ticker-keyed dict는 analyzer 내부 반환형뿐이며 저장 전 signals 행으로 변환한다. 각 dated 파일을 독립적으로 읽어 그 파일 고유 metadata/news/market_indices를 보존한다. 정규화 ticker로 병합하고 신규 ticker는 selected target의 ticker/name 및 유효 analyzer provider 필드로 생성한다. 기존 없는 파일은 각각 {signals: [], signal_date: 분석 날짜, generated_at: 현재 시각}에서 시작한다. latest는 오늘 성공 때 같은 스키마의 병합 결과로 갱신한다.
4. 통합 실행도 선택 날짜 CSV에서 실제 target을 확정한다(vcp_df=True를 DF로 오인하지 않음). target 0은 done/count0/write0. 대상이 있으면 동일 날짜와 대상 ticker 교집합의 유효 캐시만 재사용한다. 교집합 결과가 없으면 error/write0. 특정 실행의 새 생산 여부는 캐시만으로 증명할 수 없으므로 성공 메시지는 저장 결과 재사용이라고 표현한다.
5. Gemini hypothesis 세 종류를 각각 검사한다. 첫 hypothesis는 driver만 참조하며 risk 삽입을 요구하지 않는다. 두 driver 동일, 한 글자 변형, 4096자 초과도 매개변수 검사한다.
