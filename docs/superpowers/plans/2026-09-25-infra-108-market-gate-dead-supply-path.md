# [INFRA-108] Market Gate 의 쓰이지 않는 수급 점수 경로를 삭제한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 판정에 들어가지 않는 Market Gate 수급 경로(`load_supply_data`·`score_supply`와 그 래퍼·KIS 수집기 생성·임계값)를 지워, 「임의 종목 한 행을 시장 수급으로 읽는」 결함 코드가 다시 연결될 여지를 없앤다.

**Architecture:** `analyze_market_state`(`engine/market_gate_analysis.py:106-150`)의 `total_score` 는 기술 점수 다섯 개와 급락 벌점만 쓴다. 수급 호출은 2026-02-22 `45ad2a67` 리팩터링에서 빠졌고(그 전에도 "Just for display"), 지금 운영 코드에서 `_load_supply_data`·`_score_supply`·`load_supply_data`·`score_supply` 를 부르는 곳이 없다(`git grep` 확인, 호출자는 테스트와 `scripts/test_market_gate_crash.py` 뿐). 동작을 바꾸지 않는 삭제다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25, 확인 시각 11:34, 「죽은 경로 삭제」 선택), `docs/dev-cycle/TODO.md` `[INFRA-108]` 설계 승인 줄

## Global Constraints

- 티어 T3: `engine/market_gate.py`·`engine/market_gate_fetchers_local.py`·`engine/market_gate_logic.py`·`engine/market_gate_logic_fetchers.py`·`engine/market_gate_logic_scoring.py` 가 tier-rules §2 「시장 진입 판정」에 있다.
- 판정·응답 불변: `analyze_market_state` 는 수정하지 않는다. `total_score`·`details`·저장 JSON 형식이 그대로다.
- `engine/kis_collector.py` 모듈과 그 테스트는 남긴다(자체 테스트가 있고 이번 범위가 아니다). `MarketGate` 가 기동 때 만들던 인스턴스만 없앤다.
- 원본 `data/`·네트워크·LLM 에 닿지 않는다.

## 삭제 목록

| 파일 | 삭제 |
|---|---|
| `engine/market_gate_fetchers_local.py` | `load_supply_data` 함수 전체 |
| `engine/market_gate_logic_fetchers.py` | `load_supply_data` import·`__all__` |
| `engine/market_gate_logic_scoring.py` | `score_supply` 함수·`__all__` |
| `engine/market_gate_logic.py` | `load_supply_data`·`score_supply` import·`__all__` |
| `engine/market_gate.py` | 두 `_impl` import, `KisCollector` 생성 블록(`self.kis`), `_load_supply_data`·`_score_supply` 메서드, 폴백 dataclass 의 `foreign_net_buy_threshold`, 클래스 docstring 의 「+ 수급」 |
| `engine/config.py`, `config.py` | `MarketGateConfig.foreign_net_buy_threshold` 와 그 주석(읽는 코드 없음) |
| `tests/engine/test_market_gate_fetchers_local_refactor.py` | `test_load_supply_data_reads_latest_values`, import 의 `load_supply_data` |
| `tests/engine/test_market_gate_logic_facade.py` | `score_supply` import·단언, `_Config.foreign_net_buy_threshold`, 테스트 이름을 `test_score_macro_follows_config_thresholds` 로 |
| `tests/engine/test_market_gate_analysis_refactor.py` | 가짜 게이트의 `_load_supply_data`·`_score_supply`, `_SupplyFailureGate` 와 `test_analyze_market_state_does_not_require_supply_side_path`(가짜 게이트에 수급 메서드가 없으므로 `test_analyze_market_state_builds_expected_payload` 의 `total_score == 75` 가 같은 것을 고정한다. 수급 호출을 되살리면 AttributeError → 기본 결과 50 으로 실패) |
| `scripts/test_market_gate_crash.py`, `tests/test_empty_supply.csv` | 파일 삭제(수동 스크립트와 그 자료, pytest 수집 대상 아님) |

`engine/market_gate_fetchers_local.py` 의 `from typing import Any, Dict` 도 지운다(critic 지적 1). `docs/KIS_API_GUIDE.md` 의 market_gate 연동 서술을 현행으로 고친다(리뷰 지적). README 의 `kis_collector.py` 줄은 모듈이 남으므로 그대로 두고, 모듈 존폐와 `README.md:23` 은 `[INFRA-117]` 로 넘긴다.

## Review Focus

- 다른 모듈이 `engine.market_gate_logic` 에서 `load_supply_data`·`score_supply` 를 import 하면 ImportError 로 기동이 깨진다. 삭제 뒤 `git grep` 이 0 건이어야 하고 `python -c "import flask_app"` 대신 pytest 전체가 모든 import 를 거친다.
- `MarketGate()` 생성이 KIS 토큰 파일(`engine/.kis_token_*.json`)을 읽던 부수 효과가 없어진다. 이 토큰을 다른 경로가 `MarketGate.kis` 로 빌려 쓰는지 `git grep "\.kis\b"` 로 확인한다(조사 시 0 건).
- 설정 dataclass 에서 필드를 빼면 `MarketGateConfig(foreign_net_buy_threshold=...)` 처럼 키워드로 만드는 곳이 깨진다. `git grep foreign_net_buy_threshold` 가 0 건이어야 한다.

## Task 1: 삭제와 테스트 정리

- [ ] 삭제 목록대로 지운다.
- [ ] `git grep -n "load_supply_data\|score_supply\b\|_load_supply_data\|foreign_net_buy_threshold\|self\.kis\b\|test_market_gate_crash"` 에서 `docs/` 밖 결과가 종가베팅 점수기 두 줄(`engine/scorer.py:68`, `engine/scorer_scoring_mixin.py:199` 의 `_score_supply`)뿐인지 확인한다(critic 지적 3).
- [ ] `venv/bin/python -m pytest -q -p no:cacheprovider tests/engine/test_market_gate_analysis_refactor.py tests/engine/test_market_gate_logic_facade.py tests/engine/test_market_gate_fetchers_local_refactor.py tests/engine/test_kis_collector_refactor.py` 통과
- [ ] pytest 전체 통과

## 검증과 QA

실행 코드를 바꾸므로 QA 계획을 거친다. 사용자 진입 흐름(화면의 Market Gate 카드)은 저장된 JSON 을 읽을 뿐이고 분석 함수는 바뀌지 않으므로, 격리 사본에서 `MarketGate(data_dir=사본).analyze()` 결과가 삭제 전후 같은지(가짜 가격·환율·글로벌 입력, 네트워크 없음) 비교하는 하네스로 판정한다.

## 계획 검토 반영(critic ACCEPT-WITH-RESERVATIONS)

- 지적 1(`fetchers_local` 의 남는 typing import): 삭제 목록에 넣고 반영했다.
- 지적 2(중복 테스트): 삭제했다.
- 지적 3(grep 완료 기준): 허용하는 두 줄을 기준에 적었다.
- 지적 4(`kis_collector.py` 전체가 죽은 코드, `README.md:23`): `[INFRA-117]` 로 TODO 에 등록했다.
- 지적 5(QA 방식): 수정 전 사본은 `git archive 2fbcb59a`, 시각 필드는 비교에서 빼고, 벤치마크·환율·글로벌·섹터는 고정값으로 바꾸고 소켓 연결을 막는다. 합성 `daily_prices.csv` 를 두어 pykrx 폴백에 가지 않는다. `hasattr(MarketGate(), "kis")` 도 함께 본다(`qa/INFRA-108.md`).
