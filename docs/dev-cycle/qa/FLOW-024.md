# [FLOW-024] 시그널 추적기 수급 점수의 빈 칸 제외 — QA 시나리오

- 대상 흐름: `run.py` 메뉴 2 「VCP 시그널 생성」의 첫 단계 `create_tracker().scan_today_signals()`
- 구성 근거: 설계 승인(대화 2026-09-25 21:30, TODO [FLOW-024] 절). 호출 경로: `scan_today_signals` → `_load_supply_source_frame`
  → `_build_supply_score_frame`(SQLite 점수 캐시, 변경: 키 접미사 `_v2`) → `build_supply_score_frame`(변경: 최근 5행의 외국인·기관
  `count` 가 모두 5 인 종목만 남김) → 종목별 `detect_vcp_forming` → 시그널 프레임. 메뉴 2 는 이어서 AI 분석(LLM 비용)과 저장 질문으로
  가므로 하네스는 `scan_today_signals` 까지만 부른다
- browser_applicability: not_applicable. `scan_today_signals` 의 호출자는 `run.py` 메뉴 2 와 수동 스크립트 `tests/verify_vcp_pipeline.py`
  뿐이다. 웹 VCP 파이프라인(`services/kr_market_vcp_background_service.py`, `services/common_update_pipeline_steps.py`)은
  `create_signals_log` 와 `update_open_signals` 만 부른다(2026-09-25 grep). 그래서 CLI·서비스 하네스로 검사한다
- 검증 기준 커밋: 새 코드는 이 문서를 담은 첫 커밋, 대조용 수정 전 코드는 `72fc8c17`. 사본은 각 커밋의 `git archive` 다
- QA 엔진(engine): Claude Code. `[FLOW-022]`·`[FLOW-023]` 과 같은 방식으로 시나리오를 직접 구성했고 `/qa-only`·`/qa` 스킬 본체는 부르지
  않았다(두 스킬은 웹 앱 탐색용이고 이 흐름에는 화면이 없다)
- 격리: 각 커밋의 `git archive` 를 scratchpad `flow024/qa-new/`·`flow024/qa-old/` 에 풀고 사본의 `secrets/`·`data/`·`.env*` 를 지운다.
  고정 자료는 scratchpad `flow024/qa-data-<시나리오>/` 에 따로 만든다. 원본 `data/`·`.env` 는 쓰지 않는다
- 하네스(`flow024/qa_scan.py`, 저장소에 두지 않는다): 인자로 받은 사본 경로를 `sys.path` 맨 앞에 넣고, loopback 이 아닌 소켓 연결을 막아
  `QA-BLOCKED` 로 남긴 뒤 `create_tracker(data_dir=<고정 자료>).scan_today_signals()` 를 한 번 부른다. 결과의 `ticker`·`foreign_5d`·
  `inst_5d`·`score`·`vcp_score` 와 `engine.signal_tracker_supply_helpers` 로거의 줄을 출력한다. 환경은 `KRX_ID=`·`KRX_PW=` 빈 값
- 단계(phase): 시나리오 구성 완료 | 실행 전
- 반복(iteration): 0회
- baseline 상태: 수정 전 코드 사본에 같은 고정 자료로 같은 하네스를 돌려 대조한다. 회귀 테스트는 수정 전에 실패했다
  (`test_build_supply_score_frame_drops_tickers_with_blank_values_in_the_window`, 000001·000002 가 남음)
- 필수 여부(required): S-1~S-5 예
- 결과:
- 증거:
- 정리(cleanup):

고정 자료는 다음과 같다. 수급 CSV 는 2026-09-17·18·21·22·23·24 여섯 거래일이고 값은 원 단위다. 네 종목 모두 외국인 6억·기관 3억을
날마다 넣고, 아래 「빈 칸」만 비운다. 가격 CSV 는 네 종목 모두 `tests/engine/test_signal_tracker_refactor.py` 의 `_build_price_frame`
과 같은 20일 수축 모양이라 `detect_vcp_forming` 을 통과한다. 종목 목록 CSV 에 이름을 둔다. 점수는 외국인 5일 합 10억 초과 40, 기관 5억
초과 30, 외국인 연속 순매수일×6(최대 30)이다.

| 종목 | 빈 칸 | 새 코드 기대 | 수정 전 코드 기대 |
|---|---|---|---|
| 900241 QA외국인빈칸 | 09-22 외국인 | 시그널 없음 | 외국인 24억·기관 15억·82점(연속 2일) |
| 900242 QA기관빈칸 | 09-22 기관 | 시그널 없음 | 외국인 30억·기관 12억·100점 |
| 900243 QA정상 | 없음 | 외국인 30억·기관 15억·100점 | 같음 |
| 900244 QA창밖빈칸 | 09-17 외국인·기관(최근 5행 밖) | 외국인 30억·기관 15억·100점 | 같음 |

## S-1 외국인 칸이 빈 종목은 점수에서 빠진다 (필수)

- 절차: 고정 자료 `qa-data-main/` 로 새 코드 사본의 하네스를 돌린다
- 기대: 결과에 900241 이 없다. 로그에 「최근 5행에 빈 수급 값이 있어 점수에서 제외: 2개 종목」이 한 번 찍힌다. 수정 전 코드 사본은 900241 을
  24억·82점으로 내놓는다
- 실제:

## S-2 기관 칸이 빈 종목은 점수에서 빠진다 (필수)

- 절차: S-1 과 같은 실행
- 기대: 결과에 900242 가 없다. 수정 전 코드 사본은 900242 를 기관 12억·100점으로 내놓는다
- 실제:

## S-3 정상 종목의 결과는 수정 전과 같다 (필수)

- 절차: S-1 과 같은 실행에서 900243 의 행을 두 사본끼리 비교한다
- 기대: 두 사본 모두 900243 을 외국인 3,000,000,000·기관 1,500,000,000·100점으로 내놓고 `vcp_score` 도 같다
- 실제:

## S-4 예전 코드가 채운 SQLite 점수 캐시를 새 코드가 다시 쓰지 않는다 (필수)

- 절차: `qa-data-main/` 을 복사한 `qa-data-cache/` 에서 수정 전 코드 하네스를 먼저 돌려 `runtime_cache.db` 에 예전 프레임을 남긴다. 파일을
  바꾸지 않은 채 같은 자료로 새 코드 하네스를 돌리고, 한 번 더 돌린다
- 기대: `runtime_cache.db` 에 예전 접미사 키가 남아 있는 상태에서도 새 코드 두 번 모두 900241·900242 가 없다. 두 번째 실행은 새 접미사
  `_v2` 키를 읽는다(첫 실행 뒤 그 키가 생긴다)
- 실제:

## S-5 최근 5행 밖의 빈 칸은 종목을 빼지 않는다 (필수)

- 절차: S-1 과 같은 실행
- 기대: 새 코드 사본이 900244 를 외국인 30억·기관 15억·100점으로 내놓는다. 수정 전 코드 사본과 같다
- 실제:
